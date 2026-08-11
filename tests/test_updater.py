"""
Tests for the updater module (apply_updates flow).
"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from better_dnf.models import PackageUpdate, UpdatePlan
from better_dnf.updater import UpdateApplier


def _make_package(name="kernel", old="6.1.4", new="7.1.7"):
    """Create a simple PackageUpdate."""
    return PackageUpdate(
        name=name,
        arch="x86_64",
        old_version=old,
        new_version=new,
        repository="updates",
    )


def _make_plan(names=("kernel",)):
    """Create an UpdatePlan with one or more packages."""
    plan = UpdatePlan()
    for name in names:
        plan.add_package(_make_package(name=name))
    return plan


def _make_process(returncode=0, lines=(), raise_on_readline=None):
    """Create a fake Popen process object.

    stdout.readline yields the given lines then '' (end of stream).
    If raise_on_readline is set, readline raises it instead.
    """
    proc = Mock()
    proc.returncode = returncode
    proc.pid = 9999
    proc.poll.return_value = None  # still running
    proc.wait.return_value = returncode
    proc.stdout = Mock()
    if raise_on_readline is not None:
        proc.stdout.readline.side_effect = raise_on_readline
    else:
        proc.stdout.readline.side_effect = list(lines) + [""]
    proc.stdin = Mock()
    return proc


@pytest.fixture(autouse=True)
def _silence_console():
    """Silence console.print output during tests."""
    with patch("better_dnf.updater.console.print"):
        yield


@pytest.fixture
def mock_confirm_yes():
    """Final confirmation answers 'yes'."""
    with patch("questionary.confirm") as m:
        m.return_value.ask.return_value = True
        yield m


class TestApplyUpdatesEarlyReturns:
    """Tests for the early return paths."""

    def test_empty_plan_returns_no_packages(self):
        """No packages -> returns immediately, no sudo invoked."""
        plan = UpdatePlan()

        with patch("better_dnf.updater.ensure_sudo_credentials") as sudo:
            ok, msg = UpdateApplier.apply_updates(plan)

        assert ok is True
        assert "No packages" in msg
        sudo.assert_not_called()

    def test_auth_failure_cancels(self):
        """Sudo authentication failure -> cancelled, no snapshot/Popen."""
        plan = _make_plan()

        with (
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(False, None),
            ),
            patch("better_dnf.updater.SnapshotManager.create_snapshot") as snap,
            patch("better_dnf.updater.subprocess.Popen") as popen,
        ):
            ok, msg = UpdateApplier.apply_updates(plan)

        assert ok is False
        assert "cancelled" in msg
        snap.assert_not_called()
        popen.assert_not_called()

    def test_dry_run_builds_assumeno_command(self):
        """Dry run builds 'dnf upgrade --assumeno' and never touches sudo."""
        plan = _make_plan(names=("kernel", "firefox"))

        with (
            patch("better_dnf.updater.subprocess.Popen") as popen,
            patch("better_dnf.updater.ensure_sudo_credentials") as sudo,
        ):
            ok, msg = UpdateApplier.apply_updates(plan, dry_run=True)

        assert ok is True
        assert "Dry run" in msg
        popen.assert_not_called()
        sudo.assert_not_called()


class TestApplyUpdatesSudoFlow:
    """Tests for the Popen command construction and password feed."""

    def test_plain_sudo_when_no_password(self):
        """Cached credentials -> 'sudo dnf upgrade -y', no -S, no stdin."""
        plan = _make_plan()
        proc = _make_process(returncode=0, lines=["Complete!"])

        with (
            patch("better_dnf.updater.subprocess.Popen", return_value=proc) as popen,
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(True, None),
            ),
            patch("questionary.confirm") as confirm,
        ):
            confirm.return_value.ask.return_value = True
            ok, _msg = UpdateApplier.apply_updates(plan, create_snapshot=False)

        assert ok is True
        cmd = popen.call_args.args[0]
        assert cmd == ["sudo", "dnf", "upgrade", "-y", "kernel"]
        assert popen.call_args.kwargs["stdin"] is None
        proc.stdin.assert_not_called()

    def test_password_fed_via_stdin(self):
        """Password needed -> 'sudo -S dnf upgrade' with password via stdin."""
        plan = _make_plan()
        proc = _make_process(
            returncode=0,
            lines=["Downloading packages...", "Complete!"],
        )

        with (
            patch("better_dnf.updater.subprocess.Popen", return_value=proc) as popen,
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(True, "secret"),
            ),
            patch("questionary.confirm") as confirm,
        ):
            confirm.return_value.ask.return_value = True
            ok, _msg = UpdateApplier.apply_updates(plan, create_snapshot=False)

        assert ok is True
        cmd = popen.call_args.args[0]
        assert cmd == ["sudo", "-S", "dnf", "upgrade", "-y", "kernel"]
        assert popen.call_args.kwargs["stdin"] is subprocess.PIPE
        proc.stdin.write.assert_called_once_with("secret\n")
        proc.stdin.flush.assert_called_once()
        proc.stdin.close.assert_called_once()

    def test_confirmation_declined_cancels(self):
        """User declines the final confirmation -> cancelled, no Popen."""
        plan = _make_plan()

        with (
            patch("better_dnf.updater.subprocess.Popen") as popen,
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(True, None),
            ),
            patch("questionary.confirm") as confirm,
        ):
            confirm.return_value.ask.return_value = False
            ok, msg = UpdateApplier.apply_updates(plan, create_snapshot=False)

        assert ok is False
        assert "cancelled" in msg
        popen.assert_not_called()

    def test_sudo_password_prompt_filtered_from_output(self):
        """sudo's own '[sudo] password' prompt is not echoed to the user."""
        plan = _make_plan()
        proc = _make_process(
            returncode=0,
            lines=[
                "[sudo] password for rendi:",
                "Downloading packages...",
                "Complete!",
            ],
        )
        printed = []

        with (
            patch("better_dnf.updater.subprocess.Popen", return_value=proc),
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(True, "secret"),
            ),
            patch("questionary.confirm") as confirm,
        ):
            confirm.return_value.ask.return_value = True
            with patch(
                "better_dnf.updater.console.print",
                side_effect=printed.append,
            ):
                ok, _msg = UpdateApplier.apply_updates(plan, create_snapshot=False)

        assert ok is True
        printed_text = " ".join(str(p) for p in printed).lower()
        assert "[sudo] password" not in printed_text
        assert "downloading" in printed_text


class TestApplyUpdatesOutcome:
    """Tests for success/failure outcomes."""

    def test_successful_update(self):
        """returncode 0 -> updates applied successfully."""
        plan = _make_plan()
        proc = _make_process(returncode=0, lines=["Complete!"])

        with (
            patch("better_dnf.updater.subprocess.Popen", return_value=proc),
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(True, None),
            ),
            patch("questionary.confirm") as confirm,
        ):
            confirm.return_value.ask.return_value = True
            ok, msg = UpdateApplier.apply_updates(plan, create_snapshot=False)

        assert ok is True
        assert msg == "Updates applied successfully"

    def test_failed_update(self):
        """Non-zero returncode -> update failed."""
        plan = _make_plan()
        proc = _make_process(returncode=1, lines=["Error: something"])

        with (
            patch("better_dnf.updater.subprocess.Popen", return_value=proc),
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(True, None),
            ),
            patch("questionary.confirm") as confirm,
        ):
            confirm.return_value.ask.return_value = True
            ok, msg = UpdateApplier.apply_updates(plan, create_snapshot=False)

        assert ok is False
        assert msg == "Update failed"


class TestApplyUpdatesInterrupts:
    """Tests for Ctrl+C and timeout handling."""

    def test_keyboard_interrupt_kills_process_group(self):
        """Ctrl+C during output -> SIGTERM the process group, cancelled."""
        plan = _make_plan()
        proc = _make_process(raise_on_readline=KeyboardInterrupt)
        proc.poll.return_value = None  # still running

        with (
            patch("better_dnf.updater.subprocess.Popen", return_value=proc),
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(True, None),
            ),
            patch("questionary.confirm") as confirm,
        ):
            confirm.return_value.ask.return_value = True
            with (
                patch("better_dnf.updater.os.getpgid", return_value=555) as getpgid,
                patch("better_dnf.updater.os.killpg") as killpg,
            ):
                ok, msg = UpdateApplier.apply_updates(plan, create_snapshot=False)

        assert ok is False
        assert "cancelled" in msg
        getpgid.assert_called_once_with(proc.pid)
        killpg.assert_called_once()

    def test_timeout_expired_kills_process(self):
        """Timeout during output -> SIGKILL the process group, timed out."""
        plan = _make_plan()
        proc = _make_process(
            raise_on_readline=subprocess.TimeoutExpired(cmd="dnf", timeout=30)
        )

        with (
            patch("better_dnf.updater.subprocess.Popen", return_value=proc),
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(True, None),
            ),
            patch("questionary.confirm") as confirm,
        ):
            confirm.return_value.ask.return_value = True
            with (
                patch("better_dnf.updater.os.getpgid", return_value=555),
                patch("better_dnf.updater.os.killpg") as killpg,
            ):
                ok, msg = UpdateApplier.apply_updates(plan, create_snapshot=False)

        assert ok is False
        assert "timed out" in msg
        killpg.assert_called_once()


class TestApplyUpdatesSnapshots:
    """Tests for the pre/post snapshot flow."""

    def test_pre_and_post_snapshot_flow(self):
        """Snapshot created before, post-snapshot after a successful update."""
        plan = _make_plan()
        proc = _make_process(returncode=0, lines=["Complete!"])

        with (
            patch("better_dnf.updater.subprocess.Popen", return_value=proc),
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(True, None),
            ),
            patch("questionary.confirm") as confirm,
        ):
            confirm.return_value.ask.return_value = True
            with (
                patch(
                    "better_dnf.updater.SnapshotManager.create_snapshot",
                    return_value=(True, "42", "Snapshot created"),
                ) as snap,
                patch(
                    "better_dnf.updater.SnapshotManager.create_post_snapshot",
                    return_value=(True, "43", "Post created"),
                ) as post,
            ):
                ok, _msg = UpdateApplier.apply_updates(plan, create_snapshot=True)

        assert ok is True
        assert plan.snapshot_id == "42"
        snap.assert_called_once()
        post.assert_called_once()

    def test_snapshot_failure_continues_without_post(self):
        """Snapshot failure -> continue without snapshot, no post-snapshot."""
        plan = _make_plan()
        proc = _make_process(returncode=0, lines=["Complete!"])

        with (
            patch("better_dnf.updater.subprocess.Popen", return_value=proc),
            patch(
                "better_dnf.updater.ensure_sudo_credentials",
                return_value=(True, None),
            ),
            patch("questionary.confirm") as confirm,
        ):
            confirm.return_value.ask.return_value = True
            with (
                patch(
                    "better_dnf.updater.SnapshotManager.create_snapshot",
                    return_value=(False, None, "No btrfs root"),
                ),
                patch(
                    "better_dnf.updater.SnapshotManager.create_post_snapshot"
                ) as post,
            ):
                ok, _msg = UpdateApplier.apply_updates(plan, create_snapshot=True)

        assert ok is True
        assert plan.snapshot_id is None
        post.assert_not_called()


class TestRollbackUpdates:
    """Tests for rollback_updates()."""

    def test_no_snapshot_id(self):
        """No snapshot available -> error message."""
        plan = _make_plan()
        ok, msg = UpdateApplier.rollback_updates(plan)
        assert ok is False
        assert "No snapshot" in msg

    def test_rollback_delegates_to_snapshot_manager(self):
        """With a snapshot_id, delegates to SnapshotManager.rollback_snapshot."""
        plan = _make_plan()
        plan.snapshot_id = "42"

        with patch(
            "better_dnf.updater.SnapshotManager.rollback_snapshot",
            return_value=(True, "Rolled back"),
        ) as rollback:
            ok, msg = UpdateApplier.rollback_updates(plan)

        assert ok is True
        assert msg == "Rolled back"
        rollback.assert_called_once_with("42")
