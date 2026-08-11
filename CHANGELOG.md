# Changelog

All notable changes to Better DNF will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

- **Security updates detection** - Fixed parsing of security update info
- **User apps categorization** - Fixed detection of user-installed packages
- **Download size calculation** - Fixed to show actual download sizes
- **Snapshot list display** - Fixed parsing of snapper output format
- **Package name parsing** - Fixed handling of complex package names
- **Sudo without terminal** - Fixed "a terminal is required to read the password" errors by adding masked password prompting + `sudo -S` authentication for all privileged operations (updates, snapshots, history)
- **Sudo retry & NOPASSWD awareness** - Password prompt retries up to 3 times; respects per-command NOPASSWD rules (e.g. snapper) so no unnecessary password prompt

### 🧪 Testing

- **209 unit tests** across 7 test files — full module coverage:
  - `test_cli.py` (44) — all 7 CLI commands (analyze, list-updates, security, snapshot, history, version), strategy selection, confirmation flow
  - `test_snapshot.py` (33) — create/list/rollback, snapper + btrfs backends, CSV/pipe parsing
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
- **83% total line coverage**, `fail_under = 80` gate enforced
- `make test-cov` now generates terminal (weakest-first, with missing lines) + HTML + XML reports
- Module coverage: `__init__` 100%, `parser` 100%, `sudo` 95%, `snapshot` 90%, `models` 88%, `cli` 85%, `analyzer` 79%, `updater` 71%, `selector` 60%
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

## [Unreleased]

### Planned Features
- [ ] Configuration file support (`~/.config/better-dnf/config.yaml`)
- [ ] Dry-run mode for previewing changes
- [ ] Batch update support
- [ ] Export/import update plans
- [ ] System requirements checking
- [ ] Auto-update checking for better-dnf itself

---

*This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.*
