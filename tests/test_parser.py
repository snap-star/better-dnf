"""
Tests for the parser module.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from better_dnf.parser import DNFParser
from better_dnf.models import (
    PackageUpdate,
    UpdateCategory,
    UpdateType,
    UpdateImportance,
)


class TestDNFParser:
    """Tests for DNFParser class."""
    
    def test_parse_check_update_multiple(self):
        """Test parsing multiple packages (real dnf format: name.arch VERSION REPO)."""
        output = """package1.x86_64    1.0.0-1.fc40    fedora
package2.i686     2.0.0-1.fc40    updates
package3.noarch   3.0.0-1.fc40    fedora"""
        
        packages = DNFParser.parse_check_update(output)
        
        assert len(packages) == 3
        assert packages[0].name == "package1"
        assert packages[0].new_version == "1.0.0-1.fc40"
        assert packages[0].repository == "fedora"
        assert packages[1].name == "package2"
        assert packages[1].new_version == "2.0.0-1.fc40"
        assert packages[1].repository == "updates"
        assert packages[2].name == "package3"
    
    def test_parse_check_update_empty(self):
        """Test parsing empty output."""
        output = ""
        packages = DNFParser.parse_check_update(output)
        
        assert len(packages) == 0
    
    def test_parse_check_update_with_header(self):
        """Test parsing output with header lines."""
        output = """Last metadata expiration check: 0:05:12 ago on Mon 11 Aug 2026 10:00:00 AM.
package.x86_64    1.0.0-1.fc40    fedora"""
        
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
    
    def test_categorize_third_party_repo(self):
        """Test third-party repository packages are user apps."""
        package = PackageUpdate(
            name="google-chrome-stable",
            arch="x86_64",
            old_version="120.0",
            new_version="121.0",
            repository="google-chrome",
        )
        
        category = DNFParser.categorize_package(package)
        assert category == UpdateCategory.USER_APP
    
    def test_categorize_copr_repo(self):
        """Test COPR repository packages are user apps."""
        package = PackageUpdate(
            name="hyprland",
            arch="x86_64",
            old_version="1.0",
            new_version="1.1",
            repository="copr:copr.fedorainfracloud.org:somebody:hyprland",
        )
        
        category = DNFParser.categorize_package(package)
        assert category == UpdateCategory.USER_APP
    
    def test_categorize_unknown_repo(self):
        """Test unrecognized repository defaults to other."""
        package = PackageUpdate(
            name="someapp",
            arch="x86_64",
            old_version="1.0",
            new_version="1.1",
            repository="mystery-repo",
        )
        
        category = DNFParser.categorize_package(package)
        assert category == UpdateCategory.OTHER
    
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
        assert advisory is None
    

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


class TestRunCommand:
    """Tests for DNFParser.run_command."""
    
    def test_run_command_success(self):
        """Test successful command execution."""
        mock_result = MagicMock()
        mock_result.stdout = "output text\n"
        mock_result.returncode = 0
        
        with patch("better_dnf.parser.subprocess.run", return_value=mock_result) as mock_run:
            output, code = DNFParser.run_command("echo hello")
        
        assert output == "output text\n"
        assert code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == "echo hello"
        assert mock_run.call_args.kwargs["shell"] is True
        assert mock_run.call_args.kwargs["capture_output"] is True
        assert mock_run.call_args.kwargs["text"] is True
    
    def test_run_command_with_sudo(self):
        """Test command execution with sudo prefix."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        
        with patch("better_dnf.parser.subprocess.run", return_value=mock_result) as mock_run:
            DNFParser.run_command("dnf check-update", sudo=True)
        
        assert mock_run.call_args.args[0] == "sudo dnf check-update"
    
    def test_run_command_timeout(self):
        """Test timeout raises RuntimeError."""
        with patch("better_dnf.parser.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 300)):
            with pytest.raises(RuntimeError, match="Command timed out"):
                DNFParser.run_command("echo hello")
    
    def test_run_command_generic_error(self):
        """Test generic failure raises RuntimeError."""
        with patch("better_dnf.parser.subprocess.run", side_effect=OSError("boom")):
            with pytest.raises(RuntimeError, match="Failed to run command"):
                DNFParser.run_command("echo hello")


class TestCommandHelpers:
    """Tests for check-update/updateinfo helpers."""
    
    def test_get_check_update_output_success(self):
        """Test successful check-update (return code 0)."""
        with patch.object(DNFParser, "run_command", return_value=("out\n", 0)):
            assert DNFParser.get_check_update_output() == "out\n"
    
    def test_get_check_update_output_updates_available(self):
        """Test check-update with updates available (return code 100 is OK)."""
        with patch.object(DNFParser, "run_command", return_value=("out\n", 100)):
            assert DNFParser.get_check_update_output() == "out\n"
    
    def test_get_check_update_output_failure(self):
        """Test check-update failure raises RuntimeError."""
        with patch.object(DNFParser, "run_command", return_value=("err\n", 1)):
            with pytest.raises(RuntimeError, match="return code 1"):
                DNFParser.get_check_update_output()
    
    def test_get_update_info_no_package(self):
        """Test updateinfo without package filter."""
        with patch.object(DNFParser, "run_command", return_value=("adv\n", 0)) as mock_run:
            output = DNFParser.get_update_info()
        assert output == "adv\n"
        assert "updateinfo list" in mock_run.call_args.args[0]
        assert "firefox" not in mock_run.call_args.args[0]
    
    def test_get_update_info_with_package(self):
        """Test updateinfo with a package filter."""
        with patch.object(DNFParser, "run_command", return_value=("adv\n", 0)) as mock_run:
            output = DNFParser.get_update_info("firefox")
        assert output == "adv\n"
        assert mock_run.call_args.args[0].endswith("firefox")
    
    def test_get_update_info_failure_returns_empty(self):
        """Test updateinfo failure returns empty string (does not raise)."""
        with patch.object(DNFParser, "run_command", return_value=("", 1)):
            assert DNFParser.get_update_info() == ""
    
    def test_get_security_updates_success(self):
        """Test security updates listing."""
        with patch.object(DNFParser, "run_command", return_value=("sec\n", 0)) as mock_run:
            output = DNFParser.get_security_updates()
        assert output == "sec\n"
        assert "--security" in mock_run.call_args.args[0]
    
    def test_get_security_updates_failure_returns_empty(self):
        """Test security updates failure returns empty string."""
        with patch.object(DNFParser, "run_command", return_value=("", 1)):
            assert DNFParser.get_security_updates() == ""


class TestGetUserInstalledPackages:
    """Tests for get_user_installed_packages."""
    
    def test_with_epoch(self):
        """Test parsing package names with epoch."""
        output = "firefox-0:153.0.1-1.fc44.x86_64\nakmod-nvidia-580xx-3:580.173.02-1.fc44.x86_64\n"
        with patch.object(DNFParser, "run_command", return_value=(output, 0)):
            result = DNFParser.get_user_installed_packages()
        assert result == {"firefox", "akmod-nvidia-580xx"}
    
    def test_without_epoch(self):
        """Test parsing package names without epoch (split by first hyphen)."""
        output = "firefox-153.0.1-1.fc44.x86_64\n"
        with patch.object(DNFParser, "run_command", return_value=(output, 0)):
            result = DNFParser.get_user_installed_packages()
        assert result == {"firefox"}
    
    def test_skips_blank_lines(self):
        """Test blank lines in output are skipped."""
        output = "firefox-153.0.1-1.fc44.x86_64\n\n\nkernel-6.19.1-1.fc44.x86_64\n"
        with patch.object(DNFParser, "run_command", return_value=(output, 0)):
            result = DNFParser.get_user_installed_packages()
        assert result == {"firefox", "kernel"}
    
    def test_empty_output(self):
        """Test empty output returns empty set."""
        with patch.object(DNFParser, "run_command", return_value=("", 0)):
            assert DNFParser.get_user_installed_packages() == set()
    
    def test_failure_returns_empty(self):
        """Test command failure returns empty set."""
        with patch.object(DNFParser, "run_command", return_value=("", 1)):
            assert DNFParser.get_user_installed_packages() == set()
    
    def test_lowercases_names(self):
        """Test names are lowercased."""
        output = "Firefox-0:153.0.1-1.fc44.x86_64\n"
        with patch.object(DNFParser, "run_command", return_value=(output, 0)):
            result = DNFParser.get_user_installed_packages()
        assert result == {"firefox"}


class TestGetDownloadSizes:
    """Tests for get_download_sizes."""
    
    def test_empty_packages(self):
        """Test empty package list returns empty dict without running commands."""
        with patch.object(DNFParser, "run_command") as mock_run:
            assert DNFParser.get_download_sizes([]) == {}
        mock_run.assert_not_called()
    
    def test_parses_sizes(self):
        """Test parsing package sizes from repoquery output."""
        output = "firefox 123456\n"
        with patch.object(DNFParser, "run_command", return_value=(output, 0)):
            result = DNFParser.get_download_sizes(["firefox"])
        assert result == {"firefox": 123456}
    
    def test_skips_invalid_size(self):
        """Test non-numeric size is skipped."""
        output = "weirdpkg not-a-number\n"
        with patch.object(DNFParser, "run_command", return_value=(output, 0)):
            result = DNFParser.get_download_sizes(["weirdpkg"])
        assert result == {}
    
    def test_failure_returns_empty(self):
        """Test command failure returns empty dict."""
        with patch.object(DNFParser, "run_command", return_value=("", 1)):
            assert DNFParser.get_download_sizes(["firefox"]) == {}
    
    def test_limits_to_50_packages(self):
        """Test only the first 50 packages are queried."""
        names = [f"pkg{i}" for i in range(60)]
        with patch.object(DNFParser, "run_command", return_value=("", 0)) as mock_run:
            DNFParser.get_download_sizes(names)
        assert mock_run.call_count == 50


class TestParseCheckUpdateEdgeCases:
    """Tests for edge cases in parse_check_update."""
    
    def test_obsoleting_header_skipped(self):
        """Test Obsoleting header lines are skipped (but package lines below parse)."""
        output = "Obsoleting Packages\noldpkg.x86_64 fedora 1.0-1\nnewpkg.x86_64 updates 1.1-1\n"
        packages = DNFParser.parse_check_update(output)
        # Header line itself produces nothing; the two package lines below do
        assert len(packages) == 2
        assert {p.name for p in packages} == {"oldpkg", "newpkg"}
    
    def test_upgrades_header_skipped(self):
        """Test Upgrades header lines are skipped (but package lines below parse)."""
        output = "Upgrades\npkg.x86_64 fedora 1.0-1\n"
        packages = DNFParser.parse_check_update(output)
        assert len(packages) == 1
        assert packages[0].name == "pkg"
    
    def test_skip_name_in_skip_list(self):
        """Test package names matching the reserved skip list are skipped."""
        output = "available.x86_64 fedora 1.0-1\nrealpkg.x86_64 updates 2.0-1\n"
        packages = DNFParser.parse_check_update(output)
        assert len(packages) == 1
        assert packages[0].name == "realpkg"
    
    def test_no_arch_defaults_noarch(self):
        """Test package without arch defaults to noarch."""
        output = "somepkg 1.0-1.fc44 fedora\n"
        packages = DNFParser.parse_check_update(output)
        assert len(packages) == 1
        assert packages[0].arch == "noarch"
    
    def test_package_with_hyphens_and_plus(self):
        """Test names with hyphens and plus signs parse correctly."""
        output = "libavcodec-freeworld.i686 8.1.2-1.fc44 rpmfusion-free-updates\n"
        packages = DNFParser.parse_check_update(output)
        assert len(packages) == 1
        assert packages[0].name == "libavcodec-freeworld"
        assert packages[0].arch == "i686"
        assert packages[0].repository == "rpmfusion-free-updates"


class TestGetInstalledVersion:
    """Tests for get_installed_version."""
    
    def test_installed(self):
        """Test returning installed version."""
        with patch.object(DNFParser, "run_command", return_value=("153.0.1\n", 0)) as mock_run:
            version = DNFParser.get_installed_version("firefox")
        assert version == "153.0.1"
        assert "rpm -q firefox" in mock_run.call_args.args[0]
    
    def test_not_installed(self):
        """Test returns None when not installed."""
        with patch.object(DNFParser, "run_command", return_value=("", 1)):
            assert DNFParser.get_installed_version("ghostpkg") is None


class TestGetPackageInfo:
    """Tests for get_package_info."""
    
    def test_full_info(self):
        """Test parsing complete package info."""
        rpm_out = "firefox|153.0.1|1.fc44|x86_64|123456|Mon 11 Aug 2026\n"
        repo_out = "updates\n"
        
        def fake_run(cmd, sudo=False):
            if "rpm -q" in cmd:
                return (rpm_out, 0)
            return (repo_out, 0)
        
        with patch.object(DNFParser, "run_command", side_effect=fake_run):
            info = DNFParser.get_package_info("firefox")
        
        assert info["name"] == "firefox"
        assert info["version"] == "153.0.1"
        assert info["release"] == "1.fc44"
        assert info["arch"] == "x86_64"
        assert info["size"] == 123456
        assert info["install_date"] == "Mon 11 Aug 2026"
        assert info["repository"] == "updates"
    
    def test_non_numeric_size_defaults_zero(self):
        """Test non-numeric size defaults to 0."""
        rpm_out = "firefox|153.0.1|1.fc44|x86_64|unknown|date\n"
        
        def fake_run(cmd, sudo=False):
            if "rpm -q" in cmd:
                return (rpm_out, 0)
            return ("", 1)
        
        with patch.object(DNFParser, "run_command", side_effect=fake_run):
            info = DNFParser.get_package_info("firefox")
        
        assert info["size"] == 0
    
    def test_short_output_returns_empty(self):
        """Test truncated rpm output returns minimal info."""
        rpm_out = "firefox|153.0.1\n"
        
        def fake_run(cmd, sudo=False):
            if "rpm -q" in cmd:
                return (rpm_out, 0)
            return ("", 1)
        
        with patch.object(DNFParser, "run_command", side_effect=fake_run):
            info = DNFParser.get_package_info("firefox")
        
        assert info == {}
    
    def test_rpm_failure_returns_empty(self):
        """Test rpm failure returns empty dict."""
        with patch.object(DNFParser, "run_command", return_value=("", 1)):
            assert DNFParser.get_package_info("ghostpkg") == {}


class TestParseAdvisoryLineVariants:
    """Tests for parse_advisory_line variants."""
    
    def test_enhancement_type(self):
        """Test enhancement advisory type."""
        line = "FEDORA-2024-xyz789 enhancement firefox"
        advisory = DNFParser.parse_advisory_line(line)
        assert advisory is not None
        assert advisory.update_type == UpdateType.ENHANCEMENT
    
    def test_moderate_severity(self):
        """Test moderate severity."""
        line = "FEDORA-2024-abc111 security/moderate firefox"
        advisory = DNFParser.parse_advisory_line(line)
        assert advisory.severity == "moderate"
    
    def test_low_severity(self):
        """Test low severity."""
        line = "FEDORA-2024-abc222 security/low firefox"
        advisory = DNFParser.parse_advisory_line(line)
        assert advisory.severity == "low"
    
    def test_bugfix_default_type(self):
        """Test bugfix is the default type."""
        line = "FEDORA-2024-abc333 bugfix firefox"
        advisory = DNFParser.parse_advisory_line(line)
        assert advisory.update_type == UpdateType.BUGFIX
        assert advisory.severity is None
    
    def test_too_short_line_returns_none(self):
        """Test lines with fewer than 3 parts return None."""
        assert DNFParser.parse_advisory_line("just two") is None
    
    def test_multiple_cves(self):
        """Test multiple CVEs are extracted."""
        line = "FEDORA-2024-abc444 security/critical CVE-2024-1111 CVE-2024-2222 openssl"
        advisory = DNFParser.parse_advisory_line(line)
        assert advisory.cves == ["CVE-2024-1111", "CVE-2024-2222"]
    
    def test_no_cves(self):
        """Test advisory without CVEs has empty cve list."""
        line = "FEDORA-2024-abc555 security/important firefox"
        advisory = DNFParser.parse_advisory_line(line)
        assert advisory.cves == []


class TestParseAll:
    """Tests for the full parse_all pipeline."""
    
    def _patch_parse_all(self, user_installed=None, security="", sizes=None, installed=None):
        return [
            patch.object(DNFParser, "get_user_installed_packages", return_value=user_installed or set()),
            patch.object(DNFParser, "get_security_updates", return_value=security),
            patch.object(DNFParser, "get_download_sizes", return_value=sizes or {}),
            patch.object(DNFParser, "get_installed_version", return_value=installed),
        ]
    
    def test_parse_all_enriches_packages(self):
        """Test packages are enriched with version, size, and category."""
        output = "firefox.x86_64 153.0.2-1.fc44 updates\n"
        patches = self._patch_parse_all(
            user_installed={"firefox"},
            installed="153.0.1",
            sizes={"firefox": 123456},
        )
        
        with patches[0], patches[1], patches[2], patches[3]:
            packages = DNFParser.parse_all(output)
        
        assert len(packages) == 1
        pkg = packages[0]
        assert pkg.name == "firefox"
        assert pkg.old_version == "153.0.1"
        assert pkg.size == 123456
        assert pkg.category == UpdateCategory.USER_APP
    
    def test_parse_all_fetch_sizes_false(self):
        """Test fetch_sizes=False skips download size fetching."""
        output = "firefox.x86_64 153.0.2-1.fc44 updates\n"
        with patch.object(DNFParser, "get_user_installed_packages", return_value=set()), \
             patch.object(DNFParser, "get_security_updates", return_value=""), \
             patch.object(DNFParser, "get_download_sizes") as mock_sizes, \
             patch.object(DNFParser, "get_installed_version", return_value=None):
            DNFParser.parse_all(output, fetch_sizes=False)
        mock_sizes.assert_not_called()
    
    def test_parse_all_security_kernel_importance(self):
        """Test security packages in kernel/driver categories get HIGH importance."""
        output = "kernel.x86_64 6.19.108-1.fc44 updates\n"
        security = (
            "Name Type Severity Package Issued\n"
            "FEDORA-2024-1 security important kernel-6.19.108-1.fc44.x86_64 2026-08-11\n"
        )
        patches = self._patch_parse_all(
            security=security,
            installed="6.19.107",
        )
        
        with patches[0], patches[1], patches[2], patches[3]:
            packages = DNFParser.parse_all(output)
        
        assert len(packages) == 1
        pkg = packages[0]
        assert pkg.category == UpdateCategory.KERNEL
        assert pkg.update_type == UpdateType.SECURITY
        assert pkg.importance == UpdateImportance.HIGH
    
    def test_parse_all_no_security_detection(self):
        """Test packages not in security list keep default type."""
        output = "firefox.x86_64 153.0.2-1.fc44 updates\n"
        patches = self._patch_parse_all(
            security="Name Type Severity Package Issued\n",
            installed="153.0.1",
        )
        
        with patches[0], patches[1], patches[2], patches[3]:
            packages = DNFParser.parse_all(output)
        
        assert packages[0].update_type is None
    
    def test_parse_all_security_name_with_arch(self):
        """Test security matching strips arch from package names in the list."""
        # Security list entries can include the arch (e.g. openssl.x86_64-3.0.1-1)
        security = (
            "Name Type Severity Package Issued\n"
            "FEDORA-2024-2 security critical openssl.x86_64-3.0.1-1.fc44 2026-08-11\n"
        )
        output = "openssl.x86_64 3.0.2-1.fc44 updates\n"
        patches = self._patch_parse_all(
            security=security,
            installed="3.0.1",
        )
        
        with patches[0], patches[1], patches[2], patches[3]:
            packages = DNFParser.parse_all(output)
        
        assert len(packages) == 1
        assert packages[0].name == "openssl"
        assert packages[0].update_type == UpdateType.SECURITY


class TestFetchDownloadSizes:
    """Tests for fetch_download_sizes."""
    
    def test_fetches_and_updates_in_place(self):
        """Test sizes are fetched and applied in place."""
        pkg = PackageUpdate(
            name="firefox",
            arch="x86_64",
            old_version="1.0.0",
            new_version="1.0.1",
            repository="fedora",
        )
        
        with patch.object(DNFParser, "get_download_sizes", return_value={"firefox": 999}) as mock_get:
            result = DNFParser.fetch_download_sizes([pkg])
        
        assert result == [pkg]
        assert result[0] is pkg
        assert pkg.size == 999
        mock_get.assert_called_once_with(["firefox"])
    
    def test_unknown_package_unchanged(self):
        """Test packages without a reported size keep size None."""
        pkg = PackageUpdate(
            name="firefox",
            arch="x86_64",
            old_version="1.0.0",
            new_version="1.0.1",
            repository="fedora",
        )
        
        with patch.object(DNFParser, "get_download_sizes", return_value={}):
            result = DNFParser.fetch_download_sizes([pkg])
        
        assert pkg.size is None
        assert len(result) == 1