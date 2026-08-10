# Better DNF

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Fedora](https://img.shields.io/badge/Fedora-35+-294172.svg)](https://getfedora.org/)

A smarter DNF update tool that categorizes updates and lets you choose what to install safely. Perfect for old hardware where blind `sudo dnf upgrade` might cause driver crashes, black screens, or system instability.

## 🎯 Why This Tool?

When you run `sudo dnf upgrade` on an old device, you risk:
- **Driver crashes** causing black screens or freezes
- **Kernel updates** breaking compatibility with legacy hardware
- **Security updates** mixed with experimental features
- **No way to know** which updates are critical vs. optional

**Better DNF** solves this by:
1. Categorizing updates by type (security, kernel, drivers, etc.)
2. Analyzing importance using changelogs and CVEs
3. Letting you selectively choose what to update
4. Creating btrfs snapshots before updates for easy rollback

## ✨ Features

### 📊 Smart Categorization
- 🔒 **Security Updates** - Critical vulnerability patches
- 🐧 **Kernel Updates** - System core updates
- 🔧 **Driver Updates** - Hardware driver updates
- ⚙️ **System Updates** - Core system components
- 📦 **Official Fedora Packages** - Standard repository updates
- 📱 **User Applications** - Desktop apps you installed
- ❓ **Other** - Miscellaneous updates

### 🧠 AI-Powered Importance Analysis
Analyzes changelogs and CVEs to determine:
- 🔴 **Critical** - Must install immediately (security vulnerabilities)
- 🟠 **High** - Should install soon (crash fixes, stability)
- 🟡 **Medium** - Recommended (bug fixes, improvements)
- 🟢 **Low** - Optional (cosmetic changes, minor fixes)

### 🎯 Interactive Selection
- Choose by category or individually
- Pre-selected important updates
- Batch selection support
- Dry-run mode to preview changes

### 📸 Safe Updates with Snapshots
- Automatic btrfs snapshot creation (pre and post update)
- Complete before/after comparison for rollback
- One-click rollback if something goes wrong
- Snapper integration for advanced users

## 🚀 Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/snap-star/better-dnf.git
cd better-dnf

# Install in development mode
pip install -e ".[dev]"

# Or install globally
pip install .
```

### Dependencies

The tool requires these Python packages (automatically installed):
- `typer` - CLI framework
- `rich` - Beautiful terminal output
- `questionary` - Interactive prompts
- `pyyaml` - Configuration files
- `requests` - HTTP requests
- `packaging` - Version parsing

## 📖 Usage

### Basic Analysis

```bash
# Analyze all available updates
better-dnf analyze

# Skip snapshot creation
better-dnf analyze --no-snapshot

# Use a specific strategy
better-dnf analyze --strategy security
better-dnf analyze --strategy kernel_drivers
```

### List Updates

```bash
# List all updates
better-dnf list-updates

# Filter by category
better-dnf list-updates --category security
better-dnf list-updates --category kernel

# Filter by importance
better-dnf list-updates --importance critical
better-dnf list-updates --importance high
```

### Security Updates Only

```bash
# Show security updates
better-dnf security

# Apply security updates directly
better-dnf security --apply
```

### Snapshot Management

```bash
# Create a snapshot manually
better-dnf snapshot create

# List existing snapshots
better-dnf snapshot list

# Rollback to a snapshot
better-dnf snapshot rollback <snapshot-id>
```

### Update History

```bash
# Show recent updates
better-dnf history

# Show more history
better-dnf history --limit 10
```

## 🛡️ Safety Features

### 🔐 Sudo & Permissions

**Read-only operations (no sudo required):**
- `better-dnf analyze` - Analyze updates
- `better-dnf list-updates` - List available updates
- `better-dnf security` - Show security updates

**Write operations (sudo required):**
- `better-dnf analyze --apply` - Apply updates
- `better-dnf snapshot create` - Create btrfs snapshot
- `better-dnf snapshot rollback` - Rollback to snapshot
- `better-dnf history` - View update history

When sudo is needed, your system will prompt for your password (standard Linux behavior).

### Risk Assessment

The tool automatically assesses the risk of applying updates:

```
⚠️  Risk Assessment
─────────────────
Risk Level: MEDIUM

Risk Factors:
• 2 kernel updates
• 5 driver updates
• 12 security updates

Recommendation: Consider creating a snapshot before updating
```

### Update Strategies

Choose how you want to update:

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `security` | Only security patches | Critical systems |
| `kernel_drivers` | Kernel and driver updates | Hardware stability |
| `official` | Official Fedora packages | Standard maintenance |
| `user_apps` | User-installed applications | Desktop updates |
| `custom` | Manual selection | Full control |
| `all` | Everything | Complete update |

### Rollback Support

If an update causes issues:

1. **With btrfs snapshot** (recommended):
   ```bash
   better-dnf snapshot rollback <snapshot-id>
   ```

2. **With dnf history**:
   ```bash
   sudo dnf history undo <transaction-id>
   ```

### 🛡️ Safety Guarantees

✅ **No auto-apply** - Updates are never applied without explicit user confirmation
✅ **Pre-update snapshot** - Creates btrfs snapshot before applying changes
✅ **Post-update snapshot** - Creates snapshot after successful updates
✅ **Complete pre/post pair** - Full before/after comparison for rollback
✅ **Dry-run mode** - Preview changes without applying
✅ **Snapshot verification** - Verifies snapshots exist before rollback
✅ **Read-only by default** - Analysis commands don't modify your system

## ⚙️ Configuration

Create a configuration file at `~/.config/better-dnf/config.yaml`:

```yaml
# Default update strategy
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
importance_threshold: medium  # Only show medium and above
```

## 🖥️ Examples

### Example: Safe Update on Old Hardware

```bash
$ better-dnf analyze

🔍 Better DNF
Analyzing available updates...

📊 Update Summary
┌─────────────────────────┬───────┬──────────┐
│ Category                │ Count │ Status   │
├─────────────────────────┼───────┼──────────┤
│ 🔒 Security Updates     │    12 │ ⚠️ Recommended │
│ 🐧 Kernel Updates       │     2 │ ⚠️ Review │
│ 🔧 Driver Updates       │     5 │ ⚠️ Review │
│ 📦 Official Packages    │    45 │ ✅ Safe   │
│ 📱 User Applications    │    18 │ ✅ Safe   │
└─────────────────────────┴───────┴──────────┘

Update Importance:
  🔴 Critical: 3
  🟠 High: 8
  🟡 Medium: 25
  🟢 Low: 46

⚠️  Risk Assessment
─────────────────
Risk Level: HIGH

Risk Factors:
• 2 kernel updates
• 5 driver updates
• 3 critical security updates

Recommendation: Consider creating a snapshot and updating in batches

How would you like to select updates?
❯ 🔒 Security Updates Only
  🐧 Kernel & Drivers Only
  📦 Official Fedora Packages Only
  📱 User Applications Only
  🎯 Custom Selection
  ✅ Update All
```

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

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .

# Format code
black .
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Fedora Project](https://getfedora.org/) for the amazing distribution
- [DNF](https://dnf.readthedocs.io/) for the powerful package manager
- [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- [Typer](https://typer.tiangolo.com/) for the excellent CLI framework
- [Questionary](https://github.com/tmbo/questionary) for interactive prompts

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/snap-star/better-dnf/issues)
- **Discussions**: [GitHub Discussions](https://github.com/snap-star/better-dnf/discussions)
- **Wiki**: [Project Wiki](https://github.com/snap-star/better-dnf/wiki)

---

**Made with ❤️ for the Fedora community**