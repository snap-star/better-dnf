"""
Better DNF - A smarter DNF update tool for Fedora.

This tool helps Fedora users safely manage system updates by:
- Categorizing updates by type (security, kernel, drivers, etc.)
- Analyzing update importance using changelogs and CVEs
- Providing interactive selection for selective updates
- Creating btrfs snapshots before updates for easy rollback
"""

__version__ = "0.1.0"
__author__ = "snap-star"

from better_dnf.models import PackageUpdate, UpdateCategory, UpdateImportance
from better_dnf.analyzer import UpdateAnalyzer
from better_dnf.selector import UpdateSelector

__all__ = [
    "PackageUpdate",
    "UpdateCategory", 
    "UpdateImportance",
    "UpdateAnalyzer",
    "UpdateSelector",
]