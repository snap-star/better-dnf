"""
Btrfs snapshot management for safe system updates.
"""

from __future__ import annotations

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
        snapshot_type: str = "single",
    ) -> tuple[bool, str | None, str]:
        """
        Create a btrfs snapshot before applying updates.

        Args:
            description: Optional description for the snapshot
            snapshot_type: Type of snapshot ('single' or 'pre/post')

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
            return cls._create_snapper_snapshot(snapshot_name, description, "pre")

        # Fallback to btrfs subvolume snapshot
        return cls._create_btrfs_snapshot(snapshot_name, description)

    @classmethod
    def create_post_snapshot(
        cls,
        description: str | None = None,
    ) -> tuple[bool, str | None, str]:
        """
        Create a post-update snapshot (completes the pre/post pair).

        Args:
            description: Optional description for the snapshot

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
            return cls._create_snapper_snapshot(snapshot_name, description, "post")

        # Fallback to btrfs subvolume snapshot
        return cls._create_btrfs_snapshot(snapshot_name, description)

    @classmethod
    def _create_snapper_snapshot(
        cls,
        snapshot_name: str,
        description: str | None,
        snapshot_type: str = "pre",
    ) -> tuple[bool, str | None, str]:
        """
        Create snapshot using snapper.

        Args:
            snapshot_name: Name for the snapshot
            description: Optional description
            snapshot_type: Type of snapshot ('pre' or 'post')

        Returns:
            Tuple of (success, snapshot_id, message)
        """
        try:
            # Create snapshot with specified type
            result = run_sudo(
                [
                    "snapper",
                    "create",
                    "-d",
                    description or snapshot_name,
                    "-t",
                    snapshot_type,
                ],
                timeout=30,
            )

            if result.returncode == 0:
                # Get the snapshot number
                list_result = run_sudo(
                    [
                        "snapper",
                        "list",
                        "--columns",
                        "number",
                        "--columns",
                        "description",
                        "--csvout",
                    ],
                    timeout=10,
                )

                # Extract the latest snapshot number
                if list_result.returncode == 0:
                    lines = list_result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        latest = lines[-1].split(",")[0]
                        return (
                            True,
                            latest,
                            f"Snapshot created successfully: {latest}",
                        )

                return (True, None, "Snapshot created successfully")
            else:
                return (False, None, f"Failed to create snapshot: {result.stderr}")

        except subprocess.TimeoutExpired:
            return (False, None, "Snapshot creation timed out")
        except Exception as e:  # noqa: BLE001 - surface any failure to the user
            return (False, None, f"Error creating snapshot: {e!s}")

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
        snapshots = []
        try:
            # Try with --csvout first
            result = run_sudo(
                ["snapper", "list", "--csvout"],
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                # Parse CSV output
                for i, line in enumerate(lines):
                    if i == 0:  # Skip header
                        continue
                    # Split by comma but handle quoted fields
                    parts = line.split(",")
                    if len(parts) >= 4:
                        # Clean up each part
                        snapshot_id = parts[0].strip().strip('"')
                        # Skip if it's not a valid ID (like the header)
                        if not snapshot_id.isdigit():
                            continue
                        snapshots.append(
                            {
                                "id": snapshot_id,
                                "date": parts[1].strip().strip('"'),
                                "description": parts[2].strip().strip('"'),
                                "type": parts[3].strip().strip('"'),
                            }
                        )
            else:
                # If CSV fails, try plain output
                result2 = run_sudo(
                    ["snapper", "list"],
                    timeout=10,
                )
                if result2.returncode == 0 and result2.stdout.strip():
                    lines = result2.stdout.strip().split("\n")
                    for line in lines:
                        # Skip empty lines and separator lines
                        if not line.strip() or line.startswith(("-", "│")):
                            continue
                        # Try to parse line with │ separators
                        if "│" in line:
                            parts = [p.strip() for p in line.split("│") if p.strip()]
                            if len(parts) >= 4:
                                snapshot_id = parts[0]
                                if snapshot_id.isdigit():
                                    snapshots.append(
                                        {
                                            "id": snapshot_id,
                                            "date": parts[1] if len(parts) > 1 else "",
                                            "description": (
                                                parts[2] if len(parts) > 2 else ""
                                            ),
                                            "type": parts[3] if len(parts) > 3 else "",
                                        }
                                    )
                        else:
                            # Try space-separated format
                            parts = line.split()
                            if len(parts) >= 4:
                                snapshot_id = parts[0]
                                if snapshot_id.isdigit():
                                    snapshots.append(
                                        {
                                            "id": snapshot_id,
                                            "date": parts[1] if len(parts) > 1 else "",
                                            "description": (
                                                " ".join(parts[2:-1])
                                                if len(parts) > 2
                                                else ""
                                            ),
                                            "type": parts[-1] if len(parts) > 1 else "",
                                        }
                                    )
        except Exception:  # noqa: BLE001, S110
            pass

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
            result = run_sudo(
                ["snapper", "rollback", snapshot_id],
                timeout=30,
            )

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
