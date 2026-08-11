"""
Tests for the snapshot module (create/list/rollback flow).
"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from better_dnf.snapshot import SnapshotManager


def _cp(returncode=0, stdout="", stderr=""):
    """Build a CompletedProcess-like mock."""
    return Mock(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


@pytest.fixture(autouse=True)
def _silence_console():
    """Silence console.print output during tests."""
    with patch("better_dnf.snapshot.console.print"):
        yield


class TestDetection:
    """Tests for filesystem/snapper detection."""

    def test_is_btrfs_root_true(self):
        with patch(
            "better_dnf.snapshot.subprocess.run",
            return_value=_cp(0, stdout="btrfs\n"),
        ):
            assert SnapshotManager.is_btrfs_root() is True

    def test_is_btrfs_root_false(self):
        with patch(
            "better_dnf.snapshot.subprocess.run",
            return_value=_cp(0, stdout="ext4\n"),
        ):
            assert SnapshotManager.is_btrfs_root() is False

    def test_is_btrfs_root_timeout(self):
        with patch(
            "better_dnf.snapshot.subprocess.run",
            side_effect=subprocess.TimeoutExpired("findmnt", 10),
        ):
            assert SnapshotManager.is_btrfs_root() is False

    def test_is_snapper_installed_true(self):
        with patch(
            "better_dnf.snapshot.subprocess.run",
            return_value=_cp(0),
        ):
            assert SnapshotManager.is_snapper_installed() is True

    def test_is_snapper_installed_false(self):
        with patch(
            "better_dnf.snapshot.subprocess.run",
            return_value=_cp(1),
        ):
            assert SnapshotManager.is_snapper_installed() is False


class TestCreateSnapshot:
    """Tests for create_snapshot dispatch."""

    def test_non_btrfs_returns_failure(self):
        with patch.object(SnapshotManager, "is_btrfs_root", return_value=False):
            ok, snap_id, msg = SnapshotManager.create_snapshot()

        assert ok is False
        assert snap_id is None
        assert "not btrfs" in msg

    def test_uses_snapper_when_available(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_create_snapper_snapshot",
                return_value=(True, "42", "ok"),
            ) as mock_snapper,
        ):
            ok, snap_id, _msg = SnapshotManager.create_snapshot()

        assert ok is True
        assert snap_id == "42"
        # create_snapshot creates a 'pre' snapshot by default
        args = mock_snapper.call_args.args
        assert args[2] == "pre"

    def test_falls_back_to_btrfs(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=False),
            patch.object(
                SnapshotManager,
                "_create_btrfs_snapshot",
                return_value=(True, "snap", "ok"),
            ) as mock_btrfs,
        ):
            ok, snap_id, _msg = SnapshotManager.create_snapshot()

        assert ok is True
        assert snap_id == "snap"
        mock_btrfs.assert_called_once()

    def test_description_appended_to_name(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_create_snapper_snapshot",
                return_value=(True, "42", "ok"),
            ) as mock_snapper,
        ):
            SnapshotManager.create_snapshot(description="before updates")

        snapshot_name = mock_snapper.call_args.args[0]
        assert snapshot_name.startswith("better-dnf-")
        assert "before-updates" in snapshot_name


class TestCreatePostSnapshot:
    """Tests for create_post_snapshot."""

    def test_uses_pre_type_and_post_prefix(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_create_snapper_snapshot",
                return_value=(True, "43", "ok"),
            ) as mock_snapper,
        ):
            ok, snap_id, _msg = SnapshotManager.create_post_snapshot()

        assert ok is True
        assert snap_id == "43"
        snapshot_name, _, snapshot_type = mock_snapper.call_args.args
        assert snapshot_type == "post"
        assert "-post-" in snapshot_name

    def test_non_btrfs_returns_failure(self):
        with patch.object(SnapshotManager, "is_btrfs_root", return_value=False):
            ok, _snap_id, msg = SnapshotManager.create_post_snapshot()

        assert ok is False
        assert "not btrfs" in msg


class TestCreateSnapperSnapshot:
    """Tests for the snapper-backed creation."""

    def test_success_extracts_latest_id(self):
        # First call: snapper create succeeds. Second call: snapper list
        # returns the CSV from which the latest snapshot number is extracted.
        calls = [
            _cp(0, stdout=""),
            _cp(
                0,
                stdout=(
                    "Number,Date,Description,Type\n"
                    "0,date,current,single\n"
                    "42,date,my-snap,single\n"
                ),
            ),
        ]

        def fake_run_sudo(cmd, **kwargs):
            return calls.pop(0)

        with patch("better_dnf.snapshot.run_sudo", side_effect=fake_run_sudo):
            ok, snap_id, msg = SnapshotManager._create_snapper_snapshot(
                "better-dnf-20260811", None, "pre"
            )

        assert ok is True
        assert snap_id == "42"
        assert "42" in msg

    def test_success_without_list_output(self):
        calls = [_cp(0), _cp(0, stdout="")]

        with patch(
            "better_dnf.snapshot.run_sudo", side_effect=lambda *a, **k: calls.pop(0)
        ):
            ok, snap_id, msg = SnapshotManager._create_snapper_snapshot(
                "better-dnf-20260811", None, "pre"
            )

        assert ok is True
        assert snap_id is None
        assert "Snapshot created successfully" in msg

    def test_failure_returns_error(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            return_value=_cp(1, stderr="permission denied"),
        ):
            ok, _snap_id, msg = SnapshotManager._create_snapper_snapshot(
                "better-dnf-20260811", None, "pre"
            )

        assert ok is False
        assert "permission denied" in msg

    def test_timeout_returns_timed_out(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            side_effect=subprocess.TimeoutExpired("snapper", 30),
        ):
            ok, _snap_id, msg = SnapshotManager._create_snapper_snapshot(
                "better-dnf-20260811", None, "pre"
            )

        assert ok is False
        assert "timed out" in msg


class TestCreateBtrfsSnapshot:
    """Tests for the btrfs-backed creation."""

    def test_success(self):
        def fake_run_sudo(cmd, **kwargs):
            if "subvolume" in cmd and "show" in cmd:
                return _cp(0)
            if "mkdir" in cmd:
                return _cp(0)
            return _cp(0)

        with patch("better_dnf.snapshot.run_sudo", side_effect=fake_run_sudo):
            ok, snap_id, msg = SnapshotManager._create_btrfs_snapshot(
                "better-dnf-20260811", None
            )

        assert ok is True
        assert snap_id == "better-dnf-20260811"
        assert "Read-only snapshot created" in msg

    def test_subvolume_show_failure(self):
        def fake_run_sudo(cmd, **kwargs):
            if "show" in cmd:
                return _cp(1)
            return _cp(0)

        with patch("better_dnf.snapshot.run_sudo", side_effect=fake_run_sudo):
            ok, _snap_id, msg = SnapshotManager._create_btrfs_snapshot(
                "better-dnf-20260811", None
            )

        assert ok is False
        assert "Failed to get root subvolume" in msg

    def test_snapshot_failure(self):
        def fake_run_sudo(cmd, **kwargs):
            if "snapshot" in cmd and "show" not in cmd:
                return _cp(1, stderr="device busy")
            return _cp(0)

        with patch("better_dnf.snapshot.run_sudo", side_effect=fake_run_sudo):
            ok, _snap_id, msg = SnapshotManager._create_btrfs_snapshot(
                "better-dnf-20260811", None
            )

        assert ok is False
        assert "device busy" in msg

    def test_timeout_returns_timed_out(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            side_effect=subprocess.TimeoutExpired("btrfs", 60),
        ):
            ok, _snap_id, msg = SnapshotManager._create_btrfs_snapshot(
                "better-dnf-20260811", None
            )

        assert ok is False
        assert "timed out" in msg


class TestListSnapshots:
    """Tests for listing snapshots."""

    def test_dispatch_to_snapper(self):
        with (
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_list_snapper_snapshots",
                return_value=[{"id": "42"}],
            ) as mock_snapper,
            patch.object(SnapshotManager, "_list_btrfs_snapshots") as mock_btrfs,
        ):
            result = SnapshotManager.list_snapshots()

        assert result == [{"id": "42"}]
        mock_snapper.assert_called_once()
        mock_btrfs.assert_not_called()

    def test_dispatch_to_btrfs(self):
        with (
            patch.object(SnapshotManager, "is_snapper_installed", return_value=False),
            patch.object(SnapshotManager, "_list_snapper_snapshots") as mock_snapper,
            patch.object(
                SnapshotManager,
                "_list_btrfs_snapshots",
                return_value=[{"id": "7"}],
            ) as mock_btrfs,
        ):
            result = SnapshotManager.list_snapshots()

        assert result == [{"id": "7"}]
        mock_snapper.assert_not_called()
        mock_btrfs.assert_called_once()

    def test_parse_csv_output(self):
        csv = (
            "Number,Date,Description,Type\n"
            "0,date,current,single\n"
            '42,"2026-08-11 10:00:00","my snapshot",single\n'
            "not-a-number,date,x,single\n"
        )
        with patch("better_dnf.snapshot.run_sudo", return_value=_cp(0, stdout=csv)):
            result = SnapshotManager._list_snapper_snapshots()

        ids = [s["id"] for s in result]
        assert "42" in ids
        assert "0" in ids
        # Non-numeric IDs are skipped
        assert len(ids) == 2

    def test_fallback_to_pipe_format(self):
        plain = (
            "Type │ Pre # │ Date │ User │ Description\n"
            "0 │ │ 2026-08-11 │ root │ current\n"
            "─────────────── separator ───────────────\n"
            "42 │ │ 2026-08-11 │ root │ my-snap\n"
            "│ │ only separators │\n"
        )
        # First call (--csvout) fails, second (plain) succeeds
        calls = [_cp(1), _cp(0, stdout=plain)]

        with patch(
            "better_dnf.snapshot.run_sudo", side_effect=lambda *a, **k: calls.pop(0)
        ):
            result = SnapshotManager._list_snapper_snapshots()

        ids = [s["id"] for s in result]
        assert "42" in ids
        assert "0" in ids
        # Separator lines ('-...' and '│...') are skipped
        assert len(ids) == 2

    def test_parse_btrfs_output(self):
        # Real 'btrfs subvolume list' output has no header line.
        output = (
            "ID 257 gen 12 top level 5 path <FS_TREE>/.snapshots\n"
            "ID 258 gen 13 top level 5 path <FS_TREE>/.snapshots/better-dnf-20260811\n"
        )
        with patch("better_dnf.snapshot.run_sudo", return_value=_cp(0, stdout=output)):
            result = SnapshotManager._list_btrfs_snapshots()

        assert len(result) == 2
        # The parser uses the last whitespace-separated token as the name
        assert result[1]["name"] == "<FS_TREE>/.snapshots/better-dnf-20260811"
        assert result[1]["path"].endswith("better-dnf-20260811")

    def test_list_errors_are_silent(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            side_effect=RuntimeError("boom"),
        ):
            result = SnapshotManager._list_snapper_snapshots()

        assert result == []


class TestRollback:
    """Tests for the rollback flow."""

    def test_snapshot_not_found(self):
        with (
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(SnapshotManager, "_list_snapper_snapshots", return_value=[]),
        ):
            ok, msg = SnapshotManager.rollback_snapshot("999")

        assert ok is False
        assert "999 not found" in msg

    def test_user_cancels_rollback(self):
        with (
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_list_snapper_snapshots",
                return_value=[{"id": "42"}],
            ),
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_confirm.return_value.ask.return_value = False
            ok, msg = SnapshotManager.rollback_snapshot("42")

        assert ok is False
        assert "Rollback cancelled" in msg

    def test_snapper_rollback_success(self):
        with (
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_list_snapper_snapshots",
                return_value=[{"id": "42"}],
            ),
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_confirm.return_value.ask.return_value = True
            with patch.object(
                SnapshotManager,
                "_rollback_snapper",
                return_value=(True, "Rolled back"),
            ) as mock_rollback:
                ok, _msg = SnapshotManager.rollback_snapshot("42")

        assert ok is True
        mock_rollback.assert_called_once_with("42")

    def test_btrfs_rollback_success(self):
        with (
            patch.object(SnapshotManager, "is_snapper_installed", return_value=False),
            patch.object(
                SnapshotManager,
                "_list_btrfs_snapshots",
                return_value=[{"id": "7"}],
            ),
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_confirm.return_value.ask.return_value = True
            with patch.object(
                SnapshotManager,
                "_rollback_btrfs",
                return_value=(True, "Rolled back"),
            ) as mock_rollback:
                ok, _msg = SnapshotManager.rollback_snapshot("7")

        assert ok is True
        mock_rollback.assert_called_once_with("7")

    def test_snapper_rollback_failure(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            return_value=_cp(1, stderr="failed to rollback"),
        ):
            ok, msg = SnapshotManager._rollback_snapper("42")

        assert ok is False
        assert "failed to rollback" in msg

    def test_btrfs_rollback_failure(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            return_value=_cp(1, stderr="subvolume busy"),
        ):
            ok, msg = SnapshotManager._rollback_btrfs("7")

        assert ok is False
        assert "subvolume busy" in msg


class TestDisplaySnapshots:
    """Tests for the display helper."""

    def test_empty_shows_message(self):
        printed = []

        with (
            patch.object(SnapshotManager, "list_snapshots", return_value=[]),
            patch(
                "better_dnf.snapshot.console.print",
                side_effect=lambda *a, **k: printed.append(a),
            ),
        ):
            SnapshotManager.display_snapshots()

        text = " ".join(str(a[0]) for a in printed)
        assert "No snapshots found" in text

    def test_with_snapshots_builds_table(self):
        printed = []

        with (
            patch.object(
                SnapshotManager,
                "list_snapshots",
                return_value=[
                    {
                        "id": "42",
                        "date": "today",
                        "description": "pre",
                        "type": "single",
                    }
                ],
            ),
            patch(
                "better_dnf.snapshot.console.print",
                side_effect=lambda *a, **k: printed.append(a),
            ),
        ):
            SnapshotManager.display_snapshots()

        # A Table was rendered (the only non-string arg)
        from rich.table import Table

        assert any(isinstance(a[0], Table) for a in printed if a)
