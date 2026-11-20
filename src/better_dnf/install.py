"""Detect how the running copy of better-dnf was installed.

better-dnf can be installed two ways: as an RPM from COPR (the supported
path, upgraded with ``dnf``) or with pip (a user/site install).  The two
can coexist, and ``sudo better-dnf`` resolves through sudo's restricted
PATH, which usually finds ``/usr/bin/better-dnf`` -- so telling the user
which copy they are running matters.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_TIMEOUT = 10


def _rpm(args: list[str]) -> str | None:
    """Run an rpm query; return stripped stdout or None on failure."""
    try:
        result = subprocess.run(
            ["rpm", *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    out = (result.stdout or "").strip()
    return out or None


def rpm_package(package_dir: Path | str | None = None) -> str | None:
    """Return the RPM name that owns this installation, or None (pip/venv)."""
    if package_dir is None:
        package_dir = Path(__file__).resolve().parent
    return _rpm(["-qf", "--qf", "%{NAME}", str(package_dir)])


def rpm_version(package: str) -> str | None:
    """Return ``VERSION-RELEASE`` of an installed RPM package, or None."""
    return _rpm(["-q", "--qf", "%{VERSION}-%{RELEASE}", package])


def dnf_copy() -> tuple[str, str] | None:
    """Return ``(name, version-release)`` of a DNF-installed better-dnf.

    Searches installed RPMs by name (the package provides the console
    script, not a ``better-dnf`` capability), so a shadowing system copy
    is still detected.  Returns None when none is installed.
    """
    out = _rpm(["-qa", "--qf", "%{NAME},%{VERSION}-%{RELEASE}\n"])
    if not out:
        return None
    for line in out.splitlines():
        name, sep, version = line.partition(",")
        if sep and "better-dnf" in name:
            return (name.strip(), version.strip())
    return None
