"""
Tests for the sudo module (credential handling without a terminal).
"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from better_dnf.sudo import (
    _MAX_PASSWORD_ATTEMPTS,
    ensure_sudo_credentials,
    run_sudo,
)


@pytest.fixture(autouse=True)
def _silence_console(capsys):
    """Silence console.print output during tests."""
    with patch("better_dnf.sudo.console.print"):
        yield


def _mock_run(returncode, stdout="", stderr=""):
    """Create a CompletedProcess-like mock."""
    return Mock(returncode=returncode, stdout=stdout, stderr=stderr)


class TestEnsureSudoCredentials:
    """Tests for ensure_sudo_credentials()."""

    def test_cached_credentials_no_password_needed(self):
        """sudo -n -v succeeds -> already authenticated, no prompt."""
        with patch(
            "better_dnf.sudo.subprocess.run",
            return_value=_mock_run(0),
        ) as mock_run:
            ok, pwd = ensure_sudo_credentials()

        assert ok is True
        assert pwd is None
        # Credentials are checked with 'sudo -n -v', which runs nothing
        probe_cmd = mock_run.call_args.args[0]
        assert probe_cmd == ["sudo", "-n", "-v"]

    def test_probe_never_runs_effectful_command(self):
        """The target command is never executed as an authentication probe.

        Probing with the real command would apply its side effects twice
        (e.g. creating a snapshot, or running dnf upgrade).
        """
        calls = []

        def fake_run(cmd, *args, **kwargs):
            calls.append(cmd)
            if "-n" in cmd:
                return _mock_run(1, stderr="sudo: a password is required")
            return _mock_run(0)

        shared = Mock()
        shared.ask.return_value = "secret"

        with (
            patch("better_dnf.sudo.subprocess.run", side_effect=fake_run),
            patch("questionary.password", return_value=shared),
        ):
            ok, pwd = ensure_sudo_credentials(
                probe_args=["snapper", "create", "-t", "post"]
            )

        assert ok is True
        assert pwd == "secret"
        # Only '-v' (cached check) and '-S -v' (validation) ran - never the
        # actual snapper create command.
        assert ["sudo", "-n", "snapper", "create", "-t", "post"] not in calls
        assert ["sudo", "snapper", "create", "-t", "post"] not in calls

    def test_root_no_sudo_needed(self):
        """Running as root skips all sudo checks."""
        with (
            patch("better_dnf.sudo.os.geteuid", return_value=0),
            patch("better_dnf.sudo.subprocess.run") as mock_run,
        ):
            ok, pwd = ensure_sudo_credentials()

        assert ok is True
        assert pwd is None
        mock_run.assert_not_called()

    def test_password_accepted_after_retries(self):
        """Wrong password repeatedly, correct on the last allowed attempt."""

        def fake_run(cmd, *args, **kwargs):
            if "-n" in cmd:
                return _mock_run(1)  # not cached -> prompt
            pwd = (kwargs.get("input") or "").strip()
            return _mock_run(0 if pwd == "good" else 1)

        wrong = [f"bad{i}" for i in range(_MAX_PASSWORD_ATTEMPTS - 1)]
        shared = Mock()
        shared.ask.side_effect = wrong + ["good"]

        with (
            patch("better_dnf.sudo.subprocess.run", side_effect=fake_run),
            patch("questionary.password", return_value=shared),
        ):
            ok, pwd = ensure_sudo_credentials()

        assert ok is True
        assert pwd == "good"
        assert shared.ask.call_count == _MAX_PASSWORD_ATTEMPTS

    def test_max_attempts_fails_gracefully(self):
        """All wrong passwords -> auth fails after max attempts."""

        def fake_run(cmd, *args, **kwargs):
            if "-n" in cmd:
                return _mock_run(1)
            return _mock_run(1)  # always wrong

        shared = Mock()
        shared.ask.side_effect = ["x"] * _MAX_PASSWORD_ATTEMPTS

        with (
            patch("better_dnf.sudo.subprocess.run", side_effect=fake_run),
            patch("questionary.password", return_value=shared),
        ):
            ok, pwd = ensure_sudo_credentials()

        assert ok is False
        assert pwd is None
        assert shared.ask.call_count == _MAX_PASSWORD_ATTEMPTS

    def test_cancel_prompt(self):
        """User cancels the password prompt -> clean abort."""

        def fake_run(cmd, *args, **kwargs):
            if "-n" in cmd:
                return _mock_run(1)
            return _mock_run(1)

        shared = Mock()
        shared.ask.return_value = None

        with (
            patch("better_dnf.sudo.subprocess.run", side_effect=fake_run),
            patch("questionary.password", return_value=shared),
        ):
            ok, pwd = ensure_sudo_credentials()

        assert ok is False
        assert pwd is None
        shared.ask.assert_called_once()

    def test_probe_timeout_falls_back_to_prompt(self):
        """If the probe times out, still attempt password authentication."""

        def fake_run(cmd, *args, **kwargs):
            if "-n" in cmd:
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)
            pwd = (kwargs.get("input") or "").strip()
            return _mock_run(0 if pwd == "secret" else 1)

        shared = Mock()
        shared.ask.return_value = "secret"

        with (
            patch("better_dnf.sudo.subprocess.run", side_effect=fake_run),
            patch("questionary.password", return_value=shared),
        ):
            ok, pwd = ensure_sudo_credentials()

        assert ok is True
        assert pwd == "secret"

    def test_validation_timeout_fails_gracefully(self):
        """If password validation times out, return failure."""

        def fake_run(cmd, *args, **kwargs):
            if "-n" in cmd:
                return _mock_run(1)
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

        shared = Mock()
        shared.ask.return_value = "secret"

        with (
            patch("better_dnf.sudo.subprocess.run", side_effect=fake_run),
            patch("questionary.password", return_value=shared),
        ):
            ok, pwd = ensure_sudo_credentials()

        assert ok is False
        assert pwd is None

    def test_sudo_not_installed(self):
        """FileNotFoundError while probing -> falls back to prompt."""

        def fake_run(cmd, *args, **kwargs):
            if "-n" in cmd:
                raise FileNotFoundError("sudo not found")
            return _mock_run(0)

        shared = Mock()
        shared.ask.return_value = "secret"

        with (
            patch("better_dnf.sudo.subprocess.run", side_effect=fake_run),
            patch("questionary.password", return_value=shared),
        ):
            ok, pwd = ensure_sudo_credentials()

        assert ok is True
        assert pwd == "secret"


class TestRunSudo:
    """Tests for run_sudo()."""

    def test_runs_plain_sudo_when_cached(self):
        """No password needed -> sudo without -S and no stdin input."""
        calls = []

        def fake_run(cmd, *args, **kwargs):
            calls.append((cmd, kwargs.get("input")))
            if "-n" in cmd:
                return _mock_run(0)  # cached
            return _mock_run(0, stdout="snapshots output")

        with patch("better_dnf.sudo.subprocess.run", side_effect=fake_run):
            result = run_sudo(["snapper", "list"], timeout=10)

        assert result.returncode == 0
        assert result.stdout == "snapshots output"
        actual = calls[-1][0]
        assert actual == ["sudo", "snapper", "list"]
        assert calls[-1][1] is None

    def test_uses_sudo_dash_s_and_feeds_password(self):
        """Password needed -> sudo -S with password via stdin."""
        calls = []

        def fake_run(cmd, *args, **kwargs):
            calls.append((cmd, kwargs.get("input")))
            if "-n" in cmd:
                # Not cached: both '-v' and the NOPASSWD probe report it
                return _mock_run(1, stderr="sudo: a password is required")
            if cmd == ["sudo", "-S", "-v"]:
                return _mock_run(0)  # validation OK
            return _mock_run(0, stdout="output")

        shared = Mock()
        shared.ask.return_value = "secret"

        with (
            patch("better_dnf.sudo.subprocess.run", side_effect=fake_run),
            patch("questionary.password", return_value=shared),
        ):
            result = run_sudo(["dnf", "upgrade", "-y", "kernel"], timeout=30)

        assert result.returncode == 0
        actual = calls[-1][0]
        assert actual == ["sudo", "-S", "dnf", "upgrade", "-y", "kernel"]
        assert calls[-1][1] == "secret\n"
        # The command was not executed as a probe first
        assert ["sudo", "-n", "dnf", "upgrade", "-y", "kernel"] not in calls

    def test_auth_failure_returns_negative_returncode(self):
        """Authentication failure -> returncode -1 with message."""

        def fake_run(cmd, *args, **kwargs):
            if "-n" in cmd:
                return _mock_run(1, stderr="sudo: a password is required")
            return _mock_run(1)  # validation fails

        shared = Mock()
        shared.ask.side_effect = ["bad", "bad", "bad"]

        with (
            patch("better_dnf.sudo.subprocess.run", side_effect=fake_run),
            patch("questionary.password", return_value=shared),
        ):
            result = run_sudo(["snapper", "list"])

        assert result.returncode == -1
        assert "cancelled" in result.stderr.lower()

    def test_nopasswd_probe_executes_command_once(self):
        """A per-command NOPASSWD rule runs the command exactly once.

        The probe executes the command and its result is reused, so the
        command is never run a second time.
        """
        calls = []

        def fake_run(cmd, *args, **kwargs):
            calls.append(cmd)
            if cmd == ["sudo", "-n", "-v"]:
                return _mock_run(1, stderr="sudo: a password is required")
            if cmd == ["sudo", "-n", "snapper", "list"]:
                return _mock_run(0, stdout="nopasswd output")
            return _mock_run(0)

        with patch("better_dnf.sudo.subprocess.run", side_effect=fake_run):
            result = run_sudo(["snapper", "list"])

        assert result.returncode == 0
        assert result.stdout == "nopasswd output"
        # The command ran once (as the probe) and was NOT re-run
        assert calls.count(["sudo", "-n", "snapper", "list"]) == 1
        assert calls.count(["sudo", "snapper", "list"]) == 0

    def test_sudo_missing_returns_clear_error(self):
        """sudo not installed -> returncode -1 with an explanatory message."""
        with patch(
            "better_dnf.sudo.subprocess.run",
            side_effect=FileNotFoundError("sudo not found"),
        ):
            result = run_sudo(["snapper", "list"])

        assert result.returncode == -1
        assert "sudo is not available" in result.stderr

    def test_passes_timeout_to_subprocess(self):
        """Timeout argument is forwarded to subprocess.run."""
        with patch(
            "better_dnf.sudo.subprocess.run",
            return_value=_mock_run(0),
        ) as mock_run:
            run_sudo(["snapper", "list"], timeout=42)

        # Last call (the actual command) should carry the timeout
        last_call = mock_run.call_args
        assert last_call.kwargs.get("timeout") == 42
