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

    def test_respects_snapshot_type(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_create_snapper_snapshot",
                return_value=(True, "42", "ok"),
            ) as mock_snapper,
        ):
            SnapshotManager.create_snapshot(snapshot_type="single")

        assert mock_snapper.call_args.args[2] == "single"

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


class TestFindLatestPreNumber:
    """Tests for finding the latest pre snapshot for post pairing."""

    def test_returns_highest_pre_id(self):
        with patch.object(
            SnapshotManager,
            "_list_snapper_snapshots",
            return_value=[
                {"id": "10", "type": "single"},
                {"id": "11", "type": "pre"},
                {"id": "12", "type": "pre"},
                {"id": "13", "type": "single"},
            ],
        ):
            assert SnapshotManager._find_latest_pre_number() == "12"

    def test_returns_none_when_no_pre(self):
        with patch.object(
            SnapshotManager,
            "_list_snapper_snapshots",
            return_value=[{"id": "10", "type": "single"}],
        ):
            assert SnapshotManager._find_latest_pre_number() is None


class TestCreatePostSnapshot:
    """Tests for create_post_snapshot."""

    def test_uses_post_type_and_post_prefix(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_list_snapper_snapshots",
                return_value=[{"id": "42", "type": "pre", "pre_num": ""}],
            ),
            patch.object(SnapshotManager, "_find_latest_pre_number", return_value="42"),
            patch.object(
                SnapshotManager,
                "_create_snapper_snapshot",
                return_value=(True, "43", "ok"),
            ) as mock_snapper,
        ):
            ok, snap_id, msg = SnapshotManager.create_post_snapshot()

        assert ok is True
        assert snap_id == "43"
        snapshot_name, _, snapshot_type = mock_snapper.call_args.args
        assert snapshot_type == "post"
        assert "-post-" in snapshot_name
        assert mock_snapper.call_args.kwargs["pre_number"] == "42"
        assert "paired with pre #42" in msg

    def test_passes_pre_number_through(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_list_snapper_snapshots",
                return_value=[{"id": "99", "type": "pre", "pre_num": ""}],
            ),
            patch.object(
                SnapshotManager,
                "_create_snapper_snapshot",
                return_value=(True, "43", "ok"),
            ) as mock_snapper,
        ):
            ok, _snap_id, _msg = SnapshotManager.create_post_snapshot(pre_number="99")

        assert ok is True
        assert mock_snapper.call_args.kwargs["pre_number"] == "99"

    def test_no_pre_snapshot_returns_error(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(SnapshotManager, "_list_snapper_snapshots", return_value=[]),
            patch.object(SnapshotManager, "_find_latest_pre_number", return_value=None),
        ):
            ok, _snap_id, msg = SnapshotManager.create_post_snapshot()

        assert ok is False
        assert "No pre snapshot found" in msg

    def test_non_btrfs_returns_failure(self):
        with patch.object(SnapshotManager, "is_btrfs_root", return_value=False):
            ok, _snap_id, msg = SnapshotManager.create_post_snapshot()

        assert ok is False
        assert "not btrfs" in msg

    def test_pre_not_found_returns_clear_error(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_list_snapper_snapshots",
                return_value=[{"id": "10", "type": "single", "pre_num": ""}],
            ),
        ):
            ok, _snap_id, msg = SnapshotManager.create_post_snapshot(pre_number="999")

        assert ok is False
        assert "999" in msg
        assert "not found" in msg

    def test_pre_wrong_type_returns_clear_error(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_list_snapper_snapshots",
                return_value=[{"id": "42", "type": "single", "pre_num": ""}],
            ),
        ):
            ok, _snap_id, msg = SnapshotManager.create_post_snapshot(pre_number="42")

        assert ok is False
        assert "not 'pre'" in msg

    def test_pre_already_paired_returns_clear_error(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_list_snapper_snapshots",
                return_value=[
                    {"id": "42", "type": "pre", "pre_num": ""},
                    {"id": "43", "type": "post", "pre_num": "42"},
                ],
            ),
        ):
            ok, _snap_id, msg = SnapshotManager.create_post_snapshot(pre_number="42")

        assert ok is False
        assert "already has a post" in msg
        assert "#43" in msg

    def test_pairing_failure_falls_back_to_standalone(self):
        """When snapper rejects the pair, a standalone snapshot is created."""
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_list_snapper_snapshots",
                return_value=[{"id": "42", "type": "pre", "pre_num": ""}],
            ),
            patch.object(
                SnapshotManager,
                "_create_snapper_snapshot",
                side_effect=[
                    (False, None, "Illegal snapshot"),
                    (True, "50", "Snapshot created successfully: 50"),
                ],
            ) as mock_snapper,
        ):
            ok, snap_id, msg = SnapshotManager.create_post_snapshot(pre_number="42")

        assert ok is True
        assert snap_id == "50"
        assert "standalone" in msg
        assert "Illegal snapshot" in msg
        assert "--pre-number 42" in msg
        # First call: post with pre-number. Second call: standalone single.
        first = mock_snapper.call_args_list[0]
        assert first.args[2] == "post"
        assert first.kwargs["pre_number"] == "42"
        second = mock_snapper.call_args_list[1]
        assert second.args[2] == "single"

    def test_fallback_failure_returns_original_error(self):
        with (
            patch.object(SnapshotManager, "is_btrfs_root", return_value=True),
            patch.object(SnapshotManager, "is_snapper_installed", return_value=True),
            patch.object(
                SnapshotManager,
                "_list_snapper_snapshots",
                return_value=[{"id": "42", "type": "pre", "pre_num": ""}],
            ),
            patch.object(
                SnapshotManager,
                "_create_snapper_snapshot",
                return_value=(False, None, "Illegal snapshot"),
            ),
        ):
            ok, _snap_id, msg = SnapshotManager.create_post_snapshot(pre_number="42")

        assert ok is False
        assert "Pre/post snapshot failed" in msg
        assert "Illegal snapshot" in msg


class TestCreateSnapperSnapshot:
    """Tests for the snapper-backed creation."""

    def test_success_parses_print_number(self):
        # 'snapper create -p' prints the new snapshot number to stdout.
        with patch(
            "better_dnf.snapshot.run_sudo",
            return_value=_cp(0, stdout="42\n"),
        ) as run:
            ok, snap_id, msg = SnapshotManager._create_snapper_snapshot(
                "better-dnf-20260811", None, "pre"
            )

        assert ok is True
        assert snap_id == "42"
        assert "42" in msg
        # Uses --print-number, not a separate snapper list call
        cmd = run.call_args.args[0]
        assert "-p" in cmd
        assert "list" not in cmd

    def test_success_without_print_number_output(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            return_value=_cp(0, stdout=""),
        ):
            ok, snap_id, msg = SnapshotManager._create_snapper_snapshot(
                "better-dnf-20260811", None, "pre"
            )

        assert ok is True
        assert snap_id is None
        assert "Snapshot created successfully" in msg

    def test_post_passes_pre_number_flag(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            return_value=_cp(0, stdout="43\n"),
        ) as run:
            ok, snap_id, _msg = SnapshotManager._create_snapper_snapshot(
                "better-dnf-post-20260811", None, "post", "42"
            )

        assert ok is True
        assert snap_id == "43"
        cmd = run.call_args.args[0]
        assert "--pre-number" in cmd
        assert cmd[cmd.index("--pre-number") + 1] == "42"
        assert "-t" in cmd
        assert cmd[cmd.index("-t") + 1] == "post"

    def test_post_without_pre_number_fails(self):
        with patch("better_dnf.snapshot.run_sudo") as run:
            ok, _snap_id, msg = SnapshotManager._create_snapper_snapshot(
                "better-dnf-post-20260811", None, "post", None
            )

        assert ok is False
        assert "pre snapshot number" in msg
        run.assert_not_called()

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
        # Real snapper --csvout column order: #,Type,Pre #,Date,User,...
        csv = (
            "#,Type,Pre #,Date,User,Cleanup,Description,Userdata\n"
            "0,single,,,root,,current,\n"
            '42,single,,2026-08-11 10:00:00,root,,"my snapshot",\n'
            "307,pre,,2026-08-11 00:54:52,root,,better-dnf-snap,\n"
            "43,post,42,2026-08-11 11:00:00,root,,post-snap,\n"
            "not-a-number,single,,x,root,,x,\n"
        )
        with patch("better_dnf.snapshot.run_sudo", return_value=_cp(0, stdout=csv)):
            result = SnapshotManager._list_snapper_snapshots()

        by_id = {s["id"]: s for s in result}
        assert "42" in by_id
        assert "0" in by_id
        assert "307" in by_id
        assert "43" in by_id
        # Non-numeric IDs are skipped
        assert len(result) == 4
        # Type and date come from the CORRECT columns
        assert by_id["307"]["type"] == "pre"
        assert by_id["42"]["type"] == "single"
        assert by_id["42"]["date"] == "2026-08-11 10:00:00"
        # The Pre # column links a post snapshot to its pre
        assert by_id["43"]["type"] == "post"
        assert by_id["43"]["pre_num"] == "42"

    def test_parse_csv_legacy_columns(self):
        # Older/simpler formats (Number,Date,Description,Type) still work
        csv = "Number,Date,Description,Type\n0,date,current,single\n42,date,my-snap,single\n"
        with patch("better_dnf.snapshot.run_sudo", return_value=_cp(0, stdout=csv)):
            result = SnapshotManager._list_snapper_snapshots()

        by_id = {s["id"]: s for s in result}
        assert by_id["42"]["type"] == "single"
        assert by_id["42"]["description"] == "my-snap"

    def test_fallback_to_table_format(self):
        # Real snapper table format: # | Type | Pre # | Date | User | ...
        plain = (
            "   # | Type | Pre # | Date                     | User | Cleanup | Description | Userdata\n"
            "----+------+-------+--------------------------+------+---------+-------------+--------\n"
            "   0 | single|       |                          | root |         | current     |        \n"
            "  42 | single|       | 2026-08-11 10:00:00      | root |         | my-snap      |        \n"
            " 307 | pre   |       | 2026-08-11 00:54:52      | root |         | better-dnf-1 |        \n"
            "  43 | post  | 42    | 2026-08-11 11:00:00      | root |         | post-snap    |        \n"
        )
        # First call (--csvout) fails, second (plain table) succeeds
        calls = [_cp(1), _cp(0, stdout=plain)]

        with patch(
            "better_dnf.snapshot.run_sudo", side_effect=lambda *a, **k: calls.pop(0)
        ):
            result = SnapshotManager._list_snapper_snapshots()

        by_id = {s["id"]: s for s in result}
        assert "42" in by_id
        assert "0" in by_id
        assert "43" in by_id
        # Separator rows are skipped; type parsed from the correct column
        assert len(result) == 4
        assert by_id["307"]["type"] == "pre"
        assert by_id["42"]["date"] == "2026-08-11 10:00:00"
        # The Pre # column links a post snapshot to its pre
        assert by_id["43"]["type"] == "post"
        assert by_id["43"]["pre_num"] == "42"

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


class TestGetDefaultSubvolumeId:
    """Tests for _get_default_subvolume_id."""

    def test_returns_id_from_get_default(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            return_value=_cp(0, stdout="ID 257 (root)"),
        ):
            assert SnapshotManager._get_default_subvolume_id() == "257"

    def test_returns_id_from_long_format(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            return_value=_cp(0, stdout="ID 257 gen 12 top level 5 path @"),
        ):
            assert SnapshotManager._get_default_subvolume_id() == "257"

    def test_returns_none_on_failure(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            return_value=_cp(1, stderr="error"),
        ):
            assert SnapshotManager._get_default_subvolume_id() is None

    def test_returns_none_on_unexpected_output(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            return_value=_cp(0, stdout="unexpected output"),
        ):
            assert SnapshotManager._get_default_subvolume_id() is None

    def test_returns_none_on_exception(self):
        with patch(
            "better_dnf.snapshot.run_sudo",
            side_effect=RuntimeError("boom"),
        ):
            assert SnapshotManager._get_default_subvolume_id() is None


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
        with (
            patch.object(
                SnapshotManager,
                "_get_default_subvolume_id",
                return_value="257",
            ),
            patch(
                "better_dnf.snapshot.run_sudo",
                return_value=_cp(1, stderr="failed to rollback"),
            ),
        ):
            ok, msg = SnapshotManager._rollback_snapper("42")

        assert ok is False
        assert "failed to rollback" in msg

    def test_snapper_rollback_passes_ambit(self):
        """Rollback includes --ambit when default subvolume is detected."""
        with (
            patch.object(
                SnapshotManager,
                "_get_default_subvolume_id",
                return_value="257",
            ),
            patch(
                "better_dnf.snapshot.run_sudo",
                return_value=_cp(0, stdout=""),
            ) as mock_run,
        ):
            ok, _msg = SnapshotManager._rollback_snapper("42")

        assert ok is True
        cmd = mock_run.call_args.args[0]
        assert "--ambit" in cmd
        assert cmd[cmd.index("--ambit") + 1] == "257"

    def test_snapper_rollback_omits_ambit_when_undetectable(self):
        """Rollback omits --ambit when default subvolume cannot be detected."""
        with (
            patch.object(
                SnapshotManager,
                "_get_default_subvolume_id",
                return_value=None,
            ),
            patch(
                "better_dnf.snapshot.run_sudo",
                return_value=_cp(0, stdout=""),
            ) as mock_run,
        ):
            ok, _msg = SnapshotManager._rollback_snapper("42")

        assert ok is True
        cmd = mock_run.call_args.args[0]
        assert "--ambit" not in cmd

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
