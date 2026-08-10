#!/usr/bin/env python3
"""
Simple test script to verify Fedora Update Analyzer installation.
"""

import sys
import subprocess
import os


def run_command(cmd: str) -> tuple:
    """Run a command and return output and return code."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        return "", 1
    except Exception as e:
        return str(e), 1


def check_python_version():
    """Check Python version."""
    print("Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} is supported")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} is not supported (need 3.9+)")
        return False


def check_dependencies():
    """Check if dependencies are installed."""
    print("\nChecking dependencies...")
    dependencies = ["typer", "rich", "questionary", "pyyaml", "requests", "packaging"]
    
    all_ok = True
    for dep in dependencies:
        try:
            __import__(dep.replace("-", "_").split("[")[0])
            print(f"✓ {dep} is installed")
        except ImportError:
            print(f"✗ {dep} is NOT installed")
            all_ok = False
    
    return all_ok


def check_fedora():
    """Check if running on Fedora."""
    print("\nChecking Fedora...")
    output, return_code = run_command("cat /etc/os-release")
    
    if return_code == 0 and "Fedora" in output:
        print("✓ Running on Fedora")
        return True
    else:
        print("⚠ Not running on Fedora (tool may still work but is designed for Fedora)")
        return False


def check_btrfs():
    """Check if root filesystem is btrfs."""
    print("\nChecking btrfs...")
    output, return_code = run_command("findmnt -n -o FSTYPE /")
    
    if return_code == 0 and "btrfs" in output:
        print("✓ Root filesystem is btrfs (snapshots available)")
        return True
    else:
        print("⚠ Root filesystem is not btrfs (snapshots not available)")
        return False


def check_snapper():
    """Check if snapper is installed."""
    print("\nChecking snapper...")
    output, return_code = run_command("which snapper")
    
    if return_code == 0:
        print("✓ snapper is installed")
        return True
    else:
        print("⚠ snapper is not installed (basic btrfs snapshots will be used)")
        return False


def test_import():
    """Test importing the module."""
    print("\nTesting module import...")
    try:
        from better_dnf import __version__
        print(f"✓ Successfully imported better_dnf v{__version__}")
        return True
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("Better DNF - Installation Test")
    print("=" * 60)
    
    results = []
    results.append(check_python_version())
    results.append(check_dependencies())
    results.append(check_fedora())
    results.append(check_btrfs())
    results.append(check_snapper())
    results.append(test_import())
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✓ All {total} checks passed!")
        print("\nYou can now use the tool:")
        print("  better-dnf --help")
        return 0
    else:
        print(f"⚠ {passed}/{total} checks passed")
        print("\nPlease fix the issues above before using the tool.")
        return 1


if __name__ == "__main__":
    sys.exit(main())