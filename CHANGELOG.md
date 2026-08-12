# Changelog

All notable changes to Better DNF will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 🐛 Fixed

- **CI type-check (mypy) failures** - Fixed 13 mypy errors across `parser.py`, `analyzer.py`, `selector.py`, `snapshot.py`, `updater.py`, and `cli.py` (untyped `info` dict, `builtins.any` used as a type, `no-any-return` on questionary results, optional `Popen` stdio handles, and `select_update_strategy` now honestly typed as `str | None`). Also bumped the mypy `python_version` config to 3.10 and pinned `mypy<2.0` (mypy 2.x dropped Python 3.9 support, and the CI matrix still runs 3.9), keeping the Python 3.9 runtime floor intact — the type annotations stay 3.9-safe via `from __future__ import annotations`.
- **CI formatting drift across the Python matrix** - `black` was unpinned, so each matrix job resolved a different version (Python 3.9 got black 25.x, 3.10+ got 26.x) and they disagreed on formatting. The CI workflow now runs ruff/black/mypy once in a dedicated `lint` job (deterministic versions) and keeps the test matrix pytest-only.
- **Python 3.9 runtime crash on `analyze`/`snapshot` etc.** - typer eagerly resolves command-signature annotations with `get_type_hints()`, and `str | None` (PEP 604) raises `TypeError` when evaluated on Python 3.9. All typer-exposed signatures in `cli.py` now use `Optional[str]`; the Python 3.9 CI job passes again.
- **COPR builds never triggered** - `release.yml` created the GitHub release with the repository's `GITHUB_TOKEN`, and GitHub does not create workflow runs from events produced by `GITHUB_TOKEN` (anti-recursion rule), so `copr-build.yml`'s `on: release` never fired (zero runs despite a published v1.1.1 release). The workflow now triggers on tag pushes (`v*` tags) and supports manual `workflow_dispatch` runs; the `release` trigger is kept for releases published manually from the web UI. Also installs `rich` explicitly (copr-cli 2.5 imports it at startup but omits it from its package metadata, so builds crashed with `ModuleNotFoundError`) and uses the copr-cli 2.5 `buildscm` subcommand (the old `build <project> scm` form was removed).
- **COPR package build failed with "can't open file .../setup.py"** - The spec used the legacy `%py3_build`/`%py3_install` macros, which run `python3 setup.py build` — but better-dnf is a pure PEP 517 project (`pyproject.toml` + hatchling) with no `setup.py`, so every COPR build died in `%build`. The spec now uses `%pyproject_wheel`/`%pyproject_install`/`%pyproject_save_files` (plus `%pyproject_check_import`), matching the current Fedora Python guidelines — the `%py3_*` macros are removed in Fedora 45 anyway. BuildRequires are generated dynamically with `%pyproject_buildrequires -r` (buildroots no longer ship pip by default), and the generated file list is referenced with `%files -f %{pyproject_files}` (it expands to a host-side absolute path — listing it as a bare line made rpm look for it inside `%{buildroot}`). Also fixed a bogus weekday in the 1.0.0 changelog entry. Verified locally: `rpmspec -P` parses, the wheel builds, and a clean venv install exposes the `better-dnf` console script and imports v1.1.1.

## [1.1.1] - 2026-08-11

### ✨ Added

- **GitHub Pages documentation site** - New `docs/` MkDocs site (index, user guide, command reference) built with `mkdocs build --strict` and deployed to GitHub Pages by the `docs.yml` workflow on every push to `main`.

### 🐛 Fixed

- **`apply updates` keeps the controlling terminal for sudo** - The `dnf upgrade` child was spawned with `start_new_session=True` (setsid), which detaches from the controlling terminal. Fedora's sudo enables `tty_tickets` by default, keying its credential cache to the controlling terminal, so the detached child couldn't see the credentials just cached by `sudo -n -v` and failed with "a terminal is required to read the password". The child now runs in its own process group via `preexec_fn=os.setpgrp` (Ctrl+C `killpg` cleanup still works) while keeping the terminal.
- **Sudo probes no longer execute the target command** - Authentication was checked by running `sudo -n <command>`, which could execute effectful commands twice (e.g. `snapper create` ran once as a "probe" and once for real — the second attempt failed with snapper's "Illegal snapshot" because the pre snapshot already had a post; the `dnf upgrade` probe had the same double-run risk). Credentials are now checked with `sudo -n -v` (runs nothing) and validated with `sudo -S -v`. A per-command NOPASSWD probe inside `run_sudo` reuses its own result, so commands never run more than once. This also eliminates the spurious double password prompt.
- **`snapshot create post` validates the pre snapshot first** - Reports clear errors when the pre-number is missing, isn't type `pre`, or already has a post snapshot, instead of snapper's cryptic "Illegal snapshot".
- **Standalone fallback for failed post pairing** - If snapper still refuses the pre/post pair, a standalone `single` snapshot is created automatically so a backup always exists, with the reason and a manual pairing command (`sudo snapper create -t post --pre-number <N>`) shown.
- **`--pre-number` CLI flag** - `better-dnf snapshot create post --pre-number <N>` pairs with a specific pre snapshot instead of the latest one.

### 🧹 Removed

- **Unused `--all` flag on `list-updates`** - The option was accepted but had no code effect (listing everything is already the default behavior when no filters are given).
- **Unused `requests` and `pyyaml` dependencies** - Neither is imported anywhere in the codebase; both were declared ahead of planned features (config file support, advisory enrichment). Re-add them when those features land.

### 🧪 Testing

- **231 unit tests** across 7 test files (up from 222):
  - `test_sudo.py` (15) — added: probe never runs effectful commands; NOPASSWD probe reuses its result (single execution); sudo-missing error
  - `test_snapshot.py` (46) — added: pre snapshot verification (missing / wrong type / already paired), standalone fallback, `Pre #` column parsing
  - `test_cli.py` (50) — added: `--pre-number` flag
  - `test_updater.py` (16) — added: Popen keeps the controlling terminal (no `start_new_session`)
- Module coverage: `sudo` 86%, `snapshot` 92%, `updater` 71% (total 84%, `fail_under` gate 80%)

### 🚧 Planned

- [ ] Configuration file support (`~/.config/better-dnf/config.yaml`)
- [ ] Dry-run mode for previewing changes
- [ ] Batch update support
- [ ] Export/import update plans
- [ ] System requirements checking
- [ ] Auto-update checking for better-dnf itself

---

## [1.0.0] - 2026-08-11

### 🎉 First Stable Release

This is the first stable release of Better DNF with complete functionality for safe system updates.

### ✨ Added

#### Navigation System
- ⬅️ **Back navigation** - Return to previous menu in all interactive flows
- ❌ **Cancel options** - Exit without changes from any menu
- 🔄 **Menu looping** - Strategy selection loops until user confirms or cancels

#### Package Preview
- 📦 **Preview table** - See exactly what will be installed before confirming
- 📊 **Importance display** - Color-coded importance levels in preview
- 🏷️ **Category display** - Shows package category in preview table

#### Improved Help Documentation
- 📖 **Comprehensive help** - Detailed help text for all commands
- 💡 **Tips and examples** - Usage tips in help output
- 🎯 **Strategy descriptions** - Clear descriptions for each update strategy

#### Core Features
- 🔍 **Update analysis** - Fetch and analyze available updates
- 📊 **Smart categorization** - Updates grouped by type (security, kernel, drivers, etc.)
- 🧠 **Importance analysis** - CVE and changelog-based risk assessment
- ⚠️ **Risk assessment** - Automatic risk level calculation
- 🎯 **Interactive selection** - Choose packages by category or individually
- 📸 **Snapshot protection** - Pre/post snapshot support for safe rollback
- 📈 **Progress tracking** - Real-time progress during updates

#### Commands
- `better-dnf analyze` - Main analysis and update command
- `better-dnf list-updates` - List available updates with filtering
- `better-dnf security` - Security updates only
- `better-dnf snapshot` - Snapshot management (create/list/rollback)
- `better-dnf history` - Update history viewer
- `better-dnf version` - Version information

### 🔧 Fixed

- **Post-update snapshot now created after successful updates** - The post snapshot was silently skipped because the snapshot ID was guessed via a fragile `snapper list` parse (returning `None`, so the post path never ran). Now uses `snapper create -p` (prints the real snapshot number) and passes `--pre-number` so snapper creates a proper pre/post pair.
- **`snapshot create post` command** - New `better-dnf snapshot create post` (and `-t/--type`) to manually create post snapshots; auto-pairs with the latest `pre` snapshot when no `--pre-number` is given.
- **Snapshot list column parsing** - Fixed misaligned `type`/`date`/`description` columns in `snapshot list` (real snapper columns are `# | Type | Pre # | Date | User | Cleanup | Description | Userdata`); now header-based so `pre`/`post`/`single` types display and pair correctly.
- **Security updates detection** - Fixed parsing of security update info
- **User apps categorization** - Fixed detection of user-installed packages
- **Download size calculation** - Fixed to show actual download sizes
- **Snapshot list display** - Fixed parsing of snapper output format
- **Package name parsing** - Fixed handling of complex package names
- **Sudo without terminal** - Fixed "a terminal is required to read the password" errors by adding masked password prompting + `sudo -S` authentication for all privileged operations (updates, snapshots, history)
- **Sudo retry & NOPASSWD awareness** - Password prompt retries up to 3 times; respects per-command NOPASSWD rules (e.g. snapper) so no unnecessary password prompt

### 🧪 Testing

- **222 unit tests** across 7 test files — full module coverage:
  - `test_cli.py` (49) — all 7 CLI commands (analyze, list-updates, security, snapshot incl. `create post`, history, version), strategy selection, confirmation flow
  - `test_snapshot.py` (41) — create/list/rollback, pre/post pairing with `--pre-number`, snapper + btrfs backends, header-based CSV/table parsing
  - `test_selector.py` (25) — interactive menu navigation (back/cancel/escape), package selection, confirm warnings
  - `test_parser.py` (64) — dnf check-update parsing, categorization, command helpers, enrichment pipeline (**100% module coverage**)
  - `test_updater.py` (15) — apply flow, password feed via `sudo -S`, Ctrl+C/timeout handling
  - `test_analyzer.py` (15) — importance analysis, risk assessment
  - `test_sudo.py` (13) — cached creds, retry, cancel, NOPASSWD probe
  - `test_install.py` (1) — install script
- All subprocess/sudo calls mocked — tests run in ~0.3s, no root or system interaction required
- Run with: `python3 -m pytest tests/`

#### 📈 Coverage Reporting

- Added `[tool.coverage]` configuration to `pyproject.toml` — per-module line coverage via `pytest-cov`
- **84% total line coverage**, `fail_under = 80` gate enforced
- `make test-cov` now generates terminal (weakest-first, with missing lines) + HTML + XML reports
- Module coverage: `__init__` 100%, `parser` 100%, `sudo` 95%, `snapshot` 91%, `models` 88%, `cli` 86%, `analyzer` 79%, `updater` 71%, `selector` 60%
- Added `coverage.xml` / `.coverage.*` to `.gitignore`

### 📝 Changed

- **Improved error messages** - More descriptive error messages
- **Better terminal output** - Enhanced Rich formatting throughout
- **Updated README** - Comprehensive documentation with examples
- **Updated README** - Added Testing section documenting the full test suite (158 tests)

### 🔒 Security

- **Read-only by default** - Analysis commands don't modify system
- **Sudo only when needed** - Only prompts for password on write operations
- **No auto-apply** - Updates require explicit user confirmation

---

## [0.1.0] - 2026-08-01

### 🚀 Initial Release

#### Added
- Basic update analysis functionality
- Package categorization
- Interactive selection
- Snapshot support
- CLI framework with Typer

---

## Versioning Guide

This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

| Version | Meaning |
|---------|---------|
| **Major (X.0.0)** | Incompatible API changes |
| **Minor (0.X.0)** | New functionality (backwards compatible) |
| **Patch (0.0.X)** | Backwards compatible bug fixes |

### Version Bump Rules

- **Major**: Breaking changes to CLI interface or configuration format
- **Minor**: New features, commands, or significant improvements
- **Patch**: Bug fixes, documentation updates, minor improvements

---

*This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.*
