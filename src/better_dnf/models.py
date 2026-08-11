"""
Data models for package updates and categories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class UpdateCategory(Enum):
    """Categories for package updates."""

    SECURITY = "security"
    KERNEL = "kernel"
    DRIVER = "driver"
    SYSTEM = "system"
    OFFICIAL = "official"
    USER_APP = "user_app"
    OTHER = "other"


class UpdateImportance(Enum):
    """Importance levels for updates."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class UpdateType(Enum):
    """Types of updates from DNF."""

    SECURITY = "security"
    BUGFIX = "bugfix"
    ENHANCEMENT = "enhancement"


@dataclass
class UpdateAdvisory:
    """Advisory information for a package update."""

    advisory_id: str
    update_type: UpdateType
    severity: str | None = None
    description: str | None = None
    cves: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


@dataclass
class PackageUpdate:
    """Represents a single package update."""

    name: str
    arch: str
    old_version: str
    new_version: str
    repository: str
    category: UpdateCategory = UpdateCategory.OTHER
    importance: UpdateImportance = UpdateImportance.UNKNOWN
    update_type: UpdateType | None = None
    advisories: list[UpdateAdvisory] = field(default_factory=list)
    changelog_summary: str | None = None
    size: int | None = None
    installed_date: datetime | None = None

    @property
    def full_name(self) -> str:
        """Get full package name with architecture."""
        return f"{self.name}.{self.arch}"

    @property
    def version_diff(self) -> str:
        """Get version difference string."""
        return f"{self.old_version} -> {self.new_version}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "arch": self.arch,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "repository": self.repository,
            "category": self.category.value,
            "importance": self.importance.value,
            "update_type": self.update_type.value if self.update_type else None,
            "advisories": [
                {
                    "id": adv.advisory_id,
                    "type": adv.update_type.value,
                    "severity": adv.severity,
                    "cves": adv.cves,
                }
                for adv in self.advisories
            ],
            "changelog_summary": self.changelog_summary,
        }


@dataclass
class UpdateSummary:
    """Summary of all available updates."""

    total_packages: int = 0
    by_category: dict[UpdateCategory, int] = field(default_factory=dict)
    by_importance: dict[UpdateImportance, int] = field(default_factory=dict)
    by_type: dict[UpdateType, int] = field(default_factory=dict)
    security_count: int = 0
    kernel_count: int = 0
    driver_count: int = 0
    total_size: int = 0

    @property
    def has_critical(self) -> bool:
        """Check if there are critical updates."""
        return self.by_importance.get(UpdateImportance.CRITICAL, 0) > 0

    @property
    def has_security(self) -> bool:
        """Check if there are security updates."""
        return self.security_count > 0

    @property
    def has_kernel(self) -> bool:
        """Check if there are kernel updates."""
        return self.kernel_count > 0

    @property
    def has_driver(self) -> bool:
        """Check if there are driver updates."""
        return self.driver_count > 0


@dataclass
class UpdatePlan:
    """Represents a plan for applying updates."""

    packages: list[PackageUpdate] = field(default_factory=list)
    snapshot_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def total_packages(self) -> int:
        """Get total number of packages in the plan."""
        return len(self.packages)

    @property
    def total_size(self) -> int:
        """Get total size of packages in bytes."""
        return sum(pkg.size or 0 for pkg in self.packages)

    def add_package(self, package: PackageUpdate) -> None:
        """Add a package to the update plan."""
        self.packages.append(package)

    def remove_package(self, package_name: str) -> bool:
        """Remove a package from the update plan by name."""
        for i, pkg in enumerate(self.packages):
            if pkg.name == package_name:
                self.packages.pop(i)
                return True
        return False

    def get_packages_by_category(self, category: UpdateCategory) -> list[PackageUpdate]:
        """Get packages filtered by category."""
        return [pkg for pkg in self.packages if pkg.category == category]

    def get_packages_by_importance(
        self, importance: UpdateImportance
    ) -> list[PackageUpdate]:
        """Get packages filtered by importance."""
        return [pkg for pkg in self.packages if pkg.importance == importance]
