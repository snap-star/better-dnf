"""
Parser for DNF check-update output and advisory information.
"""

from __future__ import annotations

import re
import subprocess
from typing import Any

from .models import (
    PackageUpdate,
    UpdateAdvisory,
    UpdateCategory,
    UpdateImportance,
    UpdateType,
)


class DNFParser:
    """Parser for DNF command output."""

    # Pattern for DNF check-update output lines
    # Format: package.name.arch    version    repo.name
    CHECK_UPDATE_PATTERN = re.compile(
        r"^([a-zA-Z0-9][a-zA-Z0-9._+-]+)\s+" r"(\S+)\s+" r"(\S+)$"
    )

    # Pattern for version comparison
    VERSION_PATTERN = re.compile(r"(?:\d+:)?(\d+\..+?)(?:\.(\d+))?$")

    @staticmethod
    def run_command(cmd: str, sudo: bool = False) -> tuple[str, int]:
        """
        Run a shell command and return output and return code.

        Args:
            cmd: Command to run
            sudo: Whether to run with sudo

        Returns:
            Tuple of (output, return_code)
        """
        try:
            if sudo:
                cmd = f"sudo {cmd}"

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=False,  # We check the return code manually below
            )
            return result.stdout, result.returncode
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Command timed out: {cmd}")
        except Exception as e:  # noqa: BLE001 - wrap any command error as RuntimeError
            raise RuntimeError(f"Failed to run command: {e}")

    @classmethod
    def get_check_update_output(cls) -> str:
        """
        Get output from 'dnf check-update' command.

        Returns:
            Raw output string from dnf check-update

        Raises:
            RuntimeError: If command fails
        """
        output, return_code = cls.run_command("dnf check-update --quiet")

        # dnf check-update returns 100 when updates are available
        # This is expected behavior, not an error
        if return_code not in (0, 100):
            raise RuntimeError(
                f"dnf check-update failed with return code {return_code}: {output}"
            )

        return output

    @classmethod
    def get_update_info(cls, package_name: str | None = None) -> str:
        """
        Get advisory information using 'dnf updateinfo'.

        Args:
            package_name: Optional specific package name

        Returns:
            Raw output string from dnf updateinfo
        """
        cmd = "dnf updateinfo list"
        if package_name:
            cmd += f" {package_name}"

        output, return_code = cls.run_command(cmd)

        if return_code != 0:
            # Don't fail hard, just return empty
            return ""

        return output

    @classmethod
    def get_security_updates(cls) -> str:
        """Get list of security updates."""
        output, return_code = cls.run_command("dnf updateinfo list --security")
        return output if return_code == 0 else ""

    @classmethod
    def get_user_installed_packages(cls) -> set:
        """
        Get list of packages explicitly installed by the user.

        Returns:
            Set of lowercase package names that were user-installed
        """
        output, return_code = cls.run_command("dnf repoquery --userinstalled")

        user_packages = set()
        if return_code == 0 and output.strip():
            for line in output.strip().splitlines():
                # Format: package-name-epoch:version-release.arch
                # e.g., firefox-0:153.0.1-1.fc44.x86_64
                # e.g., akmod-nvidia-580xx-3:580.173.02-1.fc44.x86_64
                line = line.strip()
                if not line:
                    continue

                # Find the epoch pattern (digit followed by colon)
                # This is the delimiter between package name and version
                epoch_match = re.search(r"(\d+):", line)
                if epoch_match:
                    # Get everything before the epoch
                    pkg_name = line[: epoch_match.start()]
                    # Remove trailing hyphen if present
                    pkg_name = pkg_name.removesuffix("-")
                    user_packages.add(pkg_name.lower())
                else:
                    # No epoch, try to split by first hyphen
                    parts = line.split("-", 1)
                    if parts:
                        user_packages.add(parts[0].lower())

        return user_packages

    @classmethod
    def get_download_sizes(cls, package_names: list[str]) -> dict[str, int]:
        """
        Get download sizes for multiple packages in one command.

        Args:
            package_names: List of package names

        Returns:
            Dictionary mapping package names to sizes in bytes
        """
        if not package_names:
            return {}

        sizes = {}

        # Get sizes for each package (dnf repoquery doesn't support multiple packages well)
        for name in package_names[:50]:  # Limit to avoid too many commands
            output, return_code = cls.run_command(
                f"dnf repoquery --qf '%{{name}} %{{downloadsize}}' --latest-limit=1 {name}"
            )

            if return_code == 0 and output.strip():
                for line in output.strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        pkg_name = parts[0]
                        try:
                            size = int(parts[1])
                            sizes[pkg_name] = size
                        except ValueError:
                            pass

        return sizes

    @classmethod
    def parse_check_update(cls, output: str) -> list[PackageUpdate]:
        """
        Parse dnf check-update output into PackageUpdate objects.

        Args:
            output: Raw output from dnf check-update

        Returns:
            List of PackageUpdate objects
        """
        packages = []

        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith(("Last", "Obsoleting", "Upgrades")):
                continue

            # Try to match the package line
            match = cls.CHECK_UPDATE_PATTERN.match(line)
            if match:
                # Format: package.name.arch    version    repo
                full_name = match.group(1)  # e.g., LibRaw.x86_64
                new_version = match.group(2)  # e.g., 0.22.2-1.fc44
                repository = match.group(3)  # e.g., updates

                # Split name and architecture
                if "." in full_name:
                    name, arch = full_name.rsplit(".", 1)
                else:
                    name = full_name
                    arch = "noarch"

                # Skip if this looks like a header or separator
                if name.lower() in ("last", "obsoleting", "available", "upgrades"):
                    continue

                package = PackageUpdate(
                    name=name,
                    arch=arch,
                    old_version="installed",  # We'll get actual version later
                    new_version=new_version,
                    repository=repository,
                )
                packages.append(package)

        return packages

    @classmethod
    def get_installed_version(cls, package_name: str) -> str | None:
        """
        Get the currently installed version of a package.

        Args:
            package_name: Name of the package

        Returns:
            Version string or None if not installed
        """
        output, return_code = cls.run_command(
            f"rpm -q {package_name} --queryformat '%{{VERSION}}'"
        )

        if return_code == 0 and output.strip():
            return output.strip()

        return None

    @classmethod
    def get_package_info(cls, package_name: str) -> dict[str, Any]:
        """
        Get detailed information about a package.

        Args:
            package_name: Name of the package

        Returns:
            Dictionary with package information
        """
        info: dict[str, Any] = {}

        # Get basic info
        output, return_code = cls.run_command(
            f"rpm -q {package_name} --queryformat '%{{NAME}}|%{{VERSION}}|%{{RELEASE}}|%{{ARCH}}|%{{SIZE}}|%{{INSTALLTIME:date}}'"
        )

        if return_code == 0 and output.strip():
            parts = output.strip().split("|")
            if len(parts) >= 6:
                info["name"] = parts[0]
                info["version"] = parts[1]
                info["release"] = parts[2]
                info["arch"] = parts[3]
                info["size"] = int(parts[4]) if parts[4].isdigit() else 0
                info["install_date"] = parts[5]

        # Get repository info
        output, return_code = cls.run_command(
            f"dnf repoquery --queryformat '%{{repo}}' {package_name}"
        )
        if return_code == 0 and output.strip():
            info["repository"] = output.strip().splitlines()[0]

        return info

    @classmethod
    def parse_advisory_line(cls, line: str) -> UpdateAdvisory | None:
        """
        Parse a single advisory line from dnf updateinfo.

        Args:
            line: Advisory line to parse

        Returns:
            UpdateAdvisory object or None if not parseable
        """
        # Typical format: FEDORA-2024-abc123 security/important package_name
        # Or: Fedora 40 security update for package

        parts = line.strip().split()
        if len(parts) < 3:
            return None

        advisory_id = parts[0]

        # Determine update type
        update_type = UpdateType.BUGFIX  # default
        if "security" in line.lower():
            update_type = UpdateType.SECURITY
        elif "enhancement" in line.lower():
            update_type = UpdateType.ENHANCEMENT

        # Determine severity
        severity = None
        if "critical" in line.lower():
            severity = "critical"
        elif "important" in line.lower():
            severity = "important"
        elif "moderate" in line.lower():
            severity = "moderate"
        elif "low" in line.lower():
            severity = "low"

        # Extract CVEs if present
        cves = re.findall(r"CVE-\d{4}-\d+", line)

        return UpdateAdvisory(
            advisory_id=advisory_id,
            update_type=update_type,
            severity=severity,
            cves=cves,
        )

    @classmethod
    def categorize_package(
        cls, package: PackageUpdate, user_installed: set | None = None
    ) -> UpdateCategory:
        """
        Determine the category of a package based on its name and metadata.

        Args:
            package: PackageUpdate to categorize
            user_installed: Optional set of user-installed package names

        Returns:
            UpdateCategory for the package
        """
        name_lower = package.name.lower()

        # Kernel packages (highest priority)
        if name_lower.startswith("kernel") or "kernel-" in name_lower:
            return UpdateCategory.KERNEL

        # Driver packages (common driver patterns)
        driver_patterns = [
            "nvidia",
            "nouveau",
            "mesa",
            "vulkan",
            "libgl",
            "wl",
            "akmod",
            "kmod",
            "driver",
            "firmware",
            "microcode",
            "wifi",
            "wireless",
            "bluetooth",
            "sound",
            "alsa",
            "pulseaudio",
            "pipewire",
            "gpu",
            "graphics",
            "video",
        ]
        for pattern in driver_patterns:
            if pattern in name_lower:
                return UpdateCategory.DRIVER

        # System packages (core system components)
        system_patterns = [
            "glibc",
            "systemd",
            "dbus",
            "polkit",
            "sudo",
            "pam",
            "selinux",
            "firewalld",
            "networkmanager",
            "systemd-",
            "grub",
            "dracut",
            "plymouth",
            "filesystem",
            "basesystem",
            "setup",
        ]
        for pattern in system_patterns:
            if pattern in name_lower:
                return UpdateCategory.SYSTEM

        # User-installed packages (from dnf repoquery --userinstalled)
        if user_installed and name_lower in user_installed:
            return UpdateCategory.USER_APP

        # Official Fedora packages (typically in fedora or updates repo)
        if package.repository:
            repo_lower = package.repository.lower()
            # Third-party repositories are NOT official
            third_party_repos = [
                "rpmfusion",
                "google-chrome",
                "spotify",
                "docker",
                "copr",
                "playonlinux",
                "wine",
                "steam",
                "pgadmin",
                "code",
                "vscode",
            ]
            for tp_repo in third_party_repos:
                if tp_repo in repo_lower:
                    return UpdateCategory.USER_APP

            # Standard Fedora repos are official
            if "fedora" in repo_lower or "updates" in repo_lower:
                return UpdateCategory.OFFICIAL

        # Default to other
        return UpdateCategory.OTHER

    @classmethod
    def parse_all(cls, output: str, fetch_sizes: bool = True) -> list[PackageUpdate]:
        """
        Parse all update information and enrich with categorization.

        Args:
            output: Raw output from dnf check-update
            fetch_sizes: Whether to fetch download sizes (slower but more complete)

        Returns:
            List of enriched PackageUpdate objects
        """
        packages = cls.parse_check_update(output)

        # Get user-installed packages for categorization
        user_installed = cls.get_user_installed_packages()

        # Get security updates list
        security_output = cls.get_security_updates()
        security_packages = set()
        for line in security_output.splitlines():
            if line.strip() and not line.startswith("Name"):  # Skip header
                # The output format is: Name Type Severity Package Issued
                # We need to extract the package name (column 4, index 3)
                parts = line.split()
                if len(parts) >= 4:
                    # Get the package name from column 4 (index 3)
                    package_full = parts[3]
                    # Extract just the name (before the version)
                    package_name = (
                        package_full.split("-")[0]
                        if "-" in package_full
                        else package_full
                    )
                    # Also try to get name without arch
                    if "." in package_name:
                        package_name = package_name.split(".")[0]
                    # Add lowercase version for case-insensitive matching
                    security_packages.add(package_name.lower())
                    # Also add the full package name without version for better matching
                    # Format: name-arch (e.g., systemd-259.8-1.fc44.x86_64)
                    # We want: systemd
                    name_parts = package_full.split("-")
                    if len(name_parts) > 1:
                        # Get everything before the version number
                        name_without_version = (
                            "-".join(name_parts[:-1])
                            if name_parts[-1][0].isdigit()
                            else package_full
                        )
                        if "." in name_without_version:
                            name_without_version = name_without_version.split(".")[0]
                        security_packages.add(name_without_version.lower())

        # Get download sizes only if requested (faster initial load)
        download_sizes = {}
        if fetch_sizes:
            package_names = [p.name for p in packages]
            download_sizes = cls.get_download_sizes(package_names)

        # Enrich each package
        for package in packages:
            # Categorize with user-installed information
            package.category = cls.categorize_package(package, user_installed)

            # Get installed version
            installed_version = cls.get_installed_version(package.name)
            if installed_version:
                package.old_version = installed_version

            # Get download size if available
            if package.name in download_sizes:
                package.size = download_sizes[package.name]

            # Check if security update (case-insensitive)
            if package.name.lower() in security_packages:
                package.update_type = UpdateType.SECURITY
                # Security packages often get higher importance
                if package.category in (UpdateCategory.KERNEL, UpdateCategory.DRIVER):
                    package.importance = UpdateImportance.HIGH

        return packages

    @classmethod
    def fetch_download_sizes(cls, packages: list[PackageUpdate]) -> list[PackageUpdate]:
        """
        Fetch download sizes for a list of packages and update them in place.

        Args:
            packages: List of PackageUpdate objects to update

        Returns:
            The same list with updated size information
        """
        package_names = [p.name for p in packages]
        download_sizes = cls.get_download_sizes(package_names)

        for package in packages:
            if package.name in download_sizes:
                package.size = download_sizes[package.name]

        return packages
