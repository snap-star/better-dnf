# Better DNF

**A smarter DNF update tool for Fedora.** Categorize, assess, and selectively install package updates — so you never blind-`sudo dnf upgrade` your way into a black screen again.

Perfect for old hardware, machines with custom drivers (NVIDIA, Mesa), servers that need careful update management, or anyone who wants control over what gets installed.

> **Why?** A blind `sudo dnf upgrade` on an old device can pull in a kernel or driver update that breaks your display, freezes the system, or leaves you unable to boot. Better DNF shows you **what** is about to change, **how risky** it is, and lets you **choose** — with btrfs snapshots as a safety net.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📊 **Smart categorization** | Updates grouped by type: security, kernel, drivers, system, official, user apps, other |
| 🔍 **Importance analysis** | CVE and changelog-based risk assessment (critical / high / medium / low) |
| ⚠️ **Risk assessment** | Automatic risk level with explicit risk factors before you commit |
| 🎯 **Selective updates** | Interactive selection by category or individual package |
| 📸 **Snapshot protection** | Automatic btrfs `pre`/`post` snapshots for safe rollback |
| 📦 **Package preview** | See exactly what will be installed before confirming |
| 🚫 **No blind upgrades** | Updates require explicit confirmation — nothing auto-applies |
| 🔒 **Read-only analysis** | `analyze`, `list-updates`, and `security` never modify your system |

---

## 🚀 Installation

### Option 1: Fedora COPR (Recommended)

```bash
sudo dnf copr enable snap-star/better-dnf
sudo dnf install better-dnf
```

### Option 2: From Source

```bash
git clone https://github.com/snap-star/better-dnf.git
cd better-dnf

# Install in development mode (editable)
pip install -e .

# Or install globally
pip install .
```

### System Requirements

- **OS:** Fedora 42+ (COPR packages; older releases may work from source)
- **Python:** 3.9+
- **Optional:** `snapper` + a btrfs root for snapshot support

---

## ⚡ Quick Start

```bash
# The main command — analyze, assess, choose, update
better-dnf analyze

# Show security updates only
better-dnf security

# List all available updates
better-dnf list-updates

# View system snapshots
better-dnf snapshot list
```

For the full interactive workflow, strategies, and snapshot management, read the **[User Guide](user-guide.md)**. For every command and option, see the **[Command Reference](command-reference.md)**.

---

## 📚 Documentation

| Page | Contents |
|------|----------|
| [User Guide](user-guide.md) | The `analyze` workflow, update strategies, custom selection, snapshots, rollback, safety, troubleshooting |
| [Command Reference](command-reference.md) | Every command with all options and examples |
| [README](https://github.com/snap-star/better-dnf/blob/master/README.md) | Project overview, badges, and landing content |
| [CHANGELOG](https://github.com/snap-star/better-dnf/blob/master/CHANGELOG.md) | Version history |
| [CONTRIBUTING](https://github.com/snap-star/better-dnf/blob/master/CONTRIBUTING.md) | How to contribute |
| [PUBLISHING](https://github.com/snap-star/better-dnf/blob/master/PUBLISHING.md) | How to publish to Fedora / COPR |

---

## 🗺️ What's Next

- Walk through the [User Guide](user-guide.md) for a guided tour of a safe update.
- Jump straight to the [Command Reference](command-reference.md) for exact usage.
- Report issues or suggest features on [GitHub Issues](https://github.com/snap-star/better-dnf/issues).
