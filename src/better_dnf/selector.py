"""
Interactive selection interface for package updates.
"""

from __future__ import annotations

from typing import ClassVar

import questionary
from questionary import checkbox, confirm, select
from rich import box
from rich.console import Console
from rich.table import Table

from .models import (
    PackageUpdate,
    UpdateCategory,
    UpdateImportance,
    UpdatePlan,
    UpdateType,
)

console = Console()


class UpdateSelector:
    """Interactive selector for choosing which updates to apply."""

    # Category display names and colors
    CATEGORY_DISPLAY: ClassVar[dict[UpdateCategory, tuple[str, str]]] = {
        UpdateCategory.SECURITY: ("🔒 Security", "red"),
        UpdateCategory.KERNEL: ("🐧 Kernel", "yellow"),
        UpdateCategory.DRIVER: ("🔧 Drivers", "magenta"),
        UpdateCategory.SYSTEM: ("⚙️  System", "blue"),
        UpdateCategory.OFFICIAL: ("📦 Official", "green"),
        UpdateCategory.USER_APP: ("📱 User Apps", "cyan"),
        UpdateCategory.OTHER: ("❓ Other", "white"),
    }

    # Importance display names and colors
    IMPORTANCE_DISPLAY: ClassVar[dict[UpdateImportance, tuple[str, str]]] = {
        UpdateImportance.CRITICAL: ("🔴 Critical", "red bold"),
        UpdateImportance.HIGH: ("🟠 High", "yellow"),
        UpdateImportance.MEDIUM: ("🟡 Medium", "cyan"),
        UpdateImportance.LOW: ("🟢 Low", "green"),
        UpdateImportance.UNKNOWN: ("⚪ Unknown", "dim"),
    }

    @classmethod
    def display_update_summary(cls, packages: list[PackageUpdate]) -> None:
        """
        Display a summary of available updates.

        Args:
            packages: List of PackageUpdate objects
        """
        # Count by category
        category_counts: dict[UpdateCategory, int] = {}
        importance_counts: dict[UpdateImportance, int] = {}

        for pkg in packages:
            category_counts[pkg.category] = category_counts.get(pkg.category, 0) + 1
            importance_counts[pkg.importance] = (
                importance_counts.get(pkg.importance, 0) + 1
            )

        # Create summary table
        table = Table(
            title="📋 Update Summary",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Category", style="bold")
        table.add_column("Count", justify="right")
        table.add_column("Status", justify="center")

        # Add rows
        for category in UpdateCategory:
            if category in category_counts:
                display_name, color = cls.CATEGORY_DISPLAY[category]
                count = category_counts[category]

                # Determine status indicator
                if category == UpdateCategory.SECURITY:
                    status = "⚠️  Recommended"
                elif (
                    category == UpdateCategory.KERNEL
                    or category == UpdateCategory.DRIVER
                ):
                    status = "⚠️  Review"
                else:
                    status = "✅ Safe"

                table.add_row(
                    f"[{color}]{display_name}[/{color}]",
                    str(count),
                    status,
                )

        console.print(table)

        # Add importance summary
        console.print("\n[bold]Update Importance:[/bold]")
        for importance in UpdateImportance:
            if importance in importance_counts:
                display_name, color = cls.IMPORTANCE_DISPLAY[importance]
                count = importance_counts[importance]
                console.print(f"  [{color}]{display_name}[/{color}]: {count}")

    @classmethod
    def display_packages_by_category(
        cls,
        packages: list[PackageUpdate],
        category: UpdateCategory,
        max_display: int = 20,
    ) -> None:
        """
        Display packages filtered by category or update_type.

        Args:
            packages: List of PackageUpdate objects
            category: Category to filter by
            max_display: Maximum number of packages to display
        """
        # For SECURITY category, filter by update_type instead
        if category == UpdateCategory.SECURITY:
            filtered = [p for p in packages if p.update_type == UpdateType.SECURITY]
        else:
            filtered = [p for p in packages if p.category == category]

        if not filtered:
            console.print(f"[dim]No packages in category: {category.value}[/dim]")
            return

        display_name, color = cls.CATEGORY_DISPLAY.get(category, ("Unknown", "white"))

        # Create table
        table = Table(
            title=f"{display_name} Updates ({len(filtered)} packages)",
            box=box.SIMPLE,
            show_header=True,
            header_style=f"bold {color}",
        )
        table.add_column("Package", style="bold")
        table.add_column("Current Version", justify="right")
        table.add_column("New Version", justify="right", style="green")
        table.add_column("Importance", justify="center")

        # Sort by importance
        importance_order = {
            UpdateImportance.CRITICAL: 0,
            UpdateImportance.HIGH: 1,
            UpdateImportance.MEDIUM: 2,
            UpdateImportance.LOW: 3,
            UpdateImportance.UNKNOWN: 4,
        }
        sorted_packages = sorted(
            filtered,
            key=lambda p: importance_order.get(p.importance, 4),
        )

        # Display packages
        for i, pkg in enumerate(sorted_packages[:max_display]):
            importance_display, importance_color = cls.IMPORTANCE_DISPLAY[
                pkg.importance
            ]

            table.add_row(
                pkg.name,
                pkg.old_version,
                pkg.new_version,
                f"[{importance_color}]{importance_display}[/{importance_color}]",
            )

        if len(filtered) > max_display:
            table.add_row(
                f"[dim]... and {len(filtered) - max_display} more packages[/dim]",
                "",
                "",
                "",
            )

        console.print(table)

    @classmethod
    def interactive_select_by_category(
        cls,
        packages: list[PackageUpdate],
    ) -> list[PackageUpdate] | None:
        """
        Interactively select packages by category.

        Args:
            packages: List of PackageUpdate objects

        Returns:
            List of selected PackageUpdate objects, or None to go back to strategy menu
        """
        # Get unique categories present in packages
        categories = list({pkg.category for pkg in packages})

        if not categories:
            console.print("[yellow]No packages to select from.[/yellow]")
            return []

        while True:
            # Create choices for category selection
            choices = []
            for category in categories:
                display_name, _color = cls.CATEGORY_DISPLAY[category]
                count = len([p for p in packages if p.category == category])
                choices.append(
                    questionary.Choice(
                        title=f"{display_name} ({count} packages)",
                        value=category,
                    )
                )

            # Add special choices
            choices.append(questionary.Separator())
            choices.append(
                questionary.Choice(
                    title="📋 Show All Categories",
                    value="all",
                )
            )
            choices.append(
                questionary.Choice(
                    title="✅ Select All Packages",
                    value="select_all",
                )
            )
            choices.append(questionary.Separator())
            choices.append(
                questionary.Choice(
                    title="⬅️  Back to Strategy Menu",
                    value="back",
                )
            )
            choices.append(
                questionary.Choice(
                    title="❌ Cancel",
                    value="cancel",
                )
            )

            # Prompt user
            selected = questionary.select(
                "Which category would you like to review?",
                choices=choices,
                use_shortcuts=True,
            ).ask()

            if selected is None or selected == "cancel":
                return None

            if selected == "back":
                return None

            if selected == "select_all":
                return cls._select_individual_packages(packages)

            if selected == "all":
                # Show all categories and let user select
                return cls._select_individual_packages(packages)

            # Show packages in selected category
            category_packages = [p for p in packages if p.category == selected]
            result = cls._select_individual_packages(category_packages)
            if result is not None:  # User made a selection
                return result
            # If result is None, user pressed back, loop again

    @classmethod
    def _select_individual_packages(
        cls,
        packages: list[PackageUpdate],
    ) -> list[PackageUpdate] | None:
        """
        Let user select individual packages from a list.

        Args:
            packages: List of PackageUpdate objects

        Returns:
            List of selected PackageUpdate objects, or None to go back to category selection
        """
        if not packages:
            console.print("[yellow]No packages available for selection.[/yellow]")
            return []

        # Sort packages by importance
        importance_order = {
            UpdateImportance.CRITICAL: 0,
            UpdateImportance.HIGH: 1,
            UpdateImportance.MEDIUM: 2,
            UpdateImportance.LOW: 3,
            UpdateImportance.UNKNOWN: 4,
        }
        sorted_packages = sorted(
            packages,
            key=lambda p: importance_order.get(p.importance, 4),
        )

        # Create checkbox choices with back option
        choices = []

        # Add back option at the top
        choices.append(
            questionary.Choice(
                title="⬅️  Back to Category Selection",
                value="back",
                checked=False,
            )
        )
        choices.append(questionary.Separator())

        for pkg in sorted_packages:
            importance_display, _ = cls.IMPORTANCE_DISPLAY[pkg.importance]
            display_text = f"{pkg.name} ({pkg.old_version} → {pkg.new_version}) {importance_display}"

            # Pre-select important updates
            pre_selected = pkg.importance in (
                UpdateImportance.CRITICAL,
                UpdateImportance.HIGH,
            )

            choices.append(
                questionary.Choice(
                    title=display_text,
                    value=pkg,
                    checked=pre_selected,
                )
            )

        # Prompt user for selection
        selected = checkbox(
            "Select packages to update (use arrow keys, space to toggle, enter to confirm):",
            choices=choices,
        ).ask()

        if selected is None:
            # User pressed Escape - exit completely
            return None

        if "back" in selected:
            return None  # Signal to go back to category selection

        return selected

    @classmethod
    def create_update_plan(
        cls,
        packages: list[PackageUpdate],
    ) -> UpdatePlan:
        """
        Create an update plan from selected packages.

        Args:
            packages: List of selected PackageUpdate objects

        Returns:
            UpdatePlan object
        """
        plan = UpdatePlan(packages=packages)

        # Display plan summary
        cls._display_plan_summary(plan)

        return plan

    @classmethod
    def _display_plan_summary(cls, plan: UpdatePlan) -> None:
        """
        Display a summary of the update plan.

        Args:
            plan: UpdatePlan to display
        """
        console.print("\n[bold cyan]📝 Update Plan Summary[/bold cyan]")

        # Create summary table
        table = Table(box=box.SIMPLE)
        table.add_column("Metric", style="bold")
        table.add_column("Value")

        table.add_row("Total Packages", str(plan.total_packages))

        # Size in human readable format
        size_mb = plan.total_size / (1024 * 1024)
        table.add_row("Download Size", f"{size_mb:.2f} MB")

        # Count by importance
        critical = len(plan.get_packages_by_importance(UpdateImportance.CRITICAL))
        high = len(plan.get_packages_by_importance(UpdateImportance.HIGH))
        medium = len(plan.get_packages_by_importance(UpdateImportance.MEDIUM))
        low = len(plan.get_packages_by_importance(UpdateImportance.LOW))

        table.add_row(
            "By Importance",
            f"🔴 {critical} Critical | 🟠 {high} High | 🟡 {medium} Medium | 🟢 {low} Low",
        )

        # Count by category
        categories = {}
        for pkg in plan.packages:
            categories[pkg.category] = categories.get(pkg.category, 0) + 1

        category_str = " | ".join(
            f"{cls.CATEGORY_DISPLAY[cat][0]}: {count}"
            for cat, count in categories.items()
        )
        table.add_row("By Category", category_str)

        console.print(table)

    @classmethod
    def display_package_preview(
        cls, packages: list[PackageUpdate], max_display: int = 30
    ) -> None:
        """
        Display a preview table of packages to be updated.

        Args:
            packages: List of PackageUpdate objects
            max_display: Maximum number of packages to display
        """
        if not packages:
            return

        console.print("\n[bold cyan]📦 Packages to be Updated[/bold cyan]")

        # Create preview table
        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            title=f"Showing {min(len(packages), max_display)} of {len(packages)} packages",
        )
        table.add_column("Package", style="bold", no_wrap=True)
        table.add_column("Current Version", justify="right", style="dim")
        table.add_column("New Version", justify="right", style="green")
        table.add_column("Importance", justify="center")
        table.add_column("Category", justify="center")

        # Sort packages by importance then category
        importance_order = {
            UpdateImportance.CRITICAL: 0,
            UpdateImportance.HIGH: 1,
            UpdateImportance.MEDIUM: 2,
            UpdateImportance.LOW: 3,
            UpdateImportance.UNKNOWN: 4,
        }
        sorted_packages = sorted(
            packages,
            key=lambda p: (importance_order.get(p.importance, 4), p.category.value),
        )

        # Display packages
        for pkg in sorted_packages[:max_display]:
            importance_display, importance_color = cls.IMPORTANCE_DISPLAY[
                pkg.importance
            ]
            category_display, category_color = cls.CATEGORY_DISPLAY.get(
                pkg.category, ("Unknown", "white")
            )

            # Truncate long package names
            pkg_name = pkg.name[:28] + "..." if len(pkg.name) > 30 else pkg.name

            table.add_row(
                pkg_name,
                pkg.old_version,
                pkg.new_version,
                f"[{importance_color}]{importance_display}[/{importance_color}]",
                f"[{category_color}]{category_display}[/{category_color}]",
            )

        if len(packages) > max_display:
            console.print(
                f"\n[dim]... and {len(packages) - max_display} more packages (use 'better-dnf list-updates' to see all)[/dim]"
            )

        console.print(table)

    @classmethod
    def confirm_update(cls, plan: UpdatePlan) -> bool:
        """
        Confirm with user before applying updates.

        Args:
            plan: UpdatePlan to confirm

        Returns:
            True if user confirms, False otherwise
        """
        # Display warnings if needed
        if plan.total_packages > 20:
            console.print(
                "[yellow]⚠️  You are about to update a large number of packages. "
                "Consider updating in smaller batches.[/yellow]"
            )

        critical_count = len(plan.get_packages_by_importance(UpdateImportance.CRITICAL))
        if critical_count > 0:
            console.print(
                f"[red]🔒 {critical_count} critical security updates included.[/red]"
            )

        # Display package preview table
        cls.display_package_preview(plan.packages)

        # Final confirmation
        return confirm(
            f"\nReady to update {plan.total_packages} packages?",
            default=False,
        ).ask()

    @classmethod
    def select_update_strategy(cls) -> str:
        """
        Let user choose an update strategy.

        Returns:
            Selected strategy string, or None if cancelled
        """
        choices = [
            questionary.Choice(
                title="🔒 Security Updates Only",
                value="security",
                description="Install only security-related updates",
            ),
            questionary.Choice(
                title="🐧 Kernel & Drivers Only",
                value="kernel_drivers",
                description="Install kernel and driver updates (use with caution)",
            ),
            questionary.Choice(
                title="📦 Official Fedora Packages Only",
                value="official",
                description="Install only official Fedora repository updates",
            ),
            questionary.Choice(
                title="📱 User Applications Only",
                value="user_apps",
                description="Install only user-installed application updates",
            ),
            questionary.Choice(
                title="🎯 Custom Selection",
                value="custom",
                description="Manually select which packages to update",
            ),
            questionary.Choice(
                title="✅ Update All",
                value="all",
                description="Update all available packages (not recommended for old hardware)",
            ),
            questionary.Separator(),
            questionary.Choice(
                title="❌ Cancel",
                value="cancel",
            ),
        ]

        return select(
            "How would you like to select updates?",
            choices=choices,
        ).ask()
