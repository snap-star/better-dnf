"""
Btrfs snapshot management for safe system updates.
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
from datetime import datetime, timezone

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .sudo import run_sudo

console = Console()


class SnapshotManager:
    """Manager for btrfs snapshots before system updates."""

    # Default snapshot subvolume path
    DEFAULT_SNAPSHOT_PATH = "/.snapshots"

    # Snapshot prefix for our tool
    SNAPSHOT_PREFIX = "better-dnf"

    # Keep only this many better-dnf snapshots. Older ones are removed
    # automatically after each new snapshot is created, so snapshots never
    # pile up when the user forgets to delete them by hand.
    DEFAULT_RETENTION = 30

    @classmethod
    def is_btrfs_root(cls) -> bool:
        """
        Check if the root filesystem is btrfs.

        Returns:
            True if root is btrfs, False otherwise
        """
        try:
            result = subprocess.run(
                ["findmnt", "-n", "-o", "FSTYPE", "/"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,  # Non-zero exit just means it couldn't determine the type
            )
            return result.stdout.strip() == "btrfs"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @classmethod
    def is_snapper_installed(cls) -> bool:
        """
        Check if snapper is installed.

        Returns:
            True if snapper is available, False otherwise
        """
        try:
            result = subprocess.run(
                ["which", "snapper"],
                capture_output=True,
                timeout=5,
                check=False,  # Non-zero exit just means snapper is not installed
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @classmethod
    def create_snapshot(
        cls,
        description: str | None = None,
        snapshot_type: str = "pre",
    ) -> tuple[bool, str | None, str]:
        """
        Create a btrfs snapshot before applying updates.

        Args:
            description: Optional description for the snapshot
            snapshot_type: Type of snapshot ('pre', 'post' or 'single')

        Returns:
            Tuple of (success, snapshot_id, message)
        """
        # Check if btrfs
        if not cls.is_btrfs_root():
            return (
                False,
                None,
                "Root filesystem is not btrfs. Cannot create snapshot.",
            )  # Generate snapshot name (tz-aware, displayed in local time)
        timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
        snapshot_name = f"{cls.SNAPSHOT_PREFIX}-{timestamp}"

        if description:
            snapshot_name += f"-{description.replace(' ', '-')}"

        # Try snapper first
        if cls.is_snapper_installed():
            return cls._create_snapper_snapshot(
                snapshot_name, description, snapshot_type
            )

        # Fallback to btrfs subvolume snapshot
        return cls._create_btrfs_snapshot(snapshot_name, description)

    @classmethod
    def create_post_snapshot(
        cls,
        description: str | None = None,
        pre_number: str | None = None,
    ) -> tuple[bool, str | None, str]:
        """
        Create a post-update snapshot (completes the pre/post pair).

        Snapper requires --pre-number for post snapshots and rejects the
        request when the referenced snapshot is missing, is the current
        snapshot, is not type 'pre', or already has a post snapshot.  Those
        conditions are validated up front (with a clear error), and if the
        pairing still fails a standalone 'single' snapshot is created as a
        fallback so a backup still exists.

        Args:
            description: Optional description for the snapshot
            pre_number: Number of the pre snapshot to pair with. When
                omitted, the most recent 'pre' snapshot is used.

        Returns:
            Tuple of (success, snapshot_id, message)
        """
        # Check if btrfs
        if not cls.is_btrfs_root():
            return (
                False,
                None,
                "Root filesystem is not btrfs. Cannot create snapshot.",
            )  # Generate snapshot name (tz-aware, displayed in local time)
        timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
        snapshot_name = f"{cls.SNAPSHOT_PREFIX}-post-{timestamp}"

        if description:
            snapshot_name += f"-{description.replace(' ', '-')}"

        # Try snapper first
        if cls.is_snapper_installed():
            # Load the snapshot list once: it is used both to resolve the
            # latest 'pre' snapshot and to validate the pairing up front.
            snapshots = cls._list_snapper_snapshots()

            # Snapper requires --pre-number for post snapshots. When the
            # caller didn't supply one, pair with the latest 'pre' snapshot.
            if not pre_number:
                pre_number = cls._find_latest_pre_number(snapshots=snapshots)
                if pre_number is None:
                    return (
                        False,
                        None,
                        "No pre snapshot found. Create one first with "
                        + "'better-dnf snapshot create'.",
                    )

            verdict = cls._validate_pre_for_pairing(snapshots, pre_number)
            if verdict is not None:
                return verdict

            success, snap_id, message = cls._create_snapper_snapshot(
                snapshot_name, description, "post", pre_number=pre_number
            )
            if success:
                return (
                    True,
                    snap_id,
                    f"{message} (paired with pre #{pre_number})",
                )

            # Snapper refused to pair (its daemon-side view can differ from
            # what `snapper list` reported).  Fall back to a standalone
            # snapshot so the user still has a post-update backup.
            fallback_ok, fallback_id, fallback_msg = cls._create_snapper_snapshot(
                snapshot_name, description, "single"
            )
            if fallback_ok:
                return (
                    True,
                    fallback_id,
                    "Pre/post pairing failed: "
                    + f"{message}. Created a standalone snapshot instead "
                    + f"({fallback_msg}). To pair manually, run: "
                    + f"sudo snapper create -t post --pre-number {pre_number}",
                )
            return (False, None, f"Pre/post snapshot failed: {message}")

        # Fallback to btrfs subvolume snapshot
        return cls._create_btrfs_snapshot(snapshot_name, description)

    @classmethod
    def _validate_pre_for_pairing(
        cls,
        snapshots: list[dict],
        pre_number: str,
    ) -> tuple[bool, None, str] | None:
        """Validate that a pre snapshot can be paired; None when usable.

        Snapper fails a post create with "Illegal snapshot" when the
        --pre-number reference is missing, is the current snapshot, is not
        type 'pre', or already has a post snapshot.  These conditions are
        detected here so the user gets a clear message instead of snapper's
        cryptic error.

        Returns:
            None when the pairing is valid, otherwise an error tuple
            (False, None, message).
        """
        target = next((s for s in snapshots if s.get("id") == str(pre_number)), None)
        if target is None:
            return (
                False,
                None,
                (
                    f"Pre snapshot #{pre_number} was not found in snapper. It "
                    "may have been removed by cleanup or created in a "
                    "different config. Create a fresh pre snapshot with "
                    "'better-dnf snapshot create'."
                ),
            )
        if target.get("type") != "pre":
            return (
                False,
                None,
                (
                    f"Snapshot #{pre_number} is type '{target.get('type')}', "
                    "not 'pre'. Post snapshots must pair with a 'pre' "
                    "snapshot. Create one with 'better-dnf snapshot create'."
                ),
            )
        existing_post = next(
            (
                s
                for s in snapshots
                if s.get("type") == "post"
                and str(s.get("pre_num", "")).strip() == str(pre_number)
            ),
            None,
        )
        if existing_post is not None:
            return (
                False,
                None,
                (
                    f"Snapshot #{pre_number} already has a post snapshot "
                    f"(#{existing_post.get('id')}). Use 'better-dnf snapshot "
                    "list' to see the existing pairs."
                ),
            )
        return None

    @classmethod
    def _find_latest_pre_number(cls, snapshots: list[dict] | None = None) -> str | None:
        """Find the most recent 'pre' snapshot number for post pairing."""
        if snapshots is None:
            snapshots = cls._list_snapper_snapshots()
        pres = [s for s in snapshots if s.get("type") == "pre"]
        if not pres:
            return None
        return str(max(pres, key=lambda s: int(s["id"]))["id"])

    @classmethod
    def _create_snapper_snapshot(
        cls,
        snapshot_name: str,
        description: str | None,
        snapshot_type: str = "pre",
        pre_number: str | None = None,
    ) -> tuple[bool, str | None, str]:
        """
        Create snapshot using snapper.

        Args:
            snapshot_name: Name for the snapshot
            description: Optional description
            snapshot_type: Type of snapshot ('pre', 'post' or 'single')
            pre_number: Pre snapshot number (required for 'post')

        Returns:
            Tuple of (success, snapshot_id, message)
        """
        try:
            cmd = [
                "snapper",
                "create",
                "-d",
                cls._snapper_description(snapshot_name, description),
                "-t",
                snapshot_type,
            ]
            if snapshot_type == "post":
                if not pre_number:
                    return (
                        False,
                        None,
                        "Post snapshot requires a pre snapshot number.",
                    )
                cmd += ["--pre-number", str(pre_number)]
            # Print the new snapshot number so we can return it reliably
            cmd += ["-p"]

            result = run_sudo(cmd, timeout=30)

            if result.returncode == 0:
                snapshot_id = result.stdout.strip()
                if snapshot_id:
                    return (
                        True,
                        snapshot_id,
                        f"Snapshot created successfully: {snapshot_id}",
                    )
                return (True, None, "Snapshot created successfully")
            else:
                return (False, None, f"Failed to create snapshot: {result.stderr}")

        except subprocess.TimeoutExpired:
            return (False, None, "Snapshot creation timed out")
        except Exception as e:  # noqa: BLE001 - surface any failure to the user
            return (False, None, f"Error creating snapshot: {e!s}")

    @classmethod
    def _snapper_description(cls, snapshot_name: str, description: str | None) -> str:
        """Build a snapper description that marks the snapshot as ours.

        The prefix is what lets cleanup_old_snapshots() tell better-dnf
        snapshots apart from snapper timeline snapshots and snapshots the
        user created by hand, so retention never touches those.
        """
        text = (description or snapshot_name).strip()
        if text.lower().startswith(cls.SNAPSHOT_PREFIX):
            return text
        return f"{cls.SNAPSHOT_PREFIX}: {text}"

    @classmethod
    def _create_btrfs_snapshot(
        cls,
        snapshot_name: str,
        description: str | None,
    ) -> tuple[bool, str | None, str]:
        """
        Create snapshot using btrfs command.

        Args:
            snapshot_name: Name for the snapshot
            description: Optional description

        Returns:
            Tuple of (success, snapshot_id, message)
        """
        try:
            # Create snapshots directory if it doesn't exist
            run_sudo(
                ["mkdir", "-p", cls.DEFAULT_SNAPSHOT_PATH],
                timeout=5,
            )

            # Get root subvolume
            result = run_sudo(
                ["btrfs", "subvolume", "show", "/"],
                timeout=10,
            )

            if result.returncode != 0:
                return (False, None, "Failed to get root subvolume information")

            # Create snapshot
            snapshot_path = f"{cls.DEFAULT_SNAPSHOT_PATH}/{snapshot_name}"
            result = run_sudo(
                [
                    "btrfs",
                    "subvolume",
                    "snapshot",
                    "-r",  # Read-only snapshot
                    "/",
                    snapshot_path,
                ],
                timeout=60,
            )

            if result.returncode == 0:
                return (
                    True,
                    snapshot_name,
                    f"Read-only snapshot created: {snapshot_path}",
                )
            else:
                return (False, None, f"Failed to create snapshot: {result.stderr}")

        except subprocess.TimeoutExpired:
            return (False, None, "Snapshot creation timed out")
        except Exception as e:  # noqa: BLE001 - surface any failure to the user
            return (False, None, f"Error creating snapshot: {e!s}")

    @classmethod
    def list_snapshots(cls) -> list[dict]:
        """
        List existing snapshots created by this tool.

        Returns:
            List of snapshot information dictionaries
        """

        if cls.is_snapper_installed():
            return cls._list_snapper_snapshots()

        return cls._list_btrfs_snapshots()

    @classmethod
    def _list_snapper_snapshots(cls) -> list[dict]:
        """List snapshots using snapper."""
        try:
            # Try machine-readable CSV first. --csvout is a GLOBAL option in
            # snapper, so it must precede the 'list' command.
            result = run_sudo(["snapper", "--csvout", "list"], timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                snapshots = cls._parse_snapper_csv(result.stdout)
                if snapshots:
                    return snapshots

            # Fall back to the human-readable table format
            result2 = run_sudo(["snapper", "list"], timeout=10)
            if result2.returncode == 0 and result2.stdout.strip():
                return cls._parse_snapper_table(result2.stdout)
        except Exception:  # noqa: BLE001, S110 - best-effort listing
            pass

        return []

    @staticmethod
    def _parse_snapper_csv(text: str) -> list[dict]:
        """Parse 'snapper --csvout list' output using the header to map columns.

        Real snapper CSV columns: #,Type,Pre #,Date,User,Cleanup,Description,Userdata
        Older/simpler formats may be Number,Date,Description,Type - handled by
        matching column names from the header row.
        """
        snapshots: list[dict] = []
        try:
            reader = csv.reader(io.StringIO(text))
            header = next(reader, None)
            if not header:
                return snapshots
            cols = {name.strip().lower(): i for i, name in enumerate(header)}
            num_col = cols.get("number", cols.get("#", 0))
            type_col = cols.get("type")
            date_col = cols.get("date")
            desc_col = cols.get("description")
            pre_num_col = cols.get(
                "pre #", cols.get("pre-number", cols.get("pre_number"))
            )

            for row in reader:
                if num_col >= len(row) or not row[num_col].strip().isdigit():
                    continue
                snapshots.append(
                    {
                        "id": row[num_col].strip(),
                        "date": (
                            row[date_col].strip()
                            if date_col is not None and date_col < len(row)
                            else ""
                        ),
                        "description": (
                            row[desc_col].strip()
                            if desc_col is not None and desc_col < len(row)
                            else ""
                        ),
                        "type": (
                            row[type_col].strip()
                            if type_col is not None and type_col < len(row)
                            else ""
                        ),
                        "pre_num": (
                            row[pre_num_col].strip()
                            if pre_num_col is not None and pre_num_col < len(row)
                            else ""
                        ),
                    }
                )
        except Exception:  # noqa: BLE001 - surface nothing, return what we parsed
            return snapshots
        return snapshots

    @staticmethod
    def _parse_snapper_table(text: str) -> list[dict]:
        """Parse 'snapper list' table output using the header to map columns.

        Real snapper table columns: # | Type | Pre # | Date | User | Cleanup |
        Description | Userdata.  The header row is located first, then each
        data row is mapped by column position so the 'type' field is correct
        regardless of which columns snapper decides to print.
        """
        snapshots: list[dict] = []
        lines = text.splitlines()
        header_idx = None
        cols: dict[str, int] = {}

        for i, line in enumerate(lines):
            parts = [p.strip() for p in re.split(r"[|│]", line)]
            lowered = [p.lower() for p in parts]
            if "type" in lowered and ("date" in lowered or "#" in lowered):
                header_idx = i
                cols = {p.lower(): j for j, p in enumerate(parts) if p}
                break

        if header_idx is None:
            return snapshots

        num_col = cols.get("#", cols.get("number", 0))
        type_col = cols.get("type")
        date_col = cols.get("date")
        desc_col = cols.get("description")
        pre_num_col = cols.get("pre #", cols.get("pre-number", cols.get("pre_number")))

        for line in lines[header_idx + 1 :]:
            parts = [p.strip() for p in re.split(r"[|│]", line)]
            # Skip separator rows (e.g. ----+------+-----) and empty rows
            if num_col >= len(parts) or not parts[num_col].isdigit():
                continue
            snapshots.append(
                {
                    "id": parts[num_col],
                    "date": parts[date_col] if date_col is not None else "",
                    "description": parts[desc_col] if desc_col is not None else "",
                    "type": parts[type_col] if type_col is not None else "",
                    "pre_num": (parts[pre_num_col] if pre_num_col is not None else ""),
                }
            )
        return snapshots

    @classmethod
    def _list_btrfs_snapshots(cls) -> list[dict]:
        """List snapshots using btrfs."""
        snapshots = []
        try:
            # List subvolumes
            result = run_sudo(
                ["btrfs", "subvolume", "list", "-s", cls.DEFAULT_SNAPSHOT_PATH],
                timeout=10,
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        # Parse subvolume info
                        parts = line.split()
                        if len(parts) >= 2:
                            snapshots.append(
                                {
                                    "id": parts[1],
                                    "name": parts[-1],
                                    "path": f"{cls.DEFAULT_SNAPSHOT_PATH}/{parts[-1]}",
                                }
                            )
        except Exception:  # noqa: BLE001, S110
            pass

        return snapshots

    @classmethod
    def _is_managed_snapshot(cls, snap: dict) -> bool:
        """Whether a snapshot was created by better-dnf.

        Only these are eligible for automatic deletion - snapper timeline
        snapshots and snapshots created manually are left alone.
        """
        return any(
            str(snap.get(key, "")).strip().lower().startswith(cls.SNAPSHOT_PREFIX)
            for key in ("description", "name")
        )

    @staticmethod
    def _snapshot_sort_key(snap: dict) -> int:
        """Sort key: snapshot/subvolume numbers grow with creation time."""
        raw = str(snap.get("id", ""))
        return int(raw) if raw.isdigit() else 0

    @classmethod
    def _load_snapshots(cls) -> tuple[bool, list[dict]]:
        """Return (uses_snapper, snapshots) with a single backend probe."""
        if cls.is_snapper_installed():
            return (True, cls._list_snapper_snapshots())
        return (False, cls._list_btrfs_snapshots())

    @classmethod
    def delete_snapshot(cls, snapshot_id: str) -> tuple[bool, str]:
        """
        Delete a single snapshot.

        When snapper is used and the snapshot is a 'pre' snapshot, its
        paired 'post' snapshot is deleted in the same call (snapper refuses
        to remove a pre snapshot while its post snapshot still exists).

        Args:
            snapshot_id: Snapper number, btrfs subvolume ID, or snapshot name

        Returns:
            Tuple of (success, message)
        """
        use_snapper, snapshots = cls._load_snapshots()
        target = next(
            (
                s
                for s in snapshots
                if str(s.get("id", "")) == str(snapshot_id)
                or str(s.get("name", "")) == str(snapshot_id)
            ),
            None,
        )
        if target is None:
            return (False, f"Snapshot {snapshot_id} not found")

        doomed = [target]
        if use_snapper and target.get("type") == "pre":
            for snap in snapshots:
                if snap.get("type") == "post" and str(
                    snap.get("pre_num", "")
                ).strip() == str(target.get("id", "")):
                    doomed.append(snap)
                    break

        deleted, error = cls._delete_snapshots(doomed, use_snapper)
        if deleted:
            return (True, f"Deleted snapshot {snapshot_id}")
        return (False, f"Failed to delete snapshot {snapshot_id}: {error}")

    @classmethod
    def _delete_snapshots(
        cls, snapshots: list[dict], use_snapper: bool
    ) -> tuple[int, str]:
        """Delete snapshot records (best effort).

        Returns:
            Tuple of (number deleted, error summary - empty on full success)
        """
        if not snapshots:
            return (0, "")

        if use_snapper:
            ids = [str(s.get("id", "")) for s in snapshots if s.get("id")]
            try:
                result = run_sudo(["snapper", "delete"] + ids, timeout=120)
            except subprocess.TimeoutExpired:
                return (0, "snapper delete timed out")
            except Exception as e:  # noqa: BLE001 - surface any failure to caller
                return (0, f"Error deleting snapshots: {e!s}")
            if result.returncode == 0:
                return (len(ids), "")
            return (0, (result.stderr or "snapper delete failed").strip())

        deleted = 0
        errors: list[str] = []
        for snap in snapshots:
            path = str(
                snap.get("path")
                or f"{cls.DEFAULT_SNAPSHOT_PATH}/{snap.get('name') or snap.get('id')}"
            )
            try:
                # btrfs rejects deleting read-only snapshots, so clear the
                # read-only flag first. Failure here is fine (already
                # writable), the delete below reports the real error.
                run_sudo(["btrfs", "property", "set", path, "ro", "false"], timeout=15)
                result = run_sudo(["btrfs", "subvolume", "delete", path], timeout=30)
            except subprocess.TimeoutExpired:
                errors.append(f"{path}: timed out")
                continue
            except Exception as e:  # noqa: BLE001 - keep deleting the rest
                errors.append(f"{path}: {e!s}")
                continue
            if result.returncode == 0:
                deleted += 1
            else:
                errors.append((result.stderr or f"failed to delete {path}").strip())
        return (deleted, "; ".join(errors))

    @classmethod
    def cleanup_old_snapshots(cls, keep: int = DEFAULT_RETENTION) -> tuple[int, str]:
        """
        Delete the oldest better-dnf snapshots, keeping the newest `keep`.

        Only snapshots created by better-dnf are considered, so timeline and
        hand-made snapshots are never removed.  This runs automatically
        after a snapshot is created; it is safe to call at any time.

        Args:
            keep: Number of most recent better-dnf snapshots to keep

        Returns:
            Tuple of (number deleted, message - empty when nothing was done)
        """
        try:
            keep = max(int(keep), 1)
        except (TypeError, ValueError):
            keep = cls.DEFAULT_RETENTION

        use_snapper, snapshots = cls._load_snapshots()
        managed = [s for s in snapshots if cls._is_managed_snapshot(s)]
        if len(managed) <= keep:
            return (0, "")

        managed.sort(key=cls._snapshot_sort_key)
        stale = managed[: len(managed) - keep]
        stale_ids = {str(s.get("id", "")) for s in stale}

        if use_snapper:
            # A pre snapshot can only be deleted together with its post
            # pair. The post is newer, so it is normally already stale - this
            # covers the remaining edge cases.
            for snap in snapshots:
                if snap.get("type") != "post":
                    continue
                snap_id = str(snap.get("id", ""))
                if snap_id in stale_ids:
                    continue
                if str(snap.get("pre_num", "")).strip() in stale_ids:
                    stale.append(snap)
                    stale_ids.add(snap_id)

        deleted, error = cls._delete_snapshots(stale, use_snapper)
        if deleted == 0:
            return (0, f"Snapshot cleanup failed: {error}" if error else "")

        message = (
            f"Auto-cleanup: deleted {deleted} old snapshot(s), "
            f"keeping the latest {keep}."
        )
        if error:
            message += f" Some could not be deleted: {error}"
        return (deleted, message)

    @classmethod
    def _get_default_subvolume_id(cls) -> str | None:
        """Detect the default btrfs subvolume ID (the "ambit").

        Returns:
            The subvolume ID as a string, or None if detection fails.
        """
        try:
            result = run_sudo(
                ["btrfs", "subvolume", "get-default", "/"],
                timeout=10,
            )
            if result.returncode == 0:
                # Output looks like: "ID 5 (root)" or "ID 257 gen 12 top level 5 path @"
                match = re.search(r"ID\s+(\d+)", result.stdout)
                if match:
                    return match.group(1)
        except Exception:  # noqa: BLE001, S110 - best-effort detection
            pass
        return None

    @classmethod
    def rollback_snapshot(cls, snapshot_id: str) -> tuple[bool, str]:
        """
        Rollback to a specific snapshot.

        Args:
            snapshot_id: ID of the snapshot to rollback to

        Returns:
            Tuple of (success, message)
        """
        # Verify snapshot exists first
        if cls.is_snapper_installed():
            snapshots = cls._list_snapper_snapshots()
        else:
            snapshots = cls._list_btrfs_snapshots()

        snapshot_exists = any(str(s.get("id", "")) == snapshot_id for s in snapshots)

        if not snapshot_exists:
            return (False, f"Snapshot {snapshot_id} not found")

        # Confirm with user
        console.print(
            Panel(
                "[yellow]⚠️  WARNING: This will rollback your system to the selected snapshot.[/yellow]\n"
                "[red]All changes made after the snapshot will be lost![/red]",
                title="Rollback Confirmation",
                border_style="red",
            )
        )

        from questionary import confirm

        if not confirm("Are you sure you want to rollback?", default=False).ask():
            return (False, "Rollback cancelled by user")

        if cls.is_snapper_installed():
            return cls._rollback_snapper(snapshot_id)

        return cls._rollback_btrfs(snapshot_id)

    @classmethod
    def _rollback_snapper(cls, snapshot_id: str) -> tuple[bool, str]:
        """Rollback using snapper."""
        try:
            cmd = ["snapper", "rollback", snapshot_id]

            # Snapper needs --ambit when the default subvolume is unknown.
            # Detect the current default subvolume and pass it explicitly.
            ambit = cls._get_default_subvolume_id()
            if ambit:
                cmd += ["--ambit", ambit]

            result = run_sudo(cmd, timeout=30)

            if result.returncode == 0:
                return (True, f"Successfully rolled back to snapshot {snapshot_id}")
            else:
                return (False, f"Rollback failed: {result.stderr}")
        except Exception as e:  # noqa: BLE001 - surface any failure to the user
            return (False, f"Error during rollback: {e!s}")

    @classmethod
    def _rollback_btrfs(cls, snapshot_id: str) -> tuple[bool, str]:
        """Rollback using btrfs."""
        try:
            snapshot_path = f"{cls.DEFAULT_SNAPSHOT_PATH}/{snapshot_id}"

            # This is a simplified rollback - actual btrfs rollback is more complex
            # and typically requires booting from a live USB
            result = run_sudo(
                [
                    "btrfs",
                    "subvolume",
                    "delete",
                    "/",
                    "&&",
                    "btrfs",
                    "subvolume",
                    "snapshot",
                    snapshot_path,
                    "/",
                ],
                timeout=60,
            )

            if result.returncode == 0:
                return (True, f"Successfully rolled back to snapshot {snapshot_id}")
            else:
                return (False, f"Rollback failed: {result.stderr}")
        except Exception as e:  # noqa: BLE001 - surface any failure to the user
            return (False, f"Error during rollback: {e!s}")

    @classmethod
    def display_snapshots(cls) -> None:
        """Display available snapshots in a formatted table."""
        snapshots = cls.list_snapshots()

        if not snapshots:
            console.print("[dim]No snapshots found.[/dim]")
            return

        table = Table(
            title="📸 Available Snapshots",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("ID", style="bold")
        table.add_column("Date")
        table.add_column("Description")
        table.add_column("Type")

        for snap in snapshots:
            table.add_row(
                str(snap.get("id", "")),
                str(snap.get("date", "")),
                str(snap.get("description", "")),
                str(snap.get("type", "")),
            )

        console.print(table)
