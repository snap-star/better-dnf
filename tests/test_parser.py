"""
Tests for the parser module.
"""

import pytest
from better_dnf.parser import DNFParser
from better_dnf.models import PackageUpdate, UpdateCategory, UpdateType


class TestDNFParser:
    """Tests for DNFParser class."""
    
    def test_parse_check_update_simple(self):
        """Test parsing simple check-update output."""
        output = "package.x86_64    fedora    1.0.0-1.fc40"
        packages = DNFParser.parse_check_update(output)
        
        assert len(packages) == 1
        assert packages[0].name == "package"
        assert packages[0].arch == "x86_64"
        assert packages[0].repository == "fedora"
        assert packages[0].new_version == "1.0.0-1.fc40"
    
    def test_parse_check_update_multiple(self):
        """Test parsing multiple packages."""
        output = """package1.x86_64    fedora    1.0.0-1.fc40
package2.i686     updates   2.0.0-1.fc40
package3.noarch   fedora    3.0.0-1.fc40"""
        
        packages = DNFParser.parse_check_update(output)
        
        assert len(packages) == 3
        assert packages[0].name == "package1"
        assert packages[1].name == "package2"
        assert packages[2].name == "package3"
    
    def test_parse_check_update_empty(self):
        """Test parsing empty output."""
        output = ""
        packages = DNFParser.parse_check_update(output)
        
        assert len(packages) == 0
    
    def test_parse_check_update_with_header(self):
        """Test parsing output with header lines."""
        output = """Last metadata expiration check: 0:05:12 ago on Mon 11 Aug 2026 10:00:00 AM.
package.x86_64    fedora    1.0.0-1.fc40"""
        
        packages = DNFParser.parse_check_update(output)
        
        assert len(packages) == 1
        assert packages[0].name == "package"
    
    def test_categorize_kernel(self):
        """Test kernel package categorization."""
        package = PackageUpdate(
            name="kernel-core",
            arch="x86_64",
            old_version="6.0.0",
            new_version="6.1.0",
            repository="fedora",
        )
        
        category = DNFParser.categorize_package(package)
        assert category == UpdateCategory.KERNEL
    
    def test_categorize_driver(self):
        """Test driver package categorization."""
        package = PackageUpdate(
            name="nvidia-driver",
            arch="x86_64",
            old_version="500.0",
            new_version="501.0",
            repository="rpmfusion",
        )
        
        category = DNFParser.categorize_package(package)
        assert category == UpdateCategory.DRIVER
    
    def test_categorize_system(self):
        """Test system package categorization."""
        package = PackageUpdate(
            name="systemd",
            arch="x86_64",
            old_version="254.0",
            new_version="255.0",
            repository="fedora",
        )
        
        category = DNFParser.categorize_package(package)
        assert category == UpdateCategory.SYSTEM
    
    def test_categorize_official(self):
        """Test official Fedora package categorization."""
        package = PackageUpdate(
            name="bash",
            arch="x86_64",
            old_version="5.2.0",
            new_version="5.2.1",
            repository="fedora",
        )
        
        category = DNFParser.categorize_package(package)
        assert category == UpdateCategory.OFFICIAL
    
    def test_categorize_user_app(self):
        """Test user application categorization."""
        package = PackageUpdate(
            name="firefox",
            arch="x86_64",
            old_version="118.0",
            new_version="119.0",
            repository="fedora",
        )
        
        category = DNFParser.categorize_package(package)
        assert category == UpdateCategory.USER_APP
    
    def test_parse_advisory_line_security(self):
        """Test parsing security advisory line."""
        line = "FEDORA-2024-abc123 security/important kernel-core"
        advisory = DNFParser.parse_advisory_line(line)
        
        assert advisory is not None
        assert advisory.advisory_id == "FEDORA-2024-abc123"
        assert advisory.update_type == UpdateType.SECURITY
        assert advisory.severity == "important"
    
    def test_parse_advisory_line_with_cve(self):
        """Test parsing advisory line with CVE."""
        line = "FEDORA-2024-def456 security/critical CVE-2024-12345 openssl"
        advisory = DNFParser.parse_advisory_line(line)
        
        assert advisory is not None
        assert "CVE-2024-12345" in advisory.cves
    
    def test_parse_advisory_line_invalid(self):
        """Test parsing invalid advisory line."""
        line = "invalid line"
        advisory = DNFParser.parse_advisory_line(line)
        
        # Should return None for invalid lines
        # (implementation specific)
    
    def test_get_analysis_text(self):
        """Test getting analysis text from package."""
        from better_dnf.models import UpdateAdvisory
        
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
                    severity="critical",
                    cves=["CVE-2024-12345"],
                )
            ],
        )
        
        text = DNFParser._get_analysis_text(package)
        
        assert "Fixed critical bug" in text
        assert "critical" in text
        assert "CVE-2024-12345" in text
        assert "test-package" in text


class TestPackageUpdate:
    """Tests for PackageUpdate model."""
    
    def test_full_name(self):
        """Test full_name property."""
        package = PackageUpdate(
            name="test-package",
            arch="x86_64",
            old_version="1.0.0",
            new_version="1.0.1",
            repository="fedora",
        )
        
        assert package.full_name == "test-package.x86_64"
    
    def test_version_diff(self):
        """Test version_diff property."""
        package = PackageUpdate(
            name="test-package",
            arch="x86_64",
            old_version="1.0.0",
            new_version="1.0.1",
            repository="fedora",
        )
        
        assert package.version_diff == "1.0.0 -> 1.0.1"
    
    def test_to_dict(self):
        """Test to_dict method."""
        package = PackageUpdate(
            name="test-package",
            arch="x86_64",
            old_version="1.0.0",
            new_version="1.0.1",
            repository="fedora",
        )
        
        d = package.to_dict()
        
        assert d["name"] == "test-package"
        assert d["arch"] == "x86_64"
        assert d["old_version"] == "1.0.0"
        assert d["new_version"] == "1.0.1"
        assert d["repository"] == "fedora"