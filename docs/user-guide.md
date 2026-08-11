# User Guide

This guide walks through how Better DNF works and how to use it safely — from the first `analyze` to rollback after a bad update.

---

## 🧠 How It Works

1. **Fetch** — Better DNF runs `dnf check-update` (read-only) to discover available updates.
2. **Categorize** — Every update is grouped by type.
3. **Assess** — Importance is derived from changelogs and security (CVE) data.
4. **Choose** — You pick a strategy or individual packages.
5. **Preview** — You see a table of exactly what will be installed.
6. **Snapshot** — A btrfs `pre` snapshot is created before anything changes.
7. **Apply** — The selected packages are updated, with real-time progress.
8. **Post-snapshot** — A `post` snapshot is created after success, paired with the `pre`.

---

## 📊 Update Categories

| Category | Icon | Meaning | When to care |
|----------|------|---------|--------------|
| Security | 🔒 | CVE / vulnerability patches | **Always apply promptly** — active exploits |
| Kernel | 🐧 | Linux kernel + related packages | High risk on old hardware — review carefully |
| Drivers | 🔧 | Hardware drivers (NVIDIA, Mesa, …) | **Highest crash risk** — review carefully |
| System | ⚙️ | Core components (systemd, glibc, …) | Usually safe; occasionally breaking |
| Official | 📦 | Standard Fedora repo packages | Generally safe |
| User Apps | 📱 | User-installed applications | Safe, low risk |
| Other | ❓ | Everything else | Safe by default |

## 🎯 Importance Levels

| Level | Icon | Meaning |
|-------|------|---------|
| Critical | 🔴 | Active exploits / vulnerabilities — install immediately |
| High | 🟠 | Crash fixes, stability — install soon |
| Medium | 🟡 | Bug fixes, improvements — recommended |
| Low | 🟢 | Cosmetic / minor — optional |

The risk assessment panel combines these into an overall level (low / medium / high) and lists the concrete risk factors (e.g. "9 kernel updates", "12 driver updates").

---

## 🔍 The `analyze` Workflow

```bash
better-dnf analyze
```

### Step 1 — Analysis

Better DNF fetches available updates (this can take 30–120s depending on repo metadata) and shows the **Update Summary** table with category counts and the **Risk Assessment** panel.

### Step 2 — Choose a strategy

```
? How would you like to select updates?
  🔒 Security Updates Only
  🐧 Kernel & Drivers Only
  📦 Official Fedora Packages Only
  📱 User Applications Only
  🎯 Custom Selection
  ✅ Update All
  ❌ Cancel
```

Use `↑`/`↓` + `Enter` to select. You can always go **back** or **cancel** — nothing is applied at this stage.

### Step 3 — Review the plan

You see the **Update Plan Summary** (total packages, download size, importance and category breakdown), followed by the **Packages to be Updated** table with current → new versions, importance, and category.

### Step 4 — Confirm

```
? Ready to update N packages? (y/N)
```

Answering **No** cancels safely. Answering **Yes** starts the update:

```
🚀 Applying Updates...
📸 Creating pre-update snapshot... ✓
   (dnf upgrade runs with live progress)
📸 Creating post-update snapshot... ✓
```

After a successful update you get the snapshot IDs, so you can roll back if anything misbehaves later:

```
Snapshot ID: 343
To rollback: better-dnf snapshot rollback 343
```

If the update **fails**, Better DNF asks whether you want to roll back using the snapshot immediately.

### Flags

| Flag | Effect |
|------|--------|
| `-n, --no-snapshot` | Skip snapshot creation (faster, but no rollback safety) |
| `-s, --strategy <name>` | Skip the interactive menu and apply a strategy directly |

---

## 🎯 Update Strategies

| Strategy | Flag value | What it does | Best for |
|----------|-----------|--------------|----------|
| Security | `security` | Only security patches | Servers, anything exposed |
| Kernel & Drivers | `kernel_drivers` | Kernel + driver updates | When you *need* them, reviewed one by one |
| Official | `official` | Official Fedora repo packages | Standard maintenance |
| User Apps | `user_apps` | User-installed apps only | Daily-driver desktop updates |
| Custom | `custom` | Manual category browsing | Full control |
| Update All | `all` | Everything at once | **Not recommended** on old hardware |

```bash
better-dnf analyze -s security        # security only, no menu
better-dnf analyze -s kernel_drivers  # kernel + drivers
better-dnf analyze -s user_apps       # user apps only
```

### Custom selection

Choosing **Custom Selection** opens a category browser:

```
? Which category would you like to review?
  🐧 Kernel (9 packages)
  🔧 Drivers (12 packages)
  ...
  📋 Show All Categories
  ✅ Select All Packages
  ⬅️  Back to Strategy Menu
  ❌ Cancel
```

Inside a category you get a checkbox list. **Critical/High** packages are pre-selected. Use `space` to toggle, `a` to toggle all selections, `i` to invert, `Enter` to confirm — and `⬅️ Back` to return to the strategy menu without committing.

> 💡 **Custom selection** is the recommended way to update the kernel or drivers on old hardware: pick the exact packages you trust, skip the rest.

---

## 📸 Snapshots

Snapshots are point-in-time btrfs backups. Better DNF integrates with **snapper**.

### Snapshot types

| Type | Created when | Purpose |
|------|--------------|---------|
| `pre` | Before an update | System state before changes |
| `post` | After an update | System state after changes |
| `single` | Manual / snapper timeline | Standalone backup |

### Automatic pre/post pairing

During `analyze` (or `security -a`), Better DNF:

1. Creates a `pre` snapshot before applying anything.
2. Creates a `post` snapshot after success, **paired with the pre snapshot** — snapper requires `--pre-number` to link them, and Better DNF passes it automatically.

The result is a complete before/after pair you can diff or roll back to.

### Manual snapshot commands

```bash
# Pre-update snapshot (default)
better-dnf snapshot create

# Post-update snapshot, paired with the latest pre
better-dnf snapshot create post

# Pair with a specific pre snapshot
better-dnf snapshot create post --pre-number 307

# Standalone snapshot
better-dnf snapshot create single

# With a description
better-dnf snapshot create post --description "after kernel update"

# List everything
better-dnf snapshot list

# Roll back
better-dnf snapshot rollback <snapshot-id>
```

### How pairing is verified

Before creating a `post`, Better DNF checks that the pre snapshot **exists**, is **type `pre`**, and is **not already paired**. Instead of snapper's cryptic *"Illegal snapshot"* error you get a clear message. If snapper still refuses the pair, a standalone `single` snapshot is created automatically as a fallback, so you always keep a backup — along with a manual pairing command such as:

```bash
sudo snapper create -t post --pre-number 307
```

### Rollback

```bash
better-dnf snapshot list
better-dnf snapshot rollback <snapshot-id>
```

Rollback restores the entire system state from that snapshot — use it if an update caused black screens, freezes, or driver issues.

> ⚠️ Rollback requires sudo and reboots the relevant btrfs state; keep important snapshots (like the one before a kernel update).

---

## 🔐 Safety Model

| Guarantee | How |
|-----------|-----|
| **Read-only analysis** | `analyze`, `list-updates`, `security` only read repository data |
| **No auto-apply** | Every update requires explicit confirmation |
| **Sudo only when needed** | Write operations prompt for a password via a masked prompt |
| **No double execution** | Sudo credentials are checked with `sudo -n -v` (runs nothing) — commands are never executed as "probes" |
| **Works without a TTY** | Passwords are fed through `sudo -S` when no terminal is available |
| **`tty_tickets` compatible** | The update child keeps the controlling terminal, so Fedora's default sudo credential cache stays visible — no more *"a terminal is required to read the password"* |

> 💡 Sudo is only prompted for **write** operations (applying updates, snapshots, history). Listing and analyzing never require a password.

---

## 🗺️ Recommended Workflows

### Old hardware / custom drivers (the risky case)

```bash
better-dnf analyze            # see what's available and the risk level
better-dnf analyze -s security  # install critical security fixes first
better-dnf analyze -s user_apps # app updates next
# then review kernel/drivers with custom selection, one package at a time
```

If a driver update breaks your display: `better-dnf snapshot rollback <pre-snapshot-id>`.

### Servers

```bash
better-dnf security          # review
better-dnf security -a       # list + apply security updates
better-dnf history           # confirm what changed
```

### Daily driver

```bash
better-dnf analyze -s user_apps   # safe app updates
better-dnf analyze -s official    # official repo packages
```

---

## 🛠️ Troubleshooting

### "a terminal is required to read the password"

This error is **fixed** in current versions. It was caused by the update child being detached from the terminal (setsid), which hid Fedora's tty-keyed sudo cache. The child now runs in its own process group while keeping the controlling terminal. If you still see it, make sure you're running a recent version:

```bash
pip install --upgrade better-dnf    # or: sudo dnf update better-dnf
```

### "Illegal snapshot" when creating a post snapshot

Snapper rejects a `post` when the referenced pre snapshot is missing, isn't type `pre`, is the current snapshot, or **already has a post**. Better DNF now verifies these conditions first and gives a clear message — and falls back to a standalone `single` snapshot so you still get a backup. You can pair manually with:

```bash
sudo snapper create -t post --pre-number <N>
```

### "No packages selected for update"

The strategy you picked matched zero packages (e.g. all user apps are already up to date). Run `better-dnf list-updates` to see what's actually available.

### Stuck after cancelling mid-update

A cancelled DNF transaction may leave a stale lock, and a new `better-dnf analyze` can hang while waiting on it. First make sure no `dnf` or `better-dnf` process is still running:

```bash
pgrep -a dnf        # should show nothing
```

If the lock persists, clear it — the exact path differs between dnf4 and dnf5, and the error message usually names the lock file:

```bash
sudo rm -f /var/cache/dnf/*.pid /var/run/dnf.pid   # dnf4
sudo dnf makecache
```

### Download size shows 0.00 MB or seems wrong

Sizes are fetched per-package after strategy selection (lazy loading) to keep analysis fast. They can be missing for packages whose metadata lacks size info. The actual download size is shown by `dnf` itself during the transaction.

### `better-dnf analyze` feels slow

The first run downloads repo metadata (`dnf check-update`). Subsequent runs are faster because DNF caches it. `analyze` deliberately defers download-size fetching until you've picked a strategy.

### Help text and details

```bash
better-dnf --help                # overview
better-dnf analyze --help        # per-command help with tips and examples
better-dnf snapshot --help
```

---

## ❓ FAQ

**Does Better DNF replace dnf?**
No — it's a front-end that runs `dnf` for you with safer defaults: categorization, risk assessment, selective installs, and snapshots.

**Is it safe on servers?**
Yes. Analysis is read-only, nothing auto-applies, and `security` gives you a one-command path to CVE fixes.

**Do I need btrfs?**
Only for snapshot support. The tool works without it; you just lose the rollback safety net. Consider `snapper` + btrfs to get full protection.

**Can I undo an update without snapshots?**
Yes, via DNF history:

```bash
better-dnf history
sudo dnf history undo <transaction-id>
```
