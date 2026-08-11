"""
Module for applying selected package updates.
"""

from __future__ import annotations

import os
import subprocess

from rich import box
from rich.console import Console
from rich.table import Table

from .models import UpdatePlan
from .snapshot import SnapshotManager
from .sudo import ensure_sudo_credentials

console = Console()


class UpdateApplier:
    """Applies selected package updates using DNF."""

    @classmethod
    def apply_updates(
        cls,
        plan: UpdatePlan,
        create_snapshot: bool = True,
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """
        Apply the updates in the plan.

        Args:
            plan: UpdatePlan with packages to update
            create_snapshot: Whether to create a snapshot first
            dry_run: If True, only show what would be done

        Returns:
            Tuple of (success, message)
        """
        if not plan.packages:
            return (True, "No packages to update")

        # Ensure sudo is authenticated before any privileged operation.
        # Sudo normally needs a terminal to prompt for the password; since we
        # run with piped stdio (no TTY), a bare 'sudo dnf upgrade' fails with
        # "a terminal is required to read the password".  We pre-authenticate
        # here and keep the password to feed back via 'sudo -S' if needed.
        sudo_password: str | None = None
        if not dry_run:
            auth_ok, sudo_password = ensure_sudo_credentials(
                probe_args=["dnf", "upgrade"]
            )
            if not auth_ok:
                return (False, "Sudo authentication cancelled by user")

        # Create snapshot if requested
        if create_snapshot and not dry_run:
            console.print("\n[bold cyan]📸 Creating pre-update snapshot...[/bold cyan]")
            success, snapshot_id, message = SnapshotManager.create_snapshot(
                description=f"Before updating {len(plan.packages)} packages"
            )

            if success:
                plan.snapshot_id = snapshot_id
                console.print(f"[green]✓ {message}[/green]")
            else:
                console.print(f"[yellow]⚠️  {message}[/yellow]")
                console.print("[dim]Continuing without snapshot...[/dim]")

        # Get package names
        package_names = [pkg.name for pkg in plan.packages]

        # Build dnf command
        if dry_run:
            cmd = ["dnf", "upgrade", "--assumeno"] + package_names
            console.print(f"\n[bold]Dry run: {' '.join(cmd)}[/bold]")
        else:
            # Use -y flag to auto-confirm since we already confirmed with user.
            # When we have a password, use 'sudo -S' so sudo reads it from
            # stdin instead of requiring a terminal.
            cmd = (
                ["sudo"]
                + (["-S"] if sudo_password else [])
                + ["dnf", "upgrade", "-y"]
                + package_names
            )

        # Display what we're about to do
        cls._display_update_command(cmd, plan, dry_run)

        if dry_run:
            return (True, "Dry run completed")

        # Final confirmation before applying
        from questionary import confirm

        if not confirm(
            f"\nReady to apply {len(plan.packages)} updates?",
            default=False,
        ).ask():
            return (False, "Update cancelled by user")

        # Execute update
        console.print("\n[bold cyan]🚀 Applying Updates...[/bold cyan]")
        console.print(f"[dim]Running: {' '.join(cmd)}[/dim]\n")

        process = None
        try:
            import signal
            import sys

            # Run dnf update with real-time output
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if sudo_password else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,
                start_new_session=sys.platform != "win32",
            )

            # Feed the sudo password through stdin when needed
            if sudo_password:
                try:
                    process.stdin.write(sudo_password + "\n")
                    process.stdin.flush()
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

            # Read output in real-time
            for line in iter(process.stdout.readline, ""):
                if line:
                    line = line.rstrip()
                    # Filter out sudo's own password prompt (we already asked)
                    lowered = line.lower()
                    if "[sudo] password" in lowered or lowered.startswith("password:"):
                        continue
                    # Show progress for important lines
                    if (
                        "Downloading" in line
                        or "Installing" in line
                        or "Upgrading" in line
                    ):
                        console.print(f"  [cyan]→[/cyan] {line}")
                    elif "Complete" in line or "Done" in line:
                        console.print(f"  [green]✓[/green] {line}")
                    elif "Error" in line or "Failed" in line:
                        console.print(f"  [red]✗[/red] {line}")
                    elif line.strip():  # Show other non-empty lines
                        console.print(f"  [dim]{line}[/dim]")

            # Wait for process to complete
            process.wait()

            if process.returncode == 0:
                console.print(
                    "\n[bold green]✓ Updates applied successfully![/bold green]"
                )

                # Create post-update snapshot if pre-snapshot was created
                if create_snapshot and plan.snapshot_id:
                    console.print(
                        "\n[bold cyan]📸 Creating post-update snapshot...[/bold cyan]"
                    )
                    post_success, _post_id, post_message = (
                        SnapshotManager.create_post_snapshot(
                            description=f"After updating {len(plan.packages)} packages"
                        )
                    )
                    if post_success:
                        console.print(f"[green]✓ {post_message}[/green]")
                    else:
                        console.print(f"[yellow]⚠️  {post_message}[/yellow]")

                return (True, "Updates applied successfully")
            else:
                console.print("\n[bold red]✗ Update failed[/bold red]")
                return (False, "Update failed")

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            if process and process.poll() is None:
                # Process is still running, kill it
                try:
                    import signal

                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=5)
                except Exception:  # noqa: BLE001 - best-effort cleanup on interrupt
                    # Force kill if SIGTERM doesn't work
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except Exception:  # noqa: BLE001, S110 - best-effort cleanup
                        pass
            console.print("\n[yellow]⚠️  Update cancelled by user[/yellow]")
            return (False, "Update cancelled by user")
        except subprocess.TimeoutExpired:
            if process:
                try:
                    import signal

                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception:  # noqa: BLE001, S110 - best-effort cleanup
                    pass
            console.print("[red]✗ Update timed out[/red]")
            return (False, "Update operation timed out")
        except Exception as e:  # noqa: BLE001 - surface any update failure to the user
            if process and process.poll() is None:
                try:
                    import signal

                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except Exception:  # noqa: BLE001, S110 - best-effort cleanup
                    pass
            console.print(f"[red]✗ Error: {e!s}[/red]")
            return (False, f"Error during update: {e!s}")

    @classmethod
    def _display_update_command(
        cls,
        cmd: list[str],
        plan: UpdatePlan,
        dry_run: bool,
    ) -> None:
        """Display the update command and plan details."""
        table = Table(
            title="📦 Update Plan" + (" (Dry Run)" if dry_run else ""),
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Package", style="bold")
        table.add_column("Version Change", justify="right")

        for pkg in plan.packages[:20]:  # Show first 20
            table.add_row(
                pkg.name,
                f"{pkg.old_version} → {pkg.new_version}",
            )

        if len(plan.packages) > 20:
            table.add_row(
                f"[dim]... and {len(plan.packages) - 20} more packages[/dim]",
                "",
            )

        console.print(table)

        # Show command
        console.print(f"\n[bold]Command:[/bold] {' '.join(cmd)}")

    @classmethod
    def rollback_updates(cls, plan: UpdatePlan) -> tuple[bool, str]:
        """
        Rollback updates using the snapshot.

        Args:
            plan: UpdatePlan with snapshot information

        Returns:
            Tuple of (success, message)
        """
        if not plan.snapshot_id:
            return (False, "No snapshot available for rollback")

        return SnapshotManager.rollback_snapshot(plan.snapshot_id)

    @classmethod
    def check_update_status(cls) -> tuple[bool, str]:
        """
        Check the status of any ongoing DNF operations.

        Returns:
            Tuple of (success, message)
        """
        try:
            from .sudo import run_sudo

            result = run_sudo(
                ["dnf", "history", "list", "--limit", "1"],
                timeout=10,
            )

            if result.returncode == 0:
                return (True, result.stdout)
            else:
                return (False, "Unable to check update status")

        except Exception as e:  # noqa: BLE001 - surface any status check failure
            return (False, f"Error checking status: {e!s}")

    @classmethod
    def get_update_history(cls, limit: int = 5) -> list[dict]:
        """
        Get recent DNF update history.

        Args:
            limit: Number of recent transactions to retrieve

        Returns:
            List of transaction dictionaries
        """
        try:
            from .sudo import run_sudo

            result = run_sudo(
                ["dnf", "history", "list", f"--limit={limit}", "--reverse"],
                timeout=10,
            )

            if result.returncode == 0:
                transactions = []
                for line in result.stdout.strip().split("\n")[1:]:  # Skip header
                    if line.strip():
                        parts = line.split("|")
                        if len(parts) >= 4:
                            transactions.append(
                                {
                                    "id": parts[0].strip(),
                                    "date": parts[1].strip(),
                                    "action": parts[2].strip(),
                                    "packages": parts[3].strip(),
                                }
                            )
                return transactions
            else:
                return []

        except Exception:  # noqa: BLE001 - best-effort history; return empty on failure
            return []
