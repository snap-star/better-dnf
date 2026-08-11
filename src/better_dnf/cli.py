"""
Main CLI interface for Better DNF.
"""

import sys
from typing import Optional, List
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .analyzer import UpdateAnalyzer
from .selector import UpdateSelector
from .snapshot import SnapshotManager
from .updater import UpdateApplier
from .models import UpdateCategory, UpdateImportance

# Create CLI app
app = typer.Typer(
    name="better-dnf",
    help="""🛡️  Better DNF - A smarter package update tool for Fedora

A safer alternative to 'sudo dnf upgrade' that gives you full control
over which packages to update. Perfect for old hardware where blind
updates might cause black screens, freezes, or driver issues.

✨ KEY FEATURES:
  📊 Smart categorization  - Updates grouped by type (security, kernel, drivers, etc.)
  🔍 Importance analysis   - CVE and changelog-based risk assessment
  🎯 Selective updates     - Choose exactly what to install
  📸 Snapshot protection   - Btrfs snapshots for safe rollback
  🚫 No blind upgrades    - Prevents accidental system-breaking updates

🎯 PERFECT FOR:
  • Old hardware that might break with major updates
  • Systems with custom drivers (NVIDIA, AMD, etc.)
  • Servers that need careful update management
  • Anyone who wants control over their system updates

📋 QUICK START:
  better-dnf analyze              # Interactive update analysis
  better-dnf security             # Show security updates
  better-dnf list-updates         # List all available updates
  better-dnf snapshot list        # View system snapshots

🔗 MORE INFO:
  GitHub: https://github.com/snap-star/better-dnf""",
    add_completion=False,
)

console = Console()


@app.command()
def analyze(
    no_snapshot: bool = typer.Option(
        False,
        "--no-snapshot",
        "-n",
        help="Skip creating a snapshot before updates",
    ),
    strategy: Optional[str] = typer.Option(
        None,
        "--strategy",
        "-s",
        help="""🎯 Update strategy (skip interactive menu).

STRATEGIES:
  security     Only security patches (recommended for servers)
  kernel_drivers Kernel and driver updates (review carefully)
  official     Official Fedora repository packages only
  user_apps    User-installed applications only
  custom       Manual selection with category browsing
  all          Update everything (⚠️  not for old hardware)

💡 RECOMMENDATIONS:
  • Start with 'security' for critical fixes
  • Use 'user_apps' for application updates
  • Avoid 'all' on systems with custom drivers
  • Use 'custom' for fine-grained control

Example: better-dnf analyze -s security""",
    ),
) -> None:
    """
    🔍 Analyze available updates and help you choose what to install.
    
    This is the main command for safely updating your system.
    It provides a complete analysis workflow:
    
    📋 WORKFLOW:
    1. Fetch available updates from DNF repositories
    2. Categorize by type (security, kernel, drivers, system, apps)
    3. Analyze importance using changelogs and CVE databases
    4. Display risk assessment with recommendations
    5. Let you select packages interactively with preview
    6. Create pre/post snapshots for safe rollback
    7. Apply updates with progress tracking
    
    🎯 UPDATE STRATEGIES:
    ─────────────────────────────────────────────────
    security       Only security patches (critical for servers)
    kernel_drivers Kernel and driver updates (review carefully)
    official       Official Fedora repository packages only
    user_apps      User-installed applications only
    custom         Manual selection with category browsing
    all            Update everything (not recommended for old HW)
    ─────────────────────────────────────────────────
    
    📸 SNAPSHOT PROTECTION:
    By default, creates btrfs snapshots before/after updates.
    If something breaks, rollback with: better-dnf snapshot rollback <id>
    
    💡 TIPS:
    • Start with 'security' strategy for critical updates
    • Use 'custom' to cherry-pick specific packages
    • Add '-n' to skip snapshot creation (faster)
    • For old hardware, avoid 'kernel_drivers' unless needed
    
    Examples:
      better-dnf analyze                    # Interactive mode
      better-dnf analyze -s security        # Security updates only
      better-dnf analyze -s kernel_drivers  # Kernel & drivers only
      better-dnf analyze -s user_apps       # User apps only
      better-dnf analyze -n                 # Skip snapshot creation
      better-dnf analyze -s custom          # Custom selection
    """
    try:
        console.print(
            Panel(
                "[bold cyan]🔍 Better DNF[/bold cyan]\n"
                "[dim]Analyzing available updates...[/dim]",
                title="Starting Analysis",
                border_style="cyan",
            )
        )
        
        # Initialize analyzer
        analyzer = UpdateAnalyzer()
        
        # Analyze updates (fast mode - skip download sizes initially)
        with console.status("[bold green]Fetching updates...[/bold green]"):
            packages = analyzer.analyze_updates(fetch_sizes=False)
        
        if not packages:
            console.print("[yellow]No updates available. Your system is up to date![/yellow]")
            return
        
        # Display summary
        console.print("\n[bold cyan]📊 Update Summary[/bold cyan]")
        UpdateSelector.display_update_summary(packages)
        
        # Get risk assessment
        risk = analyzer.get_risk_assessment()
        
        # Display risk assessment
        risk_color = {
            "low": "green",
            "medium": "yellow",
            "high": "red",
        }.get(risk["risk_level"], "white")
        
        console.print(
            Panel(
                f"[{risk_color}]Risk Level: {risk['risk_level'].upper()}[/{risk_color}]\n"
                f"[dim]{risk['recommendation']}[/dim]\n\n"
                f"[bold]Risk Factors:[/bold]\n" +
                "\n".join(f"• {factor}" for factor in risk["risk_factors"]),
                title="⚠️  Risk Assessment",
                border_style=risk_color,
            )
        )
        
        # Select update strategy with loop for back navigation
        selected_packages = None
        
        # If strategy is provided via CLI flag, don't loop back to interactive menu
        if strategy:
            selected_strategy = strategy
            if selected_strategy == "custom":
                result = UpdateSelector.interactive_select_by_category(packages)
                if result is None:
                    console.print("[yellow]Operation cancelled by user.[/yellow]")
                    return
                selected_packages = result
            elif selected_strategy == "all":
                selected_packages = packages
            elif selected_strategy == "security":
                selected_packages = analyzer.get_security_updates()
            elif selected_strategy == "kernel_drivers":
                selected_packages = (
                    analyzer.get_kernel_updates() +
                    analyzer.get_driver_updates()
                )
            elif selected_strategy == "official":
                selected_packages = analyzer.get_packages_by_category(UpdateCategory.OFFICIAL)
            elif selected_strategy == "user_apps":
                selected_packages = analyzer.get_packages_by_category(UpdateCategory.USER_APP)
            else:
                console.print(f"[red]Unknown strategy: {selected_strategy}[/red]")
                return
        else:
            # Interactive mode - allow looping back
            while selected_packages is None:
                selected_strategy = UpdateSelector.select_update_strategy()
                
                if selected_strategy is None or selected_strategy == "cancel":
                    console.print("[yellow]Operation cancelled by user.[/yellow]")
                    return
                
                # Filter packages based on strategy
                if selected_strategy == "all":
                    selected_packages = packages
                elif selected_strategy == "security":
                    selected_packages = analyzer.get_security_updates()
                elif selected_strategy == "kernel_drivers":
                    selected_packages = (
                        analyzer.get_kernel_updates() +
                        analyzer.get_driver_updates()
                    )
                elif selected_strategy == "official":
                    selected_packages = analyzer.get_packages_by_category(UpdateCategory.OFFICIAL)
                elif selected_strategy == "user_apps":
                    selected_packages = analyzer.get_packages_by_category(UpdateCategory.USER_APP)
                elif selected_strategy == "custom":
                    result = UpdateSelector.interactive_select_by_category(packages)
                    if result is None:
                        # User went back to strategy menu
                        continue
                    selected_packages = result
                else:
                    console.print(f"[red]Unknown strategy: {selected_strategy}[/red]")
                    return
        
        if not selected_packages:
            console.print("[yellow]No packages selected for update.[/yellow]")
            return
        
        # Fetch download sizes for selected packages only (lazy loading)
        with console.status("[bold green]Fetching download sizes...[/bold green]"):
            analyzer.fetch_download_sizes(selected_packages)
        
        # Create update plan
        plan = UpdateSelector.create_update_plan(selected_packages)
        
        # Confirm update
        if not UpdateSelector.confirm_update(plan):
            console.print("[yellow]Update cancelled by user.[/yellow]")
            return
        
        # Apply updates
        console.print("\n[bold cyan]🚀 Applying Updates...[/bold cyan]")
        success, message = UpdateApplier.apply_updates(
            plan,
            create_snapshot=not no_snapshot,
        )
        
        if success:
            console.print(
                Panel(
                    f"[green]✓ {message}[/green]",
                    title="Update Complete",
                    border_style="green",
                )
            )
            
            # Show rollback info if snapshot was created
            if plan.snapshot_id:
                console.print(
                    f"\n[dim]Snapshot ID: {plan.snapshot_id}[/dim]\n"
                    f"[dim]To rollback: better-dnf snapshot rollback {plan.snapshot_id}[/dim]"
                )
        else:
            console.print(
                Panel(
                    f"[red]✗ {message}[/red]",
                    title="Update Failed",
                    border_style="red",
                )
            )
            
            # Offer rollback
            from questionary import confirm
            if confirm("Would you like to rollback using the snapshot?", default=False).ask():
                success, rollback_msg = UpdateApplier.rollback_updates(plan)
                if success:
                    console.print(f"[green]✓ {rollback_msg}[/green]")
                else:
                    console.print(f"[red]✗ {rollback_msg}[/red]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        raise typer.Exit()
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command("list-updates")
def list_updates(
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="""📊 Filter by update category.

CATEGORIES:
  security  Security vulnerability patches (CVE fixes)
  kernel    Linux kernel and related packages
  driver    Hardware drivers (NVIDIA, Mesa, etc.)
  system    Core system components (systemd, glibc)
  official  Standard Fedora repository packages
  user_app  User-installed applications
  other     Miscellaneous packages

Example: better-dnf list-updates -c kernel""",
    ),
    importance: Optional[str] = typer.Option(
        None,
        "--importance",
        "-i",
        help="""🎯 Filter by importance level.

LEVELS:
  critical  Must install immediately (active exploits)
  high      Should install soon (crash fixes, stability)
  medium    Recommended (bug fixes, improvements)
  low       Optional (cosmetic, minor fixes)

💡 TIP: Combine with -c for focused updates
Example: better-dnf list-updates -c security -i critical""",
    ),
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show all updates without filtering",
    ),
) -> None:
    """
    📋 List available updates with optional filtering.
    
    Displays a formatted table of available updates showing:
    • Package name and current/new versions
    • Update category (security, kernel, driver, system, etc.)
    • Importance level (critical, high, medium, low)
    • Risk assessment for each package
    
    📊 CATEGORIES:
    ─────────────────────────────────────────────────
    security  Security vulnerability patches (CVE fixes)
    kernel    Linux kernel and related packages
    driver    Hardware drivers (NVIDIA, Mesa, etc.)
    system    Core system components (systemd, glibc, etc.)
    official  Standard Fedora repository packages
    user_app  User-installed applications
    other     Miscellaneous packages
    ─────────────────────────────────────────────────
    
    🎯 IMPORTANCE LEVELS:
    ─────────────────────────────────────────────────
    critical  Must install immediately (active exploits)
    high      Should install soon (crash fixes, stability)
    medium    Recommended (bug fixes, improvements)
    low       Optional (cosmetic, minor fixes)
    ─────────────────────────────────────────────────
    
    💡 TIPS:
    • Combine filters: -c security -i critical
    • Use --all to see everything at once
    • Run without filters to see grouped categories
    
    Examples:
      better-dnf list-updates                    # Show all updates
      better-dnf list-updates -c kernel          # Kernel updates only
      better-dnf list-updates -c driver          # Driver updates only
      better-dnf list-updates -i critical        # Critical updates only
      better-dnf list-updates -c security -i high # Security + High priority
      better-dnf list-updates -c user_app        # User applications only
    """
    try:
        console.print("[bold cyan]📋 Listing Available Updates[/bold cyan]\n")
        
        # Initialize analyzer
        analyzer = UpdateAnalyzer()
        
        # Analyze updates
        with console.status("[bold green]Fetching updates...[/bold green]"):
            packages = analyzer.analyze_updates()
        
        if not packages:
            console.print("[yellow]No updates available.[/yellow]")
            return
        
        # Apply filters
        if category:
            try:
                cat_enum = UpdateCategory(category)
                packages = [p for p in packages if p.category == cat_enum]
            except ValueError:
                console.print(f"[red]Invalid category: {category}[/red]")
                return
        
        if importance:
            try:
                imp_enum = UpdateImportance(importance)
                packages = [p for p in packages if p.importance == imp_enum]
            except ValueError:
                console.print(f"[red]Invalid importance: {importance}[/red]")
                return
        
        if not packages:
            console.print("[yellow]No updates match the specified filters.[/yellow]")
            return
        
        # Display packages
        if category:
            try:
                cat_enum = UpdateCategory(category)
                UpdateSelector.display_packages_by_category(packages, cat_enum)
            except ValueError:
                # Display all
                for cat in UpdateCategory:
                    cat_packages = [p for p in packages if p.category == cat]
                    if cat_packages:
                        UpdateSelector.display_packages_by_category(cat_packages, cat)
        else:
            # Group by category
            for cat in UpdateCategory:
                cat_packages = [p for p in packages if p.category == cat]
                if cat_packages:
                    UpdateSelector.display_packages_by_category(cat_packages, cat)
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        raise typer.Exit()
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def security(
    apply: bool = typer.Option(
        False,
        "--apply",
        "-a",
        help="Apply security updates after listing",
    ),
) -> None:
    """
    🔒 Show and optionally apply security updates only.
    
    Security updates fix known vulnerabilities (CVEs) and should
    be applied promptly to protect your system from exploits.
    
    🛡️  WHAT ARE SECURITY UPDATES?
    ─────────────────────────────────────────────────
    • Fixes for CVE (Common Vulnerabilities and Exposures)
    • Patches for actively exploited vulnerabilities
    • Critical fixes for authentication, permissions, etc.
    • Kernel security patches
    ─────────────────────────────────────────────────
    
    📋 WORKFLOW:
    1. Fetch and display all available security updates
    2. Show importance levels (critical, high, medium)
    3. Create snapshot before applying (with -a flag)
    4. Apply updates with confirmation
    5. Create post-update snapshot for rollback
    
    ⚠️  RECOMMENDATION:
    Apply security updates regularly! Critical vulnerabilities
    can be exploited within hours of disclosure.
    
    💡 TIPS:
    • Run 'better-dnf security' weekly to check for updates
    • Use '-a' flag to apply immediately after listing
    • Security updates are generally safe to apply
    • Check 'better-dnf history' after applying
    
    Examples:
      better-dnf security        # List security updates
      better-dnf security -a     # List and apply security updates
    """
    try:
        console.print("[bold red]🔒 Security Updates[/bold red]\n")
        
        # Initialize analyzer
        analyzer = UpdateAnalyzer()
        
        # Analyze updates (fast mode - skip download sizes initially)
        with console.status("[bold green]Fetching security updates...[/bold green]"):
            packages = analyzer.analyze_updates(fetch_sizes=False)
        
        security_packages = analyzer.get_security_updates()
        
        if not security_packages:
            console.print("[green]No security updates available.[/green]")
            return
        
        # Display security updates
        UpdateSelector.display_packages_by_category(security_packages, UpdateCategory.SECURITY)
        
        if apply:
            # Fetch download sizes for selected packages only
            with console.status("[bold green]Fetching download sizes...[/bold green]"):
                analyzer.fetch_download_sizes(security_packages)
            
            # Create update plan
            plan = UpdateSelector.create_update_plan(security_packages)
            
            if UpdateSelector.confirm_update(plan):
                success, message = UpdateApplier.apply_updates(plan)
                if success:
                    console.print(f"[green]✓ {message}[/green]")
                else:
                    console.print(f"[red]✗ {message}[/red]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        raise typer.Exit()
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def snapshot(
    action: str = typer.Argument(
        help="""Action to perform:

  create   - Create a new pre-update snapshot
  list     - List all available snapshots
  rollback - Rollback to a specific snapshot (requires snapshot-id)"""
    ),
    snapshot_id: Optional[str] = typer.Argument(
        None,
        help="Snapshot ID for rollback (required for 'rollback' action)",
    ),
) -> None:
    """
    📸 Manage btrfs snapshots for safe system recovery.
    
    Snapshots are point-in-time backups of your system that allow
    you to restore to a working state if an update causes problems.
    
    📸 SNAPSHOT TYPES:
    ─────────────────────────────────────────────────
    pre   Created BEFORE an update (system state before changes)
    post  Created AFTER an update (system state after changes)
    single  Standalone snapshot (created by timeline/manual)
    ─────────────────────────────────────────────────
    
    🔄 PRE/POST WORKFLOW:
    1. 'pre' snapshot = System state BEFORE update
    2. Apply update
    3. 'post' snapshot = System state AFTER update
    
    This gives you complete before/after comparison.
    
    💡 COMMON COMMANDS:
    ─────────────────────────────────────────────────
    better-dnf snapshot create              # Create new pre-update snapshot
    better-dnf snapshot list                # View all available snapshots
    better-dnf snapshot rollback <id>       # Restore to specific snapshot
    ─────────────────────────────────────────────────
    
    ⚠️  IMPORTANT NOTES:
    • Requires sudo privileges for snapshot operations
    • Rollback will restore entire system state
    • Timeline snapshots are created automatically by snapper
    • Keep important snapshots (like before major updates)
    
    🔧 SNAPPER vs BETTER-DNF:
    • Better-dnf creates 'pre' snapshots before updates
    • Snapper creates 'post' snapshots after updates
    • Both work together for complete protection
    
    Examples:
      better-dnf snapshot create           # Create new snapshot
      better-dnf snapshot list             # List all snapshots
      better-dnf snapshot rollback 307     # Rollback to snapshot #307
    """
    try:
        if action == "create":
            console.print("[bold cyan]📸 Creating Snapshot[/bold cyan]\n")
            success, snap_id, message = SnapshotManager.create_snapshot()
            if success:
                console.print(f"[green]✓ {message}[/green]")
            else:
                console.print(f"[red]✗ {message}[/red]")
        
        elif action == "list":
            SnapshotManager.display_snapshots()
        
        elif action == "rollback":
            if not snapshot_id:
                console.print("[red]Please provide a snapshot ID for rollback.[/red]")
                return
            
            success, message = SnapshotManager.rollback_snapshot(snapshot_id)
            if success:
                console.print(f"[green]✓ {message}[/green]")
            else:
                console.print(f"[red]✗ {message}[/red]")
        
        else:
            console.print(f"[red]Unknown action: {action}[/red]")
            console.print("[dim]Available actions: create, list, rollback[/dim]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        raise typer.Exit()
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def history(
    limit: int = typer.Option(
        5,
        "--limit",
        "-l",
        help="Number of recent transactions to show (default: 5)",
    ),
) -> None:
    """
    📜 Show recent DNF update history.
    
    Displays a formatted table of recent DNF transactions to help
    you track what changes were made to your system.
    
    📋 TRANSACTION INFO:
    ─────────────────────────────────────────────────
    ID        Transaction identifier (use with 'dnf history undo')
    Date      When the transaction occurred
    Action    What was done (install, update, remove)
    Packages  Number of packages affected
    ─────────────────────────────────────────────────
    
    🔄 UNDOING UPDATES:
    If an update caused problems, you can undo it:
      sudo dnf history undo <transaction-id>
    
    💡 TIPS:
    • Use this to verify recent better-dnf operations
    • Check history before rolling back to identify issues
    • Default shows 5 recent transactions
    • Increase with -l flag for more history
    
    Examples:
      better-dnf history          # Show last 5 transactions
      better-dnf history -l 10    # Show last 10 transactions
      better-dnf history -l 20    # Show last 20 transactions
    """
    try:
        console.print("[bold cyan]📜 Update History[/bold cyan]\n")
        
        transactions = UpdateApplier.get_update_history(limit)
        
        if not transactions:
            console.print("[dim]No update history found.[/dim]")
            return
        
        table = Table(
            title="Recent Transactions",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("ID", style="bold")
        table.add_column("Date")
        table.add_column("Action")
        table.add_column("Packages")
        
        for tx in transactions:
            table.add_row(
                tx["id"],
                tx["date"],
                tx["action"],
                tx["packages"],
            )
        
        console.print(table)
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        raise typer.Exit()
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """
    ℹ️  Show version information.
    
    Displays the current version of better-dnf.
    Useful for bug reports and checking for updates.
    
    Example: better-dnf version
    """
    from . import __version__
    console.print(f"[bold cyan]Better DNF[/bold cyan] v{__version__}")


if __name__ == "__main__":
    app()