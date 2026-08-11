"""
AI-powered analyzer for determining update importance.
"""

from __future__ import annotations

import re
from typing import ClassVar

from .models import (
    PackageUpdate,
    UpdateCategory,
    UpdateImportance,
    UpdateSummary,
    UpdateType,
)
from .parser import DNFParser


class ImportanceAnalyzer:
    """Analyzes package updates to determine their importance."""

    # Patterns indicating critical importance
    CRITICAL_PATTERNS: ClassVar[list[str]] = [
        r"cve-\d{4}-\d+",  # CVE references
        r"remote code execution",
        r"privilege escalation",
        r"arbitrary code",
        r"buffer overflow",
        r"security fix",
        r"vulnerability",
        r"exploit",
        r"backdoor",
    ]

    # Patterns indicating high importance
    HIGH_PATTERNS: ClassVar[list[str]] = [
        r"crash fix",
        r"data loss",
        r"data corruption",
        r"system hang",
        r"boot failure",
        r"regression fix",
        r"breaking change",
        r"incompatible",
        r"deprecated",
    ]

    # Patterns indicating medium importance
    MEDIUM_PATTERNS: ClassVar[list[str]] = [
        r"bug fix",
        r"bugfix",
        r"issue fix",
        r"problem fix",
        r"stability",
        r"compatibility",
        r"improvement",
        r"update",
    ]

    # Patterns indicating low importance
    LOW_PATTERNS: ClassVar[list[str]] = [
        r"cosmetic",
        r"typo",
        r"documentation",
        r"whitespace",
        r"translation",
        r"linting",
        r"formatting",
    ]

    # Category-based importance multipliers
    CATEGORY_MULTIPLIERS: ClassVar[dict[UpdateCategory, float]] = {
        UpdateCategory.KERNEL: 1.5,  # Kernel updates are more critical
        UpdateCategory.DRIVER: 1.3,  # Driver updates can affect stability
        UpdateCategory.SECURITY: 1.4,  # Security updates are important
        UpdateCategory.SYSTEM: 1.2,  # System updates are important
        UpdateCategory.OFFICIAL: 1.0,  # Official packages are standard
        UpdateCategory.USER_APP: 0.8,  # User apps are less critical
        UpdateCategory.OTHER: 0.9,  # Other packages are less critical
    }

    # Type-based importance multipliers
    TYPE_MULTIPLIERS: ClassVar[dict[UpdateType, float]] = {
        UpdateType.SECURITY: 1.5,  # Security updates are critical
        UpdateType.BUGFIX: 1.1,  # Bug fixes are important
        UpdateType.ENHANCEMENT: 0.9,  # Enhancements are less critical
    }

    @classmethod
    def analyze_importance(cls, package: PackageUpdate) -> UpdateImportance:
        """
        Analyze and determine the importance of a package update.

        Args:
            package: PackageUpdate to analyze

        Returns:
            UpdateImportance level
        """
        # Start with base score
        score = 50.0  # Medium base

        # Apply category multiplier
        category_multiplier = cls.CATEGORY_MULTIPLIERS.get(package.category, 1.0)
        score *= category_multiplier

        # Apply type multiplier
        if package.update_type:
            type_multiplier = cls.TYPE_MULTIPLIERS.get(package.update_type, 1.0)
            score *= type_multiplier

        # Check for critical patterns in advisories and changelog
        text_to_check = cls._get_analysis_text(package)

        # Check critical patterns
        for pattern in cls.CRITICAL_PATTERNS:
            if re.search(pattern, text_to_check, re.IGNORECASE):
                score += 30.0

        # Check high patterns
        for pattern in cls.HIGH_PATTERNS:
            if re.search(pattern, text_to_check, re.IGNORECASE):
                score += 20.0

        # Check medium patterns
        for pattern in cls.MEDIUM_PATTERNS:
            if re.search(pattern, text_to_check, re.IGNORECASE):
                score += 10.0

        # Check low patterns (these reduce importance)
        for pattern in cls.LOW_PATTERNS:
            if re.search(pattern, text_to_check, re.IGNORECASE):
                score -= 10.0

        # Consider version jump size
        version_diff = cls._calculate_version_diff(package)
        if version_diff > 10:
            score += 15.0  # Major version jumps are more important
        elif version_diff > 5:
            score += 10.0
        elif version_diff > 2:
            score += 5.0

        # Map score to importance level
        if score >= 80:
            return UpdateImportance.CRITICAL
        elif score >= 65:
            return UpdateImportance.HIGH
        elif score >= 45:
            return UpdateImportance.MEDIUM
        elif score >= 30:
            return UpdateImportance.LOW
        else:
            return UpdateImportance.UNKNOWN

    @classmethod
    def _get_analysis_text(cls, package: PackageUpdate) -> str:
        """
        Get text to analyze from package metadata.

        Args:
            package: PackageUpdate to extract text from

        Returns:
            Combined text for analysis
        """
        texts = []

        # Add changelog summary if available
        if package.changelog_summary:
            texts.append(package.changelog_summary)

        # Add advisory descriptions
        for advisory in package.advisories:
            if advisory.description:
                texts.append(advisory.description)
            if advisory.severity:
                texts.append(advisory.severity)
            # Add CVE IDs as they indicate security importance
            texts.extend(advisory.cves)

        # Add package name and repository for context
        texts.append(package.name)
        texts.append(package.repository or "")

        return " ".join(texts)

    @classmethod
    def _calculate_version_diff(cls, package: PackageUpdate) -> int:
        """
        Calculate a numeric difference between old and new versions.

        Args:
            package: PackageUpdate with version info

        Returns:
            Numeric difference (higher means bigger jump)
        """
        # Simple heuristic: count dots and segments
        # This is a rough approximation
        old_parts = package.old_version.split(".")
        new_parts = package.new_version.split(".")

        diff = 0
        for i in range(min(len(old_parts), len(new_parts))):
            try:
                old_num = int(re.sub(r"[^0-9]", "", old_parts[i]) or "0")
                new_num = int(re.sub(r"[^0-9]", "", new_parts[i]) or "0")
                diff += abs(new_num - old_num)
            except (ValueError, IndexError):
                continue

        return diff


class UpdateAnalyzer:
    """Main analyzer class for processing package updates."""

    def __init__(self):
        """Initialize the analyzer."""
        self.packages: list[PackageUpdate] = []
        self.summary: UpdateSummary | None = None

    def analyze_updates(self, fetch_sizes: bool = True) -> list[PackageUpdate]:
        """
        Fetch and analyze all available updates.

        Args:
            fetch_sizes: Whether to fetch download sizes (faster if False)

        Returns:
            List of analyzed PackageUpdate objects
        """
        # Get raw update output
        raw_output = DNFParser.get_check_update_output()

        # Parse packages
        self.packages = DNFParser.parse_all(raw_output, fetch_sizes=fetch_sizes)

        # Analyze importance for each package
        for package in self.packages:
            package.importance = ImportanceAnalyzer.analyze_importance(package)

        # Generate summary
        self.summary = self._generate_summary()

        return self.packages

    def fetch_download_sizes(self, packages: list[PackageUpdate]) -> None:
        """
        Fetch download sizes for specific packages.

        Args:
            packages: List of packages to fetch sizes for
        """
        DNFParser.fetch_download_sizes(packages)
        # Update summary with new sizes
        self.summary = self._generate_summary()

    def _generate_summary(self) -> UpdateSummary:
        """
        Generate a summary of all updates.

        Returns:
            UpdateSummary object
        """
        summary = UpdateSummary()
        summary.total_packages = len(self.packages)

        for package in self.packages:
            # Count by category
            summary.by_category[package.category] = (
                summary.by_category.get(package.category, 0) + 1
            )

            # Count by importance
            summary.by_importance[package.importance] = (
                summary.by_importance.get(package.importance, 0) + 1
            )

            # Count by type
            if package.update_type:
                summary.by_type[package.update_type] = (
                    summary.by_type.get(package.update_type, 0) + 1
                )

            # Special counts
            if package.category == UpdateCategory.KERNEL:
                summary.kernel_count += 1
            if package.category == UpdateCategory.DRIVER:
                summary.driver_count += 1
            if package.update_type == UpdateType.SECURITY:
                summary.security_count += 1

            # Size
            if package.size:
                summary.total_size += package.size

        return summary

    def get_packages_by_category(self, category: UpdateCategory) -> list[PackageUpdate]:
        """
        Get packages filtered by category.

        Args:
            category: Category to filter by

        Returns:
            List of PackageUpdate objects
        """
        return [p for p in self.packages if p.category == category]

    def get_packages_by_importance(
        self, importance: UpdateImportance
    ) -> list[PackageUpdate]:
        """
        Get packages filtered by importance.

        Args:
            importance: Importance level to filter by

        Returns:
            List of PackageUpdate objects
        """
        return [p for p in self.packages if p.importance == importance]

    def get_security_updates(self) -> list[PackageUpdate]:
        """Get all security-related updates."""
        return [p for p in self.packages if p.update_type == UpdateType.SECURITY]

    def get_critical_updates(self) -> list[PackageUpdate]:
        """Get all critical importance updates."""
        return [p for p in self.packages if p.importance == UpdateImportance.CRITICAL]

    def get_kernel_updates(self) -> list[PackageUpdate]:
        """Get all kernel-related updates."""
        return [p for p in self.packages if p.category == UpdateCategory.KERNEL]

    def get_driver_updates(self) -> list[PackageUpdate]:
        """Get all driver-related updates."""
        return [p for p in self.packages if p.category == UpdateCategory.DRIVER]

    def get_update_categories(self) -> dict[UpdateCategory, list[PackageUpdate]]:
        """
        Get all packages grouped by category.

        Returns:
            Dictionary mapping categories to package lists
        """
        categories: dict[UpdateCategory, list[PackageUpdate]] = {}
        for package in self.packages:
            if package.category not in categories:
                categories[package.category] = []
            categories[package.category].append(package)
        return categories

    def get_risk_assessment(self) -> dict[str, any]:
        """
        Assess the risk of applying all updates at once.

        Returns:
            Dictionary with risk assessment information
        """
        if not self.packages:
            return {"risk_level": "low", "message": "No updates available"}

        risk_factors = []
        risk_score = 0

        # Check for critical updates
        critical_count = len(self.get_critical_updates())
        if critical_count > 0:
            risk_factors.append(f"{critical_count} critical updates")
            risk_score += critical_count * 10

        # Check for kernel updates
        kernel_count = self.summary.kernel_count if self.summary else 0
        if kernel_count > 0:
            risk_factors.append(f"{kernel_count} kernel updates")
            risk_score += kernel_count * 15

        # Check for driver updates
        driver_count = self.summary.driver_count if self.summary else 0
        if driver_count > 0:
            risk_factors.append(f"{driver_count} driver updates")
            risk_score += driver_count * 20

        # Check for security updates
        security_count = self.summary.security_count if self.summary else 0
        if security_count > 0:
            risk_factors.append(f"{security_count} security updates")
            risk_score += security_count * 5

        # Determine risk level
        if risk_score >= 50:
            risk_level = "high"
            recommendation = "Consider creating a snapshot and updating in batches"
        elif risk_score >= 25:
            risk_level = "medium"
            recommendation = "Consider creating a snapshot before updating"
        else:
            risk_level = "low"
            recommendation = "Updates appear safe to apply"

        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "recommendation": recommendation,
            "total_packages": len(self.packages),
        }
