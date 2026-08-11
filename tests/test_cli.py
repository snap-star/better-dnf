"""
Tests for the CLI analyze command flow.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from rich.panel import Panel
from rich.table import Table
from typer.testing import CliRunner

from better_dnf.cli import app
from better_dnf.models import (
    PackageUpdate,
    UpdateCategory,
    UpdateImportance,
    UpdatePlan,
)

runner = CliRunner()


def _make_package(
    name="firefox",
    old="153.0",
    new="154.0",
    repo="updates",
    category=UpdateCategory.USER_APP,
    importance=UpdateImportance.MEDIUM,
):
    """Create a simple PackageUpdate.

    Note: defaults intentionally diverge from the model's OTHER/UNKNOWN
    so category/importance filter tests have meaningful values.
    """
    return PackageUpdate(
        name=name,
        arch="x86_64",
        old_version=old,
        new_version=new,
        repository=repo,
        category=category,
        importance=importance,
    )


def _render(printed):
    """Flatten captured console.print args into readable text.

    Panels/Tables contribute their title; everything else is str()'d.
    """
    parts = []
    for args in printed:
        for arg in args:
            if isinstance(arg, (Panel, Table)):
                if arg.title:
                    parts.append(str(arg.title))
            else:
                parts.append(str(arg))
    return " ".join(parts)


@pytest.fixture
def cli_env():
    """Mock analyzer/selector/applier and capture console.print output."""
    analyzer = Mock()
    analyzer.analyze_updates.return_value = []
    analyzer.get_risk_assessment.return_value = {
        "risk_level": "low",
        "recommendation": "System looks safe",
        "risk_factors": [],
        "total_packages": 0,
    }
    analyzer.get_security_updates.return_value = []
    analyzer.get_kernel_updates.return_value = []
    analyzer.get_driver_updates.return_value = []
    analyzer.get_packages_by_category.return_value = []
    analyzer.fetch_download_sizes = Mock()

    selector = Mock()
    selector.select_update_strategy.return_value = "cancel"
    selector.interactive_select_by_category.return_value = None
    selector.create_update_plan.return_value = UpdatePlan()
    selector.confirm_update.return_value = True

    applier = Mock()
    applier.apply_updates.return_value = (True, "Updates applied successfully")
    applier.rollback_updates.return_value = (True, "Rolled back")

    printed = []

    def _print(*args, **kwargs):
        printed.append(args)

    with (
        patch("better_dnf.cli.UpdateAnalyzer", return_value=analyzer),
        patch("better_dnf.cli.UpdateSelector", selector),
        patch("better_dnf.cli.UpdateApplier", applier),
        patch("better_dnf.cli.console.print", side_effect=_print),
        patch("better_dnf.cli.console.status", return_value=MagicMock()),
    ):
        yield {
            "analyzer": analyzer,
            "selector": selector,
            "applier": applier,
            "printed": printed,
            "text": lambda: _render(printed),
        }


class TestAnalyzeNoUpdates:
    """When there are no available updates."""

    def test_reports_up_to_date(self, cli_env):
        cli_env["analyzer"].analyze_updates.return_value = []

        result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 0
        assert "No updates available" in cli_env["text"]()
        cli_env["selector"].display_update_summary.assert_not_called()
        cli_env["applier"].apply_updates.assert_not_called()


class TestAnalyzeCliStrategy:
    """Strategy provided via the --strategy flag (no interactive menu)."""

    def test_security_strategy_applies_updates(self, cli_env):
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_security_updates.return_value = [pkg]

        result = runner.invoke(app, ["analyze", "-s", "security"])

        assert result.exit_code == 0
        cli_env["analyzer"].get_security_updates.assert_called_once()
        cli_env["analyzer"].fetch_download_sizes.assert_called_once_with([pkg])
        cli_env["applier"].apply_updates.assert_called_once()
        _, kwargs = cli_env["applier"].apply_updates.call_args
        assert kwargs["create_snapshot"] is True
        assert "Update Complete" in cli_env["text"]()

    def test_security_strategy_with_no_snapshot_flag(self, cli_env):
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_security_updates.return_value = [pkg]

        result = runner.invoke(app, ["analyze", "-s", "security", "-n"])

        assert result.exit_code == 0
        _, kwargs = cli_env["applier"].apply_updates.call_args
        assert kwargs["create_snapshot"] is False

    def test_kernel_drivers_combines_both(self, cli_env):
        kernel = _make_package("kernel", repo="fedora")
        driver = _make_package("nvidia", repo="rpmfusion")
        cli_env["analyzer"].analyze_updates.return_value = [kernel, driver]
        cli_env["analyzer"].get_kernel_updates.return_value = [kernel]
        cli_env["analyzer"].get_driver_updates.return_value = [driver]

        result = runner.invoke(app, ["analyze", "-s", "kernel_drivers"])

        assert result.exit_code == 0
        cli_env["analyzer"].get_kernel_updates.assert_called_once()
        cli_env["analyzer"].get_driver_updates.assert_called_once()
        cli_env["applier"].apply_updates.assert_called_once()

    def test_official_strategy(self, cli_env):
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_packages_by_category.return_value = [pkg]

        result = runner.invoke(app, ["analyze", "-s", "official"])

        assert result.exit_code == 0
        cli_env["analyzer"].get_packages_by_category.assert_called_once_with(
            UpdateCategory.OFFICIAL
        )

    def test_user_apps_strategy(self, cli_env):
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_packages_by_category.return_value = [pkg]

        result = runner.invoke(app, ["analyze", "-s", "user_apps"])

        assert result.exit_code == 0
        cli_env["applier"].apply_updates.assert_called_once()

    def test_all_strategy_uses_full_package_list(self, cli_env):
        pkgs = [_make_package("a"), _make_package("b")]
        cli_env["analyzer"].analyze_updates.return_value = pkgs
        plan = UpdatePlan(packages=list(pkgs))
        cli_env["selector"].create_update_plan.return_value = plan

        result = runner.invoke(app, ["analyze", "-s", "all"])

        assert result.exit_code == 0
        cli_env["selector"].create_update_plan.assert_called_once_with(pkgs)
        cli_env["applier"].apply_updates.assert_called_once()
        plan_arg = cli_env["applier"].apply_updates.call_args.args[0]
        assert len(plan_arg.packages) == 2

    def test_unknown_strategy_reports_error(self, cli_env):
        cli_env["analyzer"].analyze_updates.return_value = [_make_package()]

        result = runner.invoke(app, ["analyze", "-s", "bogus"])

        assert result.exit_code == 0
        assert "Unknown strategy" in cli_env["text"]()
        cli_env["applier"].apply_updates.assert_not_called()

    def test_custom_strategy_cancelled(self, cli_env):
        cli_env["analyzer"].analyze_updates.return_value = [_make_package()]
        cli_env["selector"].interactive_select_by_category.return_value = None

        result = runner.invoke(app, ["analyze", "-s", "custom"])

        assert result.exit_code == 0
        assert "Operation cancelled by user" in cli_env["text"]()
        cli_env["applier"].apply_updates.assert_not_called()

    def test_custom_strategy_with_selection_applies_updates(self, cli_env):
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["selector"].interactive_select_by_category.return_value = [pkg]

        result = runner.invoke(app, ["analyze", "-s", "custom"])

        assert result.exit_code == 0
        cli_env["selector"].interactive_select_by_category.assert_called_once()
        cli_env["applier"].apply_updates.assert_called_once()
        assert "Update Complete" in cli_env["text"]()

    def test_no_packages_selected(self, cli_env):
        cli_env["analyzer"].analyze_updates.return_value = [_make_package()]
        cli_env["analyzer"].get_security_updates.return_value = []

        result = runner.invoke(app, ["analyze", "-s", "security"])

        assert result.exit_code == 0
        assert "No packages selected for update" in cli_env["text"]()
        cli_env["applier"].apply_updates.assert_not_called()


class TestAnalyzeInteractive:
    """Interactive mode (no --strategy flag)."""

    def test_cancel_at_strategy_menu(self, cli_env):
        cli_env["analyzer"].analyze_updates.return_value = [_make_package()]
        cli_env["selector"].select_update_strategy.return_value = None

        result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 0
        assert "Operation cancelled by user" in cli_env["text"]()
        cli_env["applier"].apply_updates.assert_not_called()

    def test_cancel_option_at_strategy_menu(self, cli_env):
        cli_env["analyzer"].analyze_updates.return_value = [_make_package()]
        cli_env["selector"].select_update_strategy.return_value = "cancel"

        result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 0
        assert "Operation cancelled by user" in cli_env["text"]()

    def test_custom_back_to_menu_loops(self, cli_env):
        """'Back' from custom selection returns to the strategy menu."""
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["selector"].select_update_strategy.side_effect = [
            "custom",
            "cancel",
        ]
        cli_env["selector"].interactive_select_by_category.return_value = None

        result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 0
        # Strategy menu was shown twice (custom, then cancel)
        assert cli_env["selector"].select_update_strategy.call_count == 2
        cli_env["selector"].interactive_select_by_category.assert_called_once()
        assert "Operation cancelled by user" in cli_env["text"]()

    def test_custom_selection_proceeds_to_update(self, cli_env):
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["selector"].select_update_strategy.return_value = "custom"
        cli_env["selector"].interactive_select_by_category.return_value = [pkg]

        result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 0
        cli_env["applier"].apply_updates.assert_called_once()
        assert "Update Complete" in cli_env["text"]()


class TestAnalyzeConfirmation:
    """Plan confirmation behavior."""

    def test_confirmation_declined_cancels(self, cli_env):
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_security_updates.return_value = [pkg]
        cli_env["selector"].confirm_update.return_value = False

        result = runner.invoke(app, ["analyze", "-s", "security"])

        assert result.exit_code == 0
        assert "Update cancelled by user" in cli_env["text"]()
        cli_env["applier"].apply_updates.assert_not_called()

    def test_success_shows_snapshot_id(self, cli_env):
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_security_updates.return_value = [pkg]
        cli_env["selector"].create_update_plan.return_value = UpdatePlan(
            snapshot_id="42"
        )

        result = runner.invoke(app, ["analyze", "-s", "security"])

        assert result.exit_code == 0
        assert "Update Complete" in cli_env["text"]()
        assert "Snapshot ID: 42" in cli_env["text"]()


class TestAnalyzeFailure:
    """Update failure and rollback flow."""

    def test_failure_offers_rollback_and_accepts(self, cli_env):
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_security_updates.return_value = [pkg]
        cli_env["applier"].apply_updates.return_value = (False, "Update failed")
        cli_env["selector"].create_update_plan.return_value = UpdatePlan(
            snapshot_id="42"
        )

        with patch("questionary.confirm") as confirm:
            confirm.return_value.ask.return_value = True
            result = runner.invoke(app, ["analyze", "-s", "security"])

        assert result.exit_code == 0
        assert "Update Failed" in cli_env["text"]()
        cli_env["applier"].rollback_updates.assert_called_once()
        assert "Rolled back" in cli_env["text"]()

    def test_failure_skips_rollback_when_declined(self, cli_env):
        pkg = _make_package()
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_security_updates.return_value = [pkg]
        cli_env["applier"].apply_updates.return_value = (False, "Update failed")
        cli_env["selector"].create_update_plan.return_value = UpdatePlan(
            snapshot_id="42"
        )

        with patch("questionary.confirm") as confirm:
            confirm.return_value.ask.return_value = False
            result = runner.invoke(app, ["analyze", "-s", "security"])

        assert result.exit_code == 0
        cli_env["applier"].rollback_updates.assert_not_called()


class TestAnalyzeExceptions:
    """Exception handling."""

    def test_keyboard_interrupt_exits_cleanly(self, cli_env):
        cli_env["analyzer"].analyze_updates.side_effect = KeyboardInterrupt()

        result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 0
        assert "Operation cancelled by user" in cli_env["text"]()

    def test_generic_exception_exits_with_error(self, cli_env):
        cli_env["analyzer"].analyze_updates.side_effect = RuntimeError("boom")

        result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 1
        assert "Error: boom" in cli_env["text"]()


class TestListUpdates:
    """Tests for the list-updates command."""

    def test_no_updates(self, cli_env):
        cli_env["analyzer"].analyze_updates.return_value = []

        result = runner.invoke(app, ["list-updates"])

        assert result.exit_code == 0
        assert "No updates available" in cli_env["text"]()

    def test_invalid_category(self, cli_env):
        cli_env["analyzer"].analyze_updates.return_value = [_make_package()]

        result = runner.invoke(app, ["list-updates", "-c", "bogus"])

        assert result.exit_code == 0
        assert "Invalid category: bogus" in cli_env["text"]()

    def test_invalid_importance(self, cli_env):
        cli_env["analyzer"].analyze_updates.return_value = [_make_package()]

        result = runner.invoke(app, ["list-updates", "-i", "bogus"])

        assert result.exit_code == 0
        assert "Invalid importance: bogus" in cli_env["text"]()

    def test_generic_exception_exits_with_error(self, cli_env):
        cli_env["analyzer"].analyze_updates.side_effect = RuntimeError("boom")

        result = runner.invoke(app, ["list-updates"])

        assert result.exit_code == 1
        assert "Error: boom" in cli_env["text"]()

    def test_filter_by_category(self, cli_env):
        kernel = _make_package("kernel", category=UpdateCategory.KERNEL, repo="fedora")
        app_pkg = _make_package("firefox")
        cli_env["analyzer"].analyze_updates.return_value = [kernel, app_pkg]

        result = runner.invoke(app, ["list-updates", "-c", "kernel"])

        assert result.exit_code == 0
        cli_env["selector"].display_packages_by_category.assert_called_once_with(
            [kernel], UpdateCategory.KERNEL
        )

    def test_no_match_for_filter(self, cli_env):
        app_pkg = _make_package("firefox")
        cli_env["analyzer"].analyze_updates.return_value = [app_pkg]

        result = runner.invoke(app, ["list-updates", "-c", "kernel"])

        assert result.exit_code == 0
        assert "No updates match the specified filters" in cli_env["text"]()

    def test_groups_by_category_when_no_filter(self, cli_env):
        kernel = _make_package("kernel", category=UpdateCategory.KERNEL, repo="fedora")
        app_pkg = _make_package("firefox", category=UpdateCategory.USER_APP)
        cli_env["analyzer"].analyze_updates.return_value = [kernel, app_pkg]

        result = runner.invoke(app, ["list-updates"])

        assert result.exit_code == 0
        # Displayed once per category that has packages
        calls = cli_env["selector"].display_packages_by_category.call_args_list
        assert len(calls) == 2
        categories = [c.args[1] for c in calls]
        assert UpdateCategory.KERNEL in categories
        assert UpdateCategory.USER_APP in categories

    def test_filter_by_importance(self, cli_env):
        pkg = _make_package(importance=UpdateImportance.CRITICAL)
        cli_env["analyzer"].analyze_updates.return_value = [pkg]

        result = runner.invoke(app, ["list-updates", "-i", "critical"])

        assert result.exit_code == 0
        cli_env["selector"].display_packages_by_category.assert_called_once()
        # The critical package passed through the filter
        passed = cli_env["selector"].display_packages_by_category.call_args.args[0]
        assert passed == [pkg]


class TestSecurityCommand:
    """Tests for the security command."""

    def test_no_security_updates(self, cli_env):
        cli_env["analyzer"].analyze_updates.return_value = [_make_package()]
        cli_env["analyzer"].get_security_updates.return_value = []

        result = runner.invoke(app, ["security"])

        assert result.exit_code == 0
        assert "No security updates available" in cli_env["text"]()

    def test_lists_security_updates(self, cli_env):
        pkg = _make_package("openssl")
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_security_updates.return_value = [pkg]

        result = runner.invoke(app, ["security"])

        assert result.exit_code == 0
        cli_env["selector"].display_packages_by_category.assert_called_once_with(
            [pkg], UpdateCategory.SECURITY
        )

    def test_apply_flag_applies_updates(self, cli_env):
        pkg = _make_package("openssl")
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_security_updates.return_value = [pkg]

        result = runner.invoke(app, ["security", "-a"])

        assert result.exit_code == 0
        cli_env["applier"].apply_updates.assert_called_once()

    def test_apply_declined_confirmation(self, cli_env):
        pkg = _make_package("openssl")
        cli_env["analyzer"].analyze_updates.return_value = [pkg]
        cli_env["analyzer"].get_security_updates.return_value = [pkg]
        cli_env["selector"].confirm_update.return_value = False

        result = runner.invoke(app, ["security", "-a"])

        assert result.exit_code == 0
        cli_env["applier"].apply_updates.assert_not_called()


class TestSnapshotCommand:
    """Tests for the snapshot command."""

    def test_create_success(self, cli_env):
        with patch(
            "better_dnf.cli.SnapshotManager.create_snapshot",
            return_value=(True, "42", "Snapshot created successfully: 42"),
        ):
            result = runner.invoke(app, ["snapshot", "create"])

        assert result.exit_code == 0
        assert "Snapshot created successfully: 42" in cli_env["text"]()

    def test_create_failure(self, cli_env):
        with patch(
            "better_dnf.cli.SnapshotManager.create_snapshot",
            return_value=(False, None, "Root filesystem is not btrfs"),
        ):
            result = runner.invoke(app, ["snapshot", "create"])

        assert result.exit_code == 0
        assert "Root filesystem is not btrfs" in cli_env["text"]()

    def test_create_post_positional(self, cli_env):
        with patch(
            "better_dnf.cli.SnapshotManager.create_post_snapshot",
            return_value=(True, "43", "Snapshot created successfully: 43"),
        ) as post:
            result = runner.invoke(app, ["snapshot", "create", "post"])

        assert result.exit_code == 0
        assert "Snapshot created successfully: 43" in cli_env["text"]()
        post.assert_called_once()

    def test_create_post_via_type_flag(self, cli_env):
        with patch(
            "better_dnf.cli.SnapshotManager.create_post_snapshot",
            return_value=(True, "43", "Snapshot created successfully: 43"),
        ) as post:
            result = runner.invoke(app, ["snapshot", "create", "-t", "post"])

        assert result.exit_code == 0
        post.assert_called_once()

    def test_create_post_with_pre_number_flag(self, cli_env):
        with patch(
            "better_dnf.cli.SnapshotManager.create_post_snapshot",
            return_value=(True, "43", "Snapshot created successfully: 43"),
        ) as post:
            result = runner.invoke(
                app, ["snapshot", "create", "post", "--pre-number", "307"]
            )

        assert result.exit_code == 0
        assert "Snapshot created successfully: 43" in cli_env["text"]()
        assert post.call_args.kwargs["pre_number"] == "307"

    def test_create_single_positional(self, cli_env):
        with patch(
            "better_dnf.cli.SnapshotManager.create_snapshot",
            return_value=(True, "44", "Snapshot created successfully: 44"),
        ) as snap:
            result = runner.invoke(app, ["snapshot", "create", "single"])

        assert result.exit_code == 0
        snap.assert_called_once()
        assert snap.call_args.kwargs["snapshot_type"] == "single"

    def test_create_with_description(self, cli_env):
        with patch(
            "better_dnf.cli.SnapshotManager.create_snapshot",
            return_value=(True, "45", "Snapshot created successfully: 45"),
        ) as snap:
            result = runner.invoke(
                app, ["snapshot", "create", "-d", "before kernel update"]
            )

        assert result.exit_code == 0
        assert snap.call_args.kwargs["description"] == "before kernel update"

    def test_create_invalid_type(self, cli_env):
        result = runner.invoke(app, ["snapshot", "create", "bogus"])

        assert result.exit_code == 0
        assert "Invalid snapshot type: bogus" in cli_env["text"]()

    def test_list(self, cli_env):
        with patch("better_dnf.cli.SnapshotManager.display_snapshots") as display:
            result = runner.invoke(app, ["snapshot", "list"])

        assert result.exit_code == 0
        display.assert_called_once()

    def test_rollback_requires_id(self, cli_env):
        result = runner.invoke(app, ["snapshot", "rollback"])

        assert result.exit_code == 0
        assert "Please provide a snapshot ID" in cli_env["text"]()

    def test_rollback_success(self, cli_env):
        with patch(
            "better_dnf.cli.SnapshotManager.rollback_snapshot",
            return_value=(True, "Rolled back"),
        ) as rollback:
            result = runner.invoke(app, ["snapshot", "rollback", "42"])

        assert result.exit_code == 0
        rollback.assert_called_once_with("42")
        assert "Rolled back" in cli_env["text"]()

    def test_rollback_failure(self, cli_env):
        with patch(
            "better_dnf.cli.SnapshotManager.rollback_snapshot",
            return_value=(False, "Rollback failed"),
        ) as rollback:
            result = runner.invoke(app, ["snapshot", "rollback", "42"])

        assert result.exit_code == 0
        rollback.assert_called_once_with("42")
        assert "Rollback failed" in cli_env["text"]()

    def test_unknown_action(self, cli_env):
        result = runner.invoke(app, ["snapshot", "bogus"])

        assert result.exit_code == 0
        assert "Unknown action: bogus" in cli_env["text"]()


class TestHistoryCommand:
    """Tests for the history command."""

    def test_no_history(self, cli_env):
        cli_env["applier"].get_update_history.return_value = []

        result = runner.invoke(app, ["history"])

        assert result.exit_code == 0
        assert "No update history found" in cli_env["text"]()

    def test_displays_transactions(self, cli_env):
        cli_env["applier"].get_update_history.return_value = [
            {"id": "1", "date": "today", "action": "Upgrade", "packages": "kernel"},
        ]

        result = runner.invoke(app, ["history"])

        assert result.exit_code == 0
        assert "Recent Transactions" in cli_env["text"]()

    def test_limit_flag(self, cli_env):
        cli_env["applier"].get_update_history.return_value = []

        result = runner.invoke(app, ["history", "-l", "10"])

        assert result.exit_code == 0
        cli_env["applier"].get_update_history.assert_called_once_with(10)


class TestVersionCommand:
    """Tests for the version command."""

    def test_prints_version(self, cli_env):
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "Better DNF" in cli_env["text"]()
