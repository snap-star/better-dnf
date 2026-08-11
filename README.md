# Better DNF

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Fedora](https://img.shields.io/badge/Fedora-35+-294172.svg)](https://getfedora.org/)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/snap-star/better-dnf)

A smarter DNF update tool that categorizes updates and lets you choose what to install safely. Perfect for old hardware where blind `sudo dnf upgrade` might cause driver crashes, black screens, or system instability.

## 🎯 Why Better DNF?

When you run `sudo dnf upgrade` on an old device, you risk:

| Risk | Consequence |
|------|-------------|
| 🔧 **Driver crashes** | Black screens, freezes, display issues |
| 🐧 **Kernel updates** | Breaking compatibility with legacy hardware |
| 🔒 **Security + Features mixed** | No way to separate critical fixes from experiments |
| ❓ **No visibility** | Can't tell which updates are critical vs. optional |

**Better DNF** solves this by:

1. **Categorizing updates** by type (security, kernel, drivers, etc.)
2. **Analyzing importance** using changelogs and CVE databases
3. **Selective updates** - Choose exactly what to install
4. **Snapshot protection** - Btrfs snapshots for safe rollback
5. **No blind upgrades** - Prevents accidental system-breaking updates

## Features

### Smart Categorization

Updates are automatically grouped by type for easy decision-making:

| Category | Icon | Description |
|----------|------|-------------|
| Security | 🔒 | Critical vulnerability patches (CVE fixes) |
| Kernel | 🐧 | Linux kernel and related packages |
| Driver | 🔧 | Hardware drivers (NVIDIA, Mesa, etc.) |
| System | ⚙️ | Core system components (systemd, glibc) |
| Official | 📦 | Standard Fedora repository packages |
| User Apps | 📱 | User-installed applications |
| Other | ❓ | Miscellaneous packages |

### Importance Analysis

Analyzes changelogs and CVEs to determine update priority:

| Level | Icon | When to Install |
|-------|------|-----------------|
| Critical | 🔴 | Immediately (active exploits, vulnerabilities) |
| High | 🟠 | Soon (crash fixes, stability improvements) |
| Medium | 🟡 | Recommended (bug fixes, improvements) |
| Low | 🟢 | Optional (cosmetic changes, minor fixes) |

### Interactive Selection with Navigation

Full navigation support for easy menu traversal:

```
Strategy Menu
├── 🔒 Security Updates Only
├── 🐧 Kernel & Drivers Only
├── 📦 Official Fedora Packages Only
├── 📱 User Applications Only
├── 🎯 Custom Selection ──────────► Category Selection
├── ✅ Update All                      ├── 📋 Security (10)
└── ❌ Cancel                          ├── 📋 Kernel (5)
                                       ├── 📋 Drivers (8)
                                       ├── ⬅️ Back to Strategy Menu
                                       └── ❌ Cancel
```

- ⬅️ **Back** - Return to previous menu
- ❌ **Cancel** - Exit without changes
- **Pre-selected** - Critical and High importance updates
- **Package preview** - See what will be installed before confirming

### Safe Updates with Snapshots

Complete pre/post snapshot protection:

| Snapshot Type | Created When | Purpose |
|---------------|--------------|---------|
| `pre` | Before update | System state before changes |
| `post` | After update | System state after changes |
| `single` | Manual/Timeline | Standalone backup |

- 🔄 **Pre/Post pairs** - Complete before/after comparison
- 🔙 **One-click rollback** - Restore if something breaks
- 🔗 **Snapper integration** - Works with existing snapper setups

## 🚀 Installation

### Option 1: Fedora COPR (Recommended)

```bash
# Enable the repository
sudo dnf copr enable snap-star/better-dnf

# Install better-dnf
sudo dnf install better-dnf
```

### Option 2: From Source

```bash
# Clone the repository
git clone https://github.com/snap-star/better-dnf.git
cd better-dnf

# Install in development mode (editable)
pip install -e .

# Or install globally
pip install .
```

### Quick Install

```bash
# One-liner install
git clone https://github.com/snap-star/better-dnf.git && cd better-dnf && pip install -e .
```

### Dependencies

Automatically installed with pip:

| Package | Purpose |
|---------|---------|
| `typer` | CLI framework with rich help text |
| `rich` | Beautiful terminal output and tables |
| `questionary` | Interactive prompts and menus |
| `pyyaml` | Configuration file support |
| `packaging` | Version parsing and comparison |

### System Requirements

- **OS**: Fedora 35 or later
- **Python**: 3.9 or later
- **Optional**: `snapper` for advanced snapshot management
- **Optional**: `btrfs` for native snapshot support

## Usage

### Main Command: `analyze`

The primary command for safely updating your system:

```bash
# Interactive mode - full menu navigation
better-dnf analyze

# Skip snapshot creation (faster)
better-dnf analyze --no-snapshot

# Direct strategy (skip interactive menu)
better-dnf analyze --strategy security
better-dnf analyze --strategy kernel_drivers
better-dnf analyze --strategy user_apps
better-dnf analyze --strategy official
better-dnf analyze --strategy custom
better-dnf analyze --strategy all
```

### List Updates

```bash
# List all updates grouped by category
better-dnf list-updates

# Filter by category
better-dnf list-updates --category security
better-dnf list-updates --category kernel
better-dnf list-updates --category driver
better-dnf list-updates --category user_app

# Filter by importance
better-dnf list-updates --importance critical
better-dnf list-updates --importance high

# Combine filters
better-dnf list-updates --category security --importance critical

# Show all without filtering
better-dnf list-updates --all
```

### Security Updates

```bash
# List security updates
better-dnf security

# List and apply security updates
better-dnf security --apply
```

### Snapshot Management

```bash
# Create a new snapshot
better-dnf snapshot create

# List all snapshots
better-dnf snapshot list

# Rollback to a specific snapshot
better-dnf snapshot rollback <snapshot-id>
```

### Update History

```bash
# Show last 5 transactions (default)
better-dnf history

# Show more history
better-dnf history --limit 10
better-dnf history --limit 20
```

### Version Info

```bash
# Show version
better-dnf version
```

## Navigation Guide

When using interactive mode, you can navigate through menus:

| Key | Action |
|-----|--------|
| `↑` `↓` | Move between options |
| `Space` | Toggle selection (checkbox mode) |
| `Enter` | Confirm selection |
| `Esc` | Cancel and exit |

### Menu Flow

```
better-dnf analyze
    │
    ▼
┌─────────────────────────────────────┐
│  How would you like to select?      │
│  ├── 🔒 Security Updates Only       │
│  ├── 🐧 Kernel & Drivers Only       │
│  ├── 📦 Official Fedora Packages    │
│  ├── 📱 User Applications Only      │
│  ├── 🎯 Custom Selection ───────────┼──► ┌──────────────────────┐
│  ├── ✅ Update All                  │    │  Select Category      │
│  └── ❌ Cancel                      │    │  ├── 📋 Security (10) │
└─────────────────────────────────────┘    │  ├── 📋 Kernel (5)    │
                                           │  ├── ⬅️ Back          │
                                           │  └── ❌ Cancel        │
                                           └──────────────────────┘
```

## 🛡️ Safety Features

### 🔐 Sudo & Permissions

| Operation | Sudo Required | Description |
|-----------|---------------|-------------|
| `better-dnf analyze` | ❌ | Analyze updates (read-only) |
| `better-dnf list-updates` | ❌ | List available updates |
| `better-dnf security` | ❌ | Show security updates |
| `better-dnf snapshot list` | ✅ | List system snapshots |
| `better-dnf snapshot create` | ✅ | Create new snapshot |
| `better-dnf snapshot rollback` | ✅ | Rollback system state |
| `better-dnf history` | ✅ | View update history |

When sudo is needed, your system will prompt for your password.

### ⚠️ Risk Assessment

The tool automatically assesses the risk of applying updates:

```
⚠️  Risk Assessment
─────────────────────────────────────────
Risk Level: HIGH

Risk Factors:
• 18 critical updates
• 9 kernel updates
• 12 driver updates

Recommendation: Consider creating a snapshot and updating in batches
─────────────────────────────────────────
```

### Update Strategies

| Strategy | Command | Description | Best For |
|----------|---------|-------------|----------|
| Security | `-s security` | Only security patches | Servers, critical systems |
| Kernel/Drivers | `-s kernel_drivers` | Kernel + driver updates | Hardware stability |
| Official | `-s official` | Official Fedora packages | Standard maintenance |
| User Apps | `-s user_apps` | User-installed apps | Desktop updates |
| Custom | `-s custom` | Manual selection | Full control |
| All | `-s all` | Everything | Complete update |

### 🔄 Rollback Support

If an update causes issues, you have two options:

**Option 1: Btrfs Snapshot (Recommended)**
```bash
# List available snapshots
better-dnf snapshot list

# Rollback to a specific snapshot
better-dnf snapshot rollback <snapshot-id>
```

**Option 2: DNF History**
```bash
# List recent transactions
better-dnf history

# Undo a specific transaction
sudo dnf history undo <transaction-id>
```

### 🛡️ Safety Guarantees

| Feature | Status | Description |
|---------|--------|-------------|
| No auto-apply | ✅ | Updates require explicit confirmation |
| Pre-update snapshot | ✅ | Creates snapshot before changes |
| Post-update snapshot | ✅ | Creates snapshot after success |
| Package preview | ✅ | See what will be installed |
| Navigation support | ✅ | Back/Cancel in all menus |
| Read-only analysis | ✅ | Analysis commands don't modify system |

## ⚙️ Configuration

Create a configuration file at `~/.config/better-dnf/config.yaml`:

```yaml
# Default update strategy
# Options: security, kernel_drivers, official, user_apps, custom, all
default_strategy: custom

# Categories to always include
always_include:
  - security
  - kernel

# Categories to always exclude
always_exclude: []

# Create snapshots by default
create_snapshot: true

# Show detailed output
verbose: false

# Importance thresholds
# Options: critical, high, medium, low
importance_threshold: medium
```

## Examples

### Example: Safe Update on Old Hardware

```bash
$ better-dnf analyze

╭──────────────────────────────────────────── Starting Analysis ─────────────────────────────────────────────╮
│ 🔍 Better DNF                                                                                             │
│ Analyzing available updates...                                                                              │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

📊 Update Summary
          📋 Update Summary           
╭──────────────┬───────┬────────────╮
│ Category     │ Count │   Status   │
├──────────────┼───────┼────────────┤
│ 🐧 Kernel    │     9 │ ⚠  Review  │
│ 🔧 Drivers   │    12 │ ⚠  Review  │
│ ⚙  System   │    33 │  ✅ Safe   │
│ 📱 User Apps │    25 │  ✅ Safe   │
│ 📦 Official  │   300 │  ✅ Safe   │
╰──────────────┴───────┴────────────╯

Update Importance:
  🔴 Critical: 18
  🟠 High: 28
  🟡 Medium: 309

╭──────────────────────────────────────────── Risk Assessment ──────────────────────────────────────────────╮
│ Risk Level: HIGH                                                                                          │
│ Consider creating a snapshot and updating in batches                                                      │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

? How would you like to select updates?
❯ 🔒 Security Updates Only
  🐧 Kernel & Drivers Only
  📦 Official Fedora Packages Only
  📱 User Applications Only
  🎯 Custom Selection
  ✅ Update All
  ❌ Cancel
```

### Package Preview Before Confirmation

```
📦 Packages to be Updated
╭──────────────────────┬─────────────────┬─────────────────┬─────────────┬──────────╮
│ Package              │ Current Version │ New Version     │ Importance  │ Category │
├──────────────────────┼─────────────────┼─────────────────┼─────────────┼──────────┤
│ kernel               │ 6.14.10         │ 6.14.11         │ 🔴 Critical │ 🐧 Kernel │
│ nvidia-modprobe      │ 580.173.02      │ 580.173.02      │ 🔴 Critical │ 🔧 Drivers│
│ abrt                 │ 2.17.8          │ 2.17.9          │ 🔴 Critical │ 📦 Official│
│ firefox              │ 153.0.1         │ 153.0.2         │ 🟠 High     │ 📱 User Apps│
╰──────────────────────┴─────────────────┴─────────────────┴─────────────┴──────────╯

? Ready to update 21 packages? (y/N)
```

## 🧪 Testing

Better DNF ships with a comprehensive test suite (**209 tests**, all passing) covering every module and CLI command.

### Test Coverage by Module

| Test File | Tests | Covers |
|-----------|-------|--------|
| `test_cli.py` | 44 | All CLI commands: analyze flow, list-updates, security, snapshot, history, version |
| `test_snapshot.py` | 33 | Snapshot create/list/rollback, snapper & btrfs backends, parsing |
| `test_selector.py` | 25 | Interactive menus: strategy selection, back/cancel navigation, confirmation |
| `test_analyzer.py` | 15 | Importance analysis, categorization, risk assessment |
| `test_updater.py` | 15 | apply_updates flow: sudo password feed, Ctrl+C, timeout, snapshots |
| `test_parser.py` | 64 | DNF output parsing, categorization, command helpers, enrichment pipeline |
| `test_sudo.py` | 13 | Sudo credential handling: cached creds, retry, cancel, NOPASSWD probe |

### Key Test Coverage Highlights

- 🧭 **Navigation** - Back/cancel options and menu looping in all interactive flows
- 🔑 **Sudo without terminal** - Masked password prompt, `sudo -S` stdin feed, 3-attempt retry, NOPASSWD awareness
- ⚡ **Ctrl+C safety** - Graceful process-group termination during updates
- 📊 **CLI flows** - Every command tested end-to-end via `typer.testing.CliRunner`
- 🧱 **Snapshot parsing** - CSV, pipe, and btrfs output formats
- 📦 **Parser at 100%** - Full command-helper, categorization, and enrichment-pipeline coverage

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run the full test suite
pytest

# Run a single module's tests
pytest tests/test_sudo.py
pytest tests/test_cli.py

# Run a single test
pytest tests/test_updater.py::TestApplyUpdatesInterrupts::test_keyboard_interrupt_kills_process_group

# Show collected tests without running
pytest --collect-only
```

All tests mock subprocess/interactive prompts, so no root access or live package repositories are needed.

### 📈 Coverage Reporting

The project uses [`pytest-cov`](https://pytest-cov.readthedocs.io/) to measure line coverage module-by-module. The `[tool.coverage]` settings live in `pyproject.toml`.

```bash
# Terminal report only (shows each module's % + missing lines, enforces the fail_under gate)
pytest --cov=better_dnf

# Terminal + HTML + XML reports (recommended)
make test-cov

# Terminal report with missing lines
pytest tests/ --cov=better_dnf --cov-report=term-missing
```

Reports generated by `make test-cov`:

| File/Dir | Description |
|----------|-------------|
| terminal output | Per-module line coverage, sorted weakest-first, with missing line numbers |
| `htmlcov/index.html` | Interactive browsable report (open in a browser) |
| `coverage.xml` | Machine-readable report used by CI / Codecov |

#### Module Coverage (baseline at 1.0.0)

| Module | Coverage | Notes |
|--------|----------|-------|
| `__init__.py` | 100% | |
| `parser.py` | 100% | DNF output parsing, categorization, enrichment pipeline |
| `sudo.py` | 95% | Credential handling, retry, NOPASSWD probe |
| `snapshot.py` | 90% | Snapper + btrfs backends, parsing |
| `models.py` | 88% | Data models |
| `cli.py` | 85% | CLI commands and flows |
| `analyzer.py` | 79% | Importance & risk analysis |
| `updater.py` | 71% | Update application, interrupts, snapshots |
| `selector.py` | 60% | Interactive menus |
| **Total** | **83%** | `fail_under` gate: 80% |

> 💡 The `fail_under = 80` gate in `pyproject.toml` makes the test command exit non-zero if coverage drops below 80% — this protects the suite in CI. Raise it as coverage improves.

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone the repo
git clone https://github.com/snap-star/better-dnf.git
cd better-dnf

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode (with test dependencies)
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .

# Format code
black .
```

### Project Structure

```
better-dnf/
├── .github/
│   └── workflows/
│       ├── ci.yml           # CI/CD pipeline
│       ├── copr-build.yml   # COPR auto-build
│       └── release.yml      # Release automation
├── src/
│   └── better_dnf/
│       ├── __init__.py      # Package initialization
│       ├── cli.py           # Main CLI commands
│       ├── analyzer.py      # Update analysis logic
│       ├── selector.py      # Interactive selection
│       ├── parser.py        # DNF output parsing
│       ├── updater.py       # Update application
│       ├── snapshot.py      # Snapshot management
│       ├── sudo.py          # Sudo credential handling
│       └── models.py        # Data models
├── tests/
│   ├── test_analyzer.py     # 15 tests
│   ├── test_cli.py          # 44 tests
│   ├── test_parser.py       # 64 tests
│   ├── test_selector.py     # 25 tests
│   ├── test_snapshot.py     # 33 tests
│   ├── test_sudo.py         # 13 tests
│   └── test_updater.py      # 15 tests
├── better-dnf.spec          # RPM spec file
├── CHANGELOG.md             # Version history
├── PUBLISHING.md            # Publishing guide
├── README.md
├── LICENSE
└── pyproject.toml
```

### CI/CD Automation

This project uses GitHub Actions for:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push/PR | Tests, linting, type checking |
| `copr-build.yml` | Release | Auto-build in COPR |
| `release.yml` | Tag push | Create GitHub release |

**To create a new release:**
```bash
git tag v1.0.0
git push origin v1.0.0
```

This automatically:
1. Runs CI tests
2. Builds the package
3. Creates GitHub release
4. Triggers COPR build
5. Publishes to PyPI

## 📞 Support

| Channel | Link |
|---------|------|
| 🐛 Issues | [GitHub Issues](https://github.com/snap-star/better-dnf/issues) |
| 💬 Discussions | [GitHub Discussions](https://github.com/snap-star/better-dnf/discussions) |

---

**Made with ❤️ for the Fedora community** | [GitHub](https://github.com/snap-star/better-dnf)