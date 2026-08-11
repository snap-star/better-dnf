"""
Tests for the analyzer module.
"""

from better_dnf.analyzer import ImportanceAnalyzer, UpdateAnalyzer
from better_dnf.models import (
    PackageUpdate,
    UpdateAdvisory,
    UpdateCategory,
    UpdateImportance,
    UpdateType,
)


class TestImportanceAnalyzer:
    """Tests for ImportanceAnalyzer class."""

    def test_analyze_critical_security(self):
        """Test analysis of critical security update."""
        package = PackageUpdate(
            name="openssl",
            arch="x86_64",
            old_version="3.0.0",
            new_version="3.0.1",
            repository="fedora",
            update_type=UpdateType.SECURITY,
            category=UpdateCategory.SYSTEM,
            advisories=[
                UpdateAdvisory(
                    advisory_id="FEDORA-2024-001",
                    update_type=UpdateType.SECURITY,
                    severity="critical",
                    cves=["CVE-2024-12345"],
                    description="Critical remote code execution vulnerability",
                )
            ],
        )

        importance = ImportanceAnalyzer.analyze_importance(package)

        # Should be critical or high due to security + CVE + system category
        assert importance in (UpdateImportance.CRITICAL, UpdateImportance.HIGH)

    def test_analyze_kernel_update(self):
        """Test analysis of kernel update."""
        package = PackageUpdate(
            name="kernel-core",
            arch="x86_64",
            old_version="6.0.0",
            new_version="6.1.0",
            repository="fedora",
            category=UpdateCategory.KERNEL,
        )

        importance = ImportanceAnalyzer.analyze_importance(package)

        # Kernel updates should have at least medium importance
        assert importance in (
            UpdateImportance.CRITICAL,
            UpdateImportance.HIGH,
            UpdateImportance.MEDIUM,
        )

    def test_analyze_driver_update(self):
        """Test analysis of driver update."""
        package = PackageUpdate(
            name="nvidia-driver",
            arch="x86_64",
            old_version="500.0",
            new_version="501.0",
            repository="rpmfusion",
            category=UpdateCategory.DRIVER,
        )

        importance = ImportanceAnalyzer.analyze_importance(package)

        # Driver updates should have at least medium importance
        assert importance in (
            UpdateImportance.CRITICAL,
            UpdateImportance.HIGH,
            UpdateImportance.MEDIUM,
        )

    def test_analyze_user_app_update(self):
        """Test analysis of user application update."""
        package = PackageUpdate(
            name="firefox",
            arch="x86_64",
            old_version="118.0",
            new_version="119.0",
            repository="fedora",
            category=UpdateCategory.USER_APP,
            update_type=UpdateType.ENHANCEMENT,
        )

        importance = ImportanceAnalyzer.analyze_importance(package)

        # User app enhancements should have lower importance
        assert importance in (
            UpdateImportance.MEDIUM,
            UpdateImportance.LOW,
            UpdateImportance.UNKNOWN,
        )

    def test_analyze_with_cve(self):
        """Test analysis with CVE references."""
        package = PackageUpdate(
            name="test-package",
            arch="x86_64",
            old_version="1.0.0",
            new_version="1.0.1",
            repository="fedora",
            advisories=[
                UpdateAdvisory(
                    advisory_id="TEST-001",
                    update_type=UpdateType.SECURITY,
                    cves=["CVE-2024-12345"],
                )
            ],
        )

        importance = ImportanceAnalyzer.analyze_importance(package)

        # CVE should increase importance
        assert importance in (
            UpdateImportance.CRITICAL,
            UpdateImportance.HIGH,
            UpdateImportance.MEDIUM,
        )

    def test_get_analysis_text(self):
        """Test getting analysis text."""
        package = PackageUpdate(
            name="test-package",
            arch="x86_64",
            old_version="1.0.0",
            new_version="1.0.1",
            repository="fedora",
            changelog_summary="Fixed critical bug",
            advisories=[
                UpdateAdvisory(
                    advisory_id="TEST-001",
                    update_type=UpdateType.SECURITY,
                    severity="high",
                )
            ],
        )

        text = ImportanceAnalyzer._get_analysis_text(package)

        assert "Fixed critical bug" in text
        assert "high" in text
        assert "test-package" in text

    def test_calculate_version_diff(self):
        """Test version difference calculation."""
        package = PackageUpdate(
            name="test-package",
            arch="x86_64",
            old_version="1.0.0",
            new_version="2.0.0",
            repository="fedora",
        )

        diff = ImportanceAnalyzer._calculate_version_diff(package)

        # Should detect major version jump
        assert diff > 0


class TestUpdateAnalyzer:
    """Tests for UpdateAnalyzer class."""

    def test_init(self):
        """Test analyzer initialization."""
        analyzer = UpdateAnalyzer()

        assert analyzer.packages == []
        assert analyzer.summary is None

    def test_get_packages_by_category(self):
        """Test filtering packages by category."""
        analyzer = UpdateAnalyzer()
        analyzer.packages = [
            PackageUpdate(
                name="kernel-core",
                arch="x86_64",
                old_version="6.0.0",
                new_version="6.1.0",
                repository="fedora",
                category=UpdateCategory.KERNEL,
            ),
            PackageUpdate(
                name="firefox",
                arch="x86_64",
                old_version="118.0",
                new_version="119.0",
                repository="fedora",
                category=UpdateCategory.USER_APP,
            ),
        ]

        kernel_packages = analyzer.get_packages_by_category(UpdateCategory.KERNEL)

        assert len(kernel_packages) == 1
        assert kernel_packages[0].name == "kernel-core"

    def test_get_packages_by_importance(self):
        """Test filtering packages by importance."""
        analyzer = UpdateAnalyzer()
        analyzer.packages = [
            PackageUpdate(
                name="package1",
                arch="x86_64",
                old_version="1.0.0",
                new_version="1.0.1",
                repository="fedora",
                importance=UpdateImportance.HIGH,
            ),
            PackageUpdate(
                name="package2",
                arch="x86_64",
                old_version="2.0.0",
                new_version="2.0.1",
                repository="fedora",
                importance=UpdateImportance.LOW,
            ),
        ]

        high_packages = analyzer.get_packages_by_importance(UpdateImportance.HIGH)

        assert len(high_packages) == 1
        assert high_packages[0].name == "package1"

    def test_get_security_updates(self):
        """Test getting security updates."""
        analyzer = UpdateAnalyzer()
        analyzer.packages = [
            PackageUpdate(
                name="openssl",
                arch="x86_64",
                old_version="3.0.0",
                new_version="3.0.1",
                repository="fedora",
                update_type=UpdateType.SECURITY,
            ),
            PackageUpdate(
                name="bash",
                arch="x86_64",
                old_version="5.2.0",
                new_version="5.2.1",
                repository="fedora",
                update_type=UpdateType.BUGFIX,
            ),
        ]

        security_updates = analyzer.get_security_updates()

        assert len(security_updates) == 1
        assert security_updates[0].name == "openssl"

    def test_get_kernel_updates(self):
        """Test getting kernel updates."""
        analyzer = UpdateAnalyzer()
        analyzer.packages = [
            PackageUpdate(
                name="kernel-core",
                arch="x86_64",
                old_version="6.0.0",
                new_version="6.1.0",
                repository="fedora",
                category=UpdateCategory.KERNEL,
            ),
            PackageUpdate(
                name="kernel-headers",
                arch="x86_64",
                old_version="6.0.0",
                new_version="6.1.0",
                repository="fedora",
                category=UpdateCategory.KERNEL,
            ),
        ]

        kernel_updates = analyzer.get_kernel_updates()

        assert len(kernel_updates) == 2

    def test_get_driver_updates(self):
        """Test getting driver updates."""
        analyzer = UpdateAnalyzer()
        analyzer.packages = [
            PackageUpdate(
                name="nvidia-driver",
                arch="x86_64",
                old_version="500.0",
                new_version="501.0",
                repository="rpmfusion",
                category=UpdateCategory.DRIVER,
            ),
        ]

        driver_updates = analyzer.get_driver_updates()

        assert len(driver_updates) == 1

    def test_get_update_categories(self):
        """Test getting packages grouped by category."""
        analyzer = UpdateAnalyzer()
        analyzer.packages = [
            PackageUpdate(
                name="kernel-core",
                arch="x86_64",
                old_version="6.0.0",
                new_version="6.1.0",
                repository="fedora",
                category=UpdateCategory.KERNEL,
            ),
            PackageUpdate(
                name="nvidia-driver",
                arch="x86_64",
                old_version="500.0",
                new_version="501.0",
                repository="rpmfusion",
                category=UpdateCategory.DRIVER,
            ),
        ]

        categories = analyzer.get_update_categories()

        assert UpdateCategory.KERNEL in categories
        assert UpdateCategory.DRIVER in categories
        assert len(categories[UpdateCategory.KERNEL]) == 1
        assert len(categories[UpdateCategory.DRIVER]) == 1

    def test_get_risk_assessment(self):
        """Test risk assessment."""
        analyzer = UpdateAnalyzer()
        analyzer.packages = [
            PackageUpdate(
                name="kernel-core",
                arch="x86_64",
                old_version="6.0.0",
                new_version="6.1.0",
                repository="fedora",
                category=UpdateCategory.KERNEL,
                importance=UpdateImportance.HIGH,
            ),
        ]

        # Generate summary first
        analyzer.summary = analyzer._generate_summary()

        risk = analyzer.get_risk_assessment()

        assert "risk_level" in risk
        assert "risk_score" in risk
        assert "recommendation" in risk
        assert risk["total_packages"] == 1
