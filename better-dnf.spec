Name:           better-dnf
Version:        1.1.1
Release:        1%{?dist}
Summary:        A smarter DNF update tool for Fedora

License:        MIT
URL:            https://github.com/snap-star/better-dnf
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-hatchling
BuildRequires:  python3-packaging
BuildRequires:  python3-questionary
BuildRequires:  python3-rich
BuildRequires:  python3-typer

%global _description %{expand:
A smarter DNF update tool that categorizes updates and lets you
choose what to install safely. Perfect for old hardware where
blind 'sudo dnf upgrade' might cause driver crashes, black screens,
or system instability.

Features:
- Smart categorization (security, kernel, drivers, etc.)
- Importance analysis using changelogs and CVEs
- Interactive selection with navigation
- Btrfs snapshot protection
- Package preview before confirmation
}

%description %{_description}

%package -n     python3-%{name}
Summary:        %{summary}

%description -n python3-%{name} %{_description}

%prep
%autosetup -n %{name}-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files better_dnf

%check
%pyproject_check_import better_dnf

%files -n python3-%{name}
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/%{name}
%{pyproject_files}

%changelog
* Tue Aug 11 2026 snap-star <rendiyuspramana@gmail.com> - 1.1.1-1
- Bump version to 1.1.1
- GitHub Pages documentation site + deployment workflow
- Sudo/tty fixes: keep controlling terminal (tty_tickets), no double-executed probes
- Snapshot post pairing with --pre-number + verification + standalone fallback
- Remove unused --all flag and unused requests/pyyaml dependencies
- Use PEP 517 pyproject macros (%pyproject_wheel/%pyproject_install/%pyproject_save_files)
  instead of legacy %py3_build/%py3_install, fixing the COPR build (the project has no
  setup.py - it is a pure pyproject.toml/hatchling project)

* Tue Aug 11 2026 snap-star <rendiyuspramana@gmail.com> - 1.0.0-1
- First stable release
- Smart categorization of updates
- Importance analysis using changelogs and CVEs
- Interactive selection with back/cancel navigation
- Package preview before confirmation
- Btrfs snapshot protection (pre/post)
- Security updates detection
- User apps categorization
- Updated help documentation
