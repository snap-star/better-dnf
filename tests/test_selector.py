"""
Tests for the selector module (interactive menu navigation).

NOTE ON MOCK TARGETS: selector.py mixes two styles of questionary usage:
  - `questionary.select(...)` (attribute access) in interactive_select_by_category
  - `from questionary import select, checkbox, confirm` (module-level imports)
    used in select_update_strategy / _select_individual_packages / confirm_update

So `questionary.select` and `better_dnf.selector.select` are intentionally
patched separately below — they are distinct call sites and patching one does
not affect the other.
"""

from unittest.mock import Mock, patch

import pytest
import questionary

from better_dnf.models import (
    PackageUpdate,
    UpdateCategory,
    UpdateImportance,
    UpdatePlan,
)
from better_dnf.selector import UpdateSelector


def _make_package(
    name="firefox",
    category=UpdateCategory.USER_APP,
    importance=UpdateImportance.MEDIUM,
):
    """Create a simple PackageUpdate."""
    return PackageUpdate(
        name=name,
        arch="x86_64",
        old_version="153.0",
        new_version="154.0",
        repository="updates",
        category=category,
        importance=importance,
    )


@pytest.fixture(autouse=True)
def _silence_console():
    """Silence console.print output during tests."""
    with patch("better_dnf.selector.console.print"):
        yield


class TestSelectUpdateStrategy:
    """Tests for the strategy selection menu."""

    def test_returns_selected_strategy(self):
        with patch("better_dnf.selector.select") as mock_select:
            mock_select.return_value.ask.return_value = "security"
            result = UpdateSelector.select_update_strategy()

        assert result == "security"

    def test_returns_cancel_value(self):
        with patch("better_dnf.selector.select") as mock_select:
            mock_select.return_value.ask.return_value = "cancel"
            result = UpdateSelector.select_update_strategy()

        assert result == "cancel"

    def test_returns_none_on_escape(self):
        with patch("better_dnf.selector.select") as mock_select:
            mock_select.return_value.ask.return_value = None
            result = UpdateSelector.select_update_strategy()

        assert result is None

    def test_menu_includes_cancel_option(self):
        """The strategy menu must contain a Cancel choice."""
        with patch("better_dnf.selector.select") as mock_select:
            mock_select.return_value.ask.return_value = "security"
            UpdateSelector.select_update_strategy()

        choices = mock_select.call_args.kwargs["choices"]
        values = [
            c.value for c in choices
            if isinstance(c, questionary.Choice)
        ]
        assert "cancel" in values


class TestInteractiveSelectByCategory:
    """Tests for category browsing and navigation."""

    def test_no_categories_returns_empty(self):
        packages = []

        result = UpdateSelector.interactive_select_by_category(packages)

        assert result == []

    def test_select_returns_none_on_escape(self):
        packages = [_make_package()]

        with patch("questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = None
            result = UpdateSelector.interactive_select_by_category(packages)

        assert result is None

    def test_cancel_option_returns_none(self):
        packages = [_make_package()]

        with patch("questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "cancel"
            result = UpdateSelector.interactive_select_by_category(packages)

        assert result is None

    def test_back_option_returns_none(self):
        packages = [_make_package()]

        with patch("questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "back"
            result = UpdateSelector.interactive_select_by_category(packages)

        assert result is None

    def test_menu_includes_back_and_cancel(self):
        packages = [_make_package()]

        with patch("questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = None
            UpdateSelector.interactive_select_by_category(packages)

        choices = mock_select.call_args.kwargs["choices"]
        values = [
            c.value for c in choices
            if isinstance(c, questionary.Choice)
        ]
        assert "back" in values
        assert "cancel" in values

    def test_select_all_delegates_to_individual_selection(self):
        packages = [_make_package("a"), _make_package("b")]
        selected = [packages[0]]

        with patch("questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "select_all"
            with patch.object(
                UpdateSelector, "_select_individual_packages",
                return_value=selected,
            ) as mock_individual:
                result = UpdateSelector.interactive_select_by_category(packages)

        assert result == selected
        mock_individual.assert_called_once_with(packages)

    def test_show_all_delegates_to_individual_selection(self):
        packages = [_make_package("a")]

        with patch("questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "all"
            with patch.object(
                UpdateSelector, "_select_individual_packages",
                return_value=packages,
            ) as mock_individual:
                result = UpdateSelector.interactive_select_by_category(packages)

        assert result == packages
        mock_individual.assert_called_once_with(packages)

    def test_empty_individual_selection_propagates(self):
        """An empty (but not 'back') selection is returned as-is."""
        packages = [_make_package("a")]

        with patch("questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "select_all"
            with patch.object(
                UpdateSelector, "_select_individual_packages",
                return_value=[],  # user confirmed with nothing selected
            ) as mock_individual:
                result = UpdateSelector.interactive_select_by_category(packages)

        assert result == []
        mock_individual.assert_called_once_with(packages)

    def test_category_selection_filters_packages(self):
        kernel = _make_package(
            "kernel", category=UpdateCategory.KERNEL,
            importance=UpdateImportance.HIGH,
        )
        app = _make_package("firefox")
        packages = [kernel, app]
        selected = [kernel]

        with patch("questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = UpdateCategory.KERNEL
            with patch.object(
                UpdateSelector, "_select_individual_packages",
                return_value=selected,
            ) as mock_individual:
                result = UpdateSelector.interactive_select_by_category(packages)

        assert result == selected
        # Only the kernel package should be passed to individual selection
        mock_individual.assert_called_once_with([kernel])

    def test_category_back_then_pick_loops(self):
        """Back from category selection returns to the menu and loops."""
        pkg = _make_package()
        packages = [pkg]

        # First ask: pick a category, individual selection goes back (None).
        # The loop re-asks; second ask: cancel.
        with patch("questionary.select") as mock_select:
            mock_select.return_value.ask.side_effect = [
                UpdateCategory.USER_APP,
                "cancel",
            ]
            with patch.object(
                UpdateSelector, "_select_individual_packages",
                return_value=None,  # back to category menu
            ):
                result = UpdateSelector.interactive_select_by_category(packages)

        assert result is None
        assert mock_select.return_value.ask.call_count == 2

    def test_back_loops_then_selection_succeeds(self):
        """Back once, then complete a selection on the second pass."""
        pkg = _make_package()
        packages = [pkg]

        with patch("questionary.select") as mock_select:
            mock_select.return_value.ask.side_effect = [
                UpdateCategory.USER_APP,
                UpdateCategory.USER_APP,
            ]
            with patch.object(
                UpdateSelector, "_select_individual_packages",
                side_effect=[None, [pkg]],
            ):
                result = UpdateSelector.interactive_select_by_category(packages)

        assert result == [pkg]
        assert mock_select.return_value.ask.call_count == 2


class TestSelectIndividualPackages:
    """Tests for the checkbox package selection."""

    def test_empty_packages_returns_empty(self):
        result = UpdateSelector._select_individual_packages([])
        assert result == []

    def test_escape_returns_none(self):
        packages = [_make_package()]

        with patch("better_dnf.selector.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = None
            result = UpdateSelector._select_individual_packages(packages)

        assert result is None

    def test_back_option_returns_none(self):
        packages = [_make_package()]

        with patch("better_dnf.selector.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = ["back"]
            result = UpdateSelector._select_individual_packages(packages)

        assert result is None

    def test_back_with_selections_returns_none(self):
        """Back wins even if other packages were toggled."""
        packages = [_make_package()]

        with patch("better_dnf.selector.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = ["back", packages[0]]
            result = UpdateSelector._select_individual_packages(packages)

        assert result is None

    def test_returns_selected_packages(self):
        pkg = _make_package()
        packages = [pkg]

        with patch("better_dnf.selector.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = [pkg]
            result = UpdateSelector._select_individual_packages(packages)

        assert result == [pkg]

    def test_menu_includes_back_option(self):
        packages = [_make_package()]

        with patch("better_dnf.selector.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = [packages[0]]
            UpdateSelector._select_individual_packages(packages)

        choices = mock_checkbox.call_args.kwargs["choices"]
        values = [
            c.value for c in choices
            if isinstance(c, questionary.Choice)
        ]
        assert "back" in values


class TestConfirmUpdate:
    """Tests for the final confirmation prompt."""

    def test_confirm_returns_true(self):
        plan = UpdatePlan(packages=[_make_package()])

        with patch("better_dnf.selector.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = True
            result = UpdateSelector.confirm_update(plan)

        assert result is True

    def test_confirm_returns_false(self):
        plan = UpdatePlan(packages=[_make_package()])

        with patch("better_dnf.selector.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = UpdateSelector.confirm_update(plan)

        assert result is False

    def test_large_plan_shows_warning(self):
        """More than 20 packages triggers the batch-size warning."""
        plan = UpdatePlan(
            packages=[_make_package(f"pkg{i}") for i in range(25)]
        )
        printed = []

        with patch("better_dnf.selector.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = True
            with patch(
                "better_dnf.selector.console.print",
                side_effect=lambda *a, **k: printed.append(a),
            ):
                UpdateSelector.confirm_update(plan)

        text = " ".join(str(a[0]) for a in printed)
        assert "large number of packages" in text

    def test_critical_updates_shown(self):
        plan = UpdatePlan(
            packages=[
                _make_package(
                    "openssl",
                    category=UpdateCategory.SYSTEM,
                    importance=UpdateImportance.CRITICAL,
                )
            ]
        )
        printed = []

        with patch("better_dnf.selector.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = True
            with patch(
                "better_dnf.selector.console.print",
                side_effect=lambda *a, **k: printed.append(a),
            ):
                UpdateSelector.confirm_update(plan)

        text = " ".join(str(a[0]) for a in printed)
        assert "critical" in text
