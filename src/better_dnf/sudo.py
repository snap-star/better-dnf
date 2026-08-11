"""
Shared helpers for running sudo commands without an interactive terminal.

Sudo normally needs a terminal to prompt for the password.  Since better-dnf
runs its commands with piped stdio (no TTY), a bare 'sudo ...' fails with
"a terminal is required to read the password".  These helpers pre-authenticate
with a masked password prompt and feed the password back via stdin using
'sudo -S', so no terminal is ever required.
"""

from __future__ import annotations

import os
import subprocess

from rich.console import Console

console = Console()

# Number of attempts allowed for the sudo password prompt
_MAX_PASSWORD_ATTEMPTS = 3


def ensure_sudo_credentials(
    probe_args: list[str] | None = None,
) -> tuple[bool, str | None]:
    """
    Ensure sudo can run without requiring an interactive terminal.

    Strategy:
      1. If already root, no sudo is needed.
      2. Probe whether the specific command is already permitted without a
         password (via 'sudo -n <command>').  This respects per-command
         NOPASSWD rules (e.g. Fedora ships a NOPASSWD rule for snapper),
         so commands that never need a password don't trigger a prompt.
      3. Otherwise, prompt for the password and validate it with
         'sudo -S true' (which also caches the credentials).

    Args:
        probe_args: The command that will actually be run (e.g. ["snapper",
            "list"]).  When None, probes 'sudo -n true'.

    Returns:
        Tuple of (success, password_or_none):
        - password is returned when the caller should use 'sudo -S'
          and feed it via stdin
        - None password means sudo is already authenticated or not needed
    """
    # Already running as root: no sudo needed
    try:
        if os.geteuid() == 0:
            return (True, None)
    except AttributeError:
        pass

    # Check if this specific command can run without a password
    # (covers cached credentials AND per-command NOPASSWD rules)
    probe_cmd = ["sudo", "-n"] + (probe_args or ["true"])
    try:
        check = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,  # We inspect returncode manually
        )
        if check.returncode == 0:
            return (True, None)  # Already authenticated / NOPASSWD
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Prompt for the password (masked input) with retries
    from questionary import password

    console.print("[yellow]🔑 Sudo authentication required.[/yellow]")
    for attempt in range(_MAX_PASSWORD_ATTEMPTS):
        pwd = password("Enter your sudo password:").ask()
        if pwd is None:
            return (False, None)  # Cancelled by user

        # Validate the password (this also caches the sudo timestamp)
        try:
            validate = subprocess.run(
                ["sudo", "-S", "true"],
                input=pwd + "\n",
                capture_output=True,
                text=True,
                timeout=10,
                check=False,  # We inspect returncode manually
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            console.print("[red]✗ Unable to validate sudo credentials.[/red]")
            return (False, None)

        if validate.returncode == 0:
            return (True, pwd)

        remaining = _MAX_PASSWORD_ATTEMPTS - attempt - 1
        if remaining > 0:
            console.print(
                f"[red]✗ Incorrect password. {remaining} attempt(s) left.[/red]"
            )
        else:
            console.print("[red]✗ Too many incorrect password attempts.[/red]")

    return (False, None)


def run_sudo(
    args: list[str],
    timeout: float | None = None,
    text: bool = True,
) -> subprocess.CompletedProcess:
    """
    Run a command with sudo, handling password authentication without a TTY.

    Args:
        args: Command to run after 'sudo' (e.g. ["snapper", "list"]).
        timeout: Optional timeout in seconds.
        text: Whether to decode output as text.

    Returns:
        CompletedProcess.  On authentication failure, returncode is -1 and
        stderr explains why.
    """
    auth_ok, sudo_password = ensure_sudo_credentials(probe_args=args)
    if not auth_ok:
        return subprocess.CompletedProcess(
            args=["sudo"] + args,
            returncode=-1,
            stdout="",
            stderr="Sudo authentication cancelled by user",
        )

    cmd = ["sudo"] + (["-S"] if sudo_password else []) + args
    return subprocess.run(
        cmd,
        input=(sudo_password + "\n") if sudo_password else None,
        capture_output=True,
        text=text,
        timeout=timeout,
        check=False,  # We inspect returncode manually
    )
