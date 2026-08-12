# 📦 Publishing Better DNF to Fedora

This guide explains how to publish `better-dnf` so users can install it with:
```bash
sudo dnf install better-dnf
```

## 🎯 Two Publishing Paths

| Path | Command | Difficulty | Time to Users |
|------|---------|------------|---------------|
| **COPR** | `dnf copr enable snap-star/better-dnf` | Easy | Hours |
| **Official Fedora** | `dnf install better-dnf` | Hard | Months |

**Recommendation:** Start with COPR, then submit to official Fedora later.

---

## 🚀 Path 1: Fedora COPR (Start Here)

COPR (Cool Other Package Repo) is Fedora's official third-party repository system.

### Step 1: Create Fedora Account

1. Go to [accounts.fedoraproject.org](https://accounts.fedoraproject.org/)
2. Create an account (use username: `snap-star`)
3. Complete the initial account setup

### Step 2: Setup COPR Access

```bash
# Install COPR CLI
sudo dnf install copr-cli
```

`copr-cli` authenticates with an API token stored in `~/.config/copr`. Log in to
[copr.fedorainfracloud.org/api/](https://copr.fedorainfracloud.org/api/) — the page
shows your credentials as a ready-made snippet. Save it as `~/.config/copr`:

```ini
[copr-cli]
login = <login hash>
username = <your username>
token = <token>
copr_url = https://copr.fedorainfracloud.org
```

```bash
chmod 600 ~/.config/copr
copr-cli whoami   # should print your username
```

> ⚠️ Two gotchas:
> - **Never create `~/.config/copr` with `sudo`.** copr-cli runs as your user, and
>   if it can't read the file it silently falls back to GSSAPI (Kerberos) auth —
>   you'll see a wall of `401 Unauthorized` / `gssapi_login` errors and
>   "Can't detect who are you" from `whoami`. Fix a root-owned file with
>   `sudo chown $USER:$USER ~/.config/copr`.
> - **`copr-cli new-api-token` is not a first-time setup command** — it only
>   *refreshes* an existing token and errors with "File ~/.config/copr not found"
>   if no config exists yet.

### Step 3: Create COPR Project

```bash
# Create project for the supported Fedora versions (drop EOL releases)
copr-cli create better-dnf \
    --chroot fedora-43-x86_64 \
    --chroot fedora-44-x86_64 \
    --chroot fedora-rawhide-x86_64 \
    --description "A smarter DNF update tool for Fedora" \
    --instructions "https://github.com/snap-star/better-dnf"
```

### Step 4: Build Package (Recommended: from the GitHub tag)

The bundled GitHub Actions workflow (`copr-build.yml`) runs this automatically on every release, so you normally don't need to do it by hand:

```bash
# Build from the GitHub release tag (no PyPI upload needed)
copr-cli buildscm snap-star/better-dnf --clone-url https://github.com/snap-star/better-dnf --commit v1.1.1

# Alternative: build directly from PyPI (requires publishing to PyPI first)
# copr-cli build snap-star/better-dnf pypi:better-dnf
```

### Step 5: Build from Local Spec File

```bash
# Create source tarball
cd better-dnf
python -m build --sdist
cd ..

# Build SRPM
rpmbuild -bs better-dnf/better-dnf.spec --define "_sourcedir $(pwd)/better-dnf/dist"

# Upload to COPR
copr-cli build snap-star/better-dnf ~/rpmbuild/SOURCES/better-dnf-1.0.0.tar.gz
```

### Step 6: Users Install Your Package

Once built, users can install with:

```bash
# Enable your repository
sudo dnf copr enable snap-star/better-dnf

# Install the package
sudo dnf install better-dnf

# Update when new versions are released
sudo dnf update better-dnf
```

### Step 7: Automate Builds (Included)

This repository ships ready-made GitHub Actions workflows — no webhook setup needed:

- `release.yml` — Creates a GitHub release when you push a `v*` tag
- `copr-build.yml` — Builds that release in COPR automatically (SCM build from the tag)

To use them:

1. Push a version tag: `git tag v1.1.1 && git push origin v1.1.1`
2. Add the `COPR_CONFIG` secret to GitHub (Settings → Secrets and variables → Actions, with the contents of your `~/.config/copr` file)
3. The release and COPR build happen automatically — `copr-build.yml` triggers on the **tag push** (`v*`) and runs `copr-cli buildscm` against that tag

---

## 🏛️ Path 2: Official Fedora Repository

This makes `better-dnf` available to all Fedora users without enabling external repos.

### Prerequisites

- ✅ Package must be open source (MIT license is approved)
- ✅ All dependencies must be in official Fedora repos
- ✅ Package must follow Fedora Packaging Guidelines
- ✅ You need a Fedora Account System (FAS) account

### Step 1: Check Dependencies

Verify all dependencies are available in Fedora:

```bash
# Check each dependency
dnf search python3-typer
dnf search python3-rich
dnf search python3-questionary
dnf search python3-packaging
```

### Step 2: Install Packaging Tools

```bash
sudo dnf install fedpkg rpm-build python3-rpm-macros
```

### Step 3: Create SRPM Locally

```bash
cd better-dnf

# Build source distribution
python -m build --sdist

# Create SRPM
rpmbuild -bs better-dnf.spec \
    --define "_sourcedir $(pwd)/dist" \
    --define "_specdir $(pwd)" \
    --define "_srpmdir $(pwd)/srpms"
```

### Step 4: Request Package Review

1. Go to [Bugzilla](https://bugzilla.redhat.com/)
2. Create a new bug report:
   - Product: Fedora
   - Component: Package Review
   - Summary: Review Request: better-dnf - A smarter DNF update tool
3. Include in the report:
   - Link to your `.spec` file (on GitHub)
   - Link to your `.src.rpm` file
   - Description of the package
   - Link to upstream source

### Step 5: Pass Review

A Fedora packager will review your package. Common feedback:

- Fix spec file issues
- Update license headers
- Add missing dependencies
- Follow naming conventions

### Step 6: Get Sponsored

Once approved, you need a **sponsor** (existing Fedora packager) to:
1. Approve your package
2. Grant you packager access

### Step 7: Import to DistGit

```bash
# Clone your package repo
fedpkg clone better-dnf
cd better-dnf

# Import sources
fedpkg new-sources better-dnf-1.0.0.tar.gz

# Commit and push
git add .
git commit -m "Initial import of better-dnf 1.0.0"
fedpkg push

# Build in Koji
fedpkg build
```

### Step 8: Submit Update

```bash
# Request update to stable repos
fedpkg request-update f41 f42
```

### Step 9: Users Install (Automatic)

Once in stable repos, all Fedora users can install:

```bash
sudo dnf install better-dnf
```

---

## 📋 Packaging Checklist

### For COPR

- [ ] Create Fedora Account
- [ ] Install `copr-cli`
- [ ] Create COPR project
- [ ] Build package (PyPI or SCM)
- [ ] Test installation on clean system
- [ ] Document enable command in README

### For Official Fedora

- [ ] All dependencies in Fedora repos
- [ ] Spec file follows guidelines
- [ ] License is Fedora-approved (MIT ✅)
- [ ] Create SRPM
- [ ] Submit review request
- [ ] Pass review
- [ ] Get sponsored
- [ ] Import to DistGit
- [ ] Build in Koji
- [ ] Submit update via Bodhi

---

## 🔧 Spec File Template

The `better-dnf.spec` file is included in this repository. Key sections (note the
PEP 517 `%pyproject_*` macros — the legacy `%py3_build`/`%py3_install` macros run
`setup.py`, which doesn't exist in this pyproject.toml-only project):

```spec
Name:           better-dnf
Version:        1.1.1
Release:        1%{?dist}
Summary:        A smarter DNF update tool for Fedora

License:        MIT
URL:            https://github.com/snap-star/better-dnf
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel

%generate_buildrequires
%pyproject_buildrequires -r

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files better_dnf

%files -n python3-%{name}
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/%{name}
%{pyproject_files}
```

---

## 📚 Resources

- [Fedora Packaging Guidelines](https://docs.fedoraproject.org/en-US/packaging-guidelines/)
- [Python Packaging Guidelines](https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/)
- [COPR Documentation](https://docs.copr.fedorainfracloud.org/)
- [New Package Process](https://docs.fedoraproject.org/en-US/package-maintainers/New_Package_Process_for_New_Contributors/)
- [Fedora Koji](https://koji.fedoraproject.org/)

---

## 🎯 Recommended Path

1. **Start with COPR** - Get users immediately
2. **Polish the package** - Fix any issues users report
3. **Submit to Fedora** - Get into official repos

This way, users can install immediately via COPR, and later via `dnf install` when it's in official repos.
