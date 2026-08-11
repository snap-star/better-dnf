"""
Shared helpers for running sudo commands without an interactive terminal.

Sudo normally needs a terminal to prompt for the password.  Since better-dnf
runs its commands with piped stdio (no TTY), a bare 'sudo ...' fails with
"a terminal is required to read the password".  These helpers pre-authenticate
with a masked password prompt and feed the password back via stdin using
'sudo -S', so no terminal is ever required.

Authentication checks never execute the caller's command: running an
effectful command (e.g. 'snapper create' or 'dnf upgrade') as a probe would
apply its side effects twice.  We check cached credentials with
'sudo -n -v' (which runs nothing) and only probe a specific command inside
run_sudo(), where the probe result is reused as the command result so the
command is never executed more than once.
"""

from __future__ import annotations

import os
import subprocess

from rich.console import Console

console = Console()

# Number of attempts allowed for the sudo password prompt
_MAX_PASSWORD_ATTEMPTS = 3

# stderr markers sudo prints when credentials are required/incorrect
_AUTH_FAILURE_MARKERS = ("a password is required", "no password was provided")


def _is_root() -> bool:
    """Return True when running with euid 0 (no sudo needed)."""
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _looks_like_auth_failure(result: subprocess.CompletedProcess) -> bool:
    """True when a 'sudo -n <cmd>' probe failed because sudo wanted a password.

    sudo prints its own authentication error (not the command's output) when
    credentials are missing or expired.  Distinguishing the two means a real
    command failure is surfaced as-is instead of being mistaken for a login
    prompt (and vice versa).
    """
    stderr = (result.stderr or "").lower()
    return any(marker in stderr for marker in _AUTH_FAILURE_MARKERS)


def ensure_sudo_credentials(
    probe_args: list[str] | None = None,
) -> tuple[bool, str | None]:
    """
    Ensure sudo can run without requiring an interactive terminal.

    Strategy:
      1. If already root, no sudo is needed.
      2. Probe 'sudo -n -v' to check whether credentials are already cached.
         Unlike probing the target command, 'sudo -v' runs nothing, so
         effectful commands (snapper create, dnf upgrade) are never executed
         as a side effect of authentication checks.
      3. Otherwise, prompt for the password and validate it with
         'sudo -S -v' (which also caches the credentials).

    Args:
        probe_args: Retained for API compatibility.  Per-command NOPASSWD
            handling lives in run_sudo(), where the probe result can be
            reused safely instead of executing the command twice.

    Returns:
        Tuple of (success, password_or_none):
        - password is returned when the caller should use 'sudo -S'
          and feed it via stdin
        - None password means sudo is already authenticated or not needed
    """
    # Already running as root: no sudo needed
    if _is_root():
        return (True, None)

    # Check whether credentials are cached (no side effects)
    try:
        check = subprocess.run(
            ["sudo", "-n", "-v"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,  # We inspect returncode manually
        )
        if check.returncode == 0:
            return (True, None)  # Already authenticated
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Prompt for the password (masked input) with retries
    from questionary import password

    console.print("[yellow]🔑 Sudo authentication required.[/yellow]")
    for attempt in range(_MAX_PASSWORD_ATTEMPTS):
        pwd = password("Enter your sudo password:").ask()
        if pwd is None:
            return (False, None)  # Cancelled by user

        # Validate the password with 'sudo -S -v': validates and caches the
        # sudo timestamp but does not run any command.
        try:
            validate = subprocess.run(
                ["sudo", "-S", "-v"],
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

    The command is never executed more than once:
      1. If credentials are already cached ('sudo -n -v' succeeds, running
         nothing), the command is run with plain 'sudo'.
      2. Otherwise, for a per-command NOPASSWD rule the probe 'sudo -n <cmd>'
         executes the command once, and that probe result IS the result --
         the command is not run a second time.
      3. Otherwise the user is prompted for the password (validated with
         'sudo -S -v') and the command is run once via 'sudo -S'.

    Args:
        args: Command to run after 'sudo' (e.g. ["snapper", "list"]).
        timeout: Optional timeout in seconds.
        text: Whether to decode output as text.

    Returns:
        CompletedProcess.  On authentication failure, returncode is -1 and
        stderr explains why.
    """
    # Root needs no sudo at all
    if _is_root():
        return subprocess.run(
            args,
            capture_output=True,
            text=text,
            timeout=timeout,
            check=False,  # We inspect returncode manually
        )

    # 1) Cached credentials?  'sudo -n -v' runs nothing.
    try:
        cached = subprocess.run(
            ["sudo", "-n", "-v"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,  # We inspect returncode manually
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=["sudo"] + args,
            returncode=-1,
            stdout="",
            stderr="sudo is not available",
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=["sudo"] + args,
            returncode=-1,
            stdout="",
            stderr="sudo credential check timed out",
        )
    if cached.returncode == 0:
        return subprocess.run(
            ["sudo"] + args,
            capture_output=True,
            text=text,
            timeout=timeout,
            check=False,  # We inspect returncode manually
        )

    # 2) Per-command NOPASSWD rule (e.g. Fedora's snapper rule)?  The probe
    #    executes the command once; when sudo was authorized we reuse that
    #    result so nothing runs a second time.
    try:
        probe = subprocess.run(
            ["sudo", "-n"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # We inspect returncode manually
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=["sudo"] + args,
            returncode=-1,
            stdout="",
            stderr="sudo is not available",
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=["sudo"] + args,
            returncode=-1,
            stdout="",
            stderr="sudo credential check timed out",
        )
    if not _looks_like_auth_failure(probe):
        return probe

    # 3) Password needed: prompt (validated with 'sudo -S -v'), then run once.
    auth_ok, sudo_password = ensure_sudo_credentials(probe_args=args)
    if not auth_ok:
        return subprocess.CompletedProcess(
            args=["sudo"] + args,
            returncode=-1,
            stdout="",
            stderr="Sudo authentication cancelled by user",
        )

    return subprocess.run(
        ["sudo", "-S"] + args,
        input=(sudo_password + "\n") if sudo_password else None,
        capture_output=True,
        text=text,
        timeout=timeout,
        check=False,  # We inspect returncode manually
    )
