# Command Reference

Reference for every `better-dnf` command, option, and value — verified against the CLI source.

```bash
better-dnf --help              # overview + quick start
better-dnf <command> --help    # per-command help with tips and examples
```

---

## 📋 Commands at a Glance

| Command | Purpose | Sudo |
|---------|---------|------|
| [`analyze`](#analyze) | Analyze updates, choose what to install, apply safely | write ops |
| [`list-updates`](#list-updates) | List available updates with filters | no |
| [`security`](#security) | Show and optionally apply security updates | write ops (`--apply`) |
| [`snapshot`](#snapshot) | Create / list / rollback btrfs snapshots | yes |
| [`history`](#history) | Show recent DNF transactions | yes |
| [`version`](#version) | Show installed version | no |

> **Exit behavior:** `Ctrl+C` aborts cleanly at any point — menus show "Operation cancelled by user", while an in-flight update shows "Update cancelled by user". Errors are shown as friendly messages and exit non-zero.

---

## `analyze`

The main command: analyze available updates, assess risk, let you choose what to install, snapshot, and apply.

```bash
better-dnf analyze
better-dnf analyze -s security
better-dnf analyze -n
```

### Options

| Option | Alias | Default | Description |
|--------|-------|---------|-------------|
| `--strategy <name>` | `-s` | *(interactive menu)* | Skip the menu and use a strategy directly |
| `--no-snapshot` | `-n` | `false` | Skip snapshot creation before updates |

### Strategy values for `-s`

| Value | Meaning |
|-------|---------|
| `security` | Only security patches (recommended for servers) |
| `kernel_drivers` | Kernel and driver updates (review carefully) |
| `official` | Official Fedora repository packages only |
| `user_apps` | User-installed applications only |
| `custom` | Manual selection with category browsing |
| `all` | Update everything (⚠️ not for old hardware) |

### Examples

```bash
better-dnf analyze                      # interactive mode
better-dnf analyze -s security          # security updates only
better-dnf analyze -s kernel_drivers    # kernel & drivers only
better-dnf analyze -s official          # official packages only
better-dnf analyze -s user_apps         # user apps only
better-dnf analyze -s custom            # browse categories manually
better-dnf analyze -n                   # skip snapshots (faster)
better-dnf analyze -s all               # everything (not recommended)
```

### Workflow

1. Fetch updates (read-only) → summary + risk assessment
2. Select strategy (or skip with `-s`)
3. Review plan summary + package preview table
4. Confirm (`? Ready to update N packages? (y/N)`)
5. `pre` snapshot → apply with live progress → `post` snapshot

---

## `list-updates`

List available updates, optionally filtered by category and/or importance.

```bash
better-dnf list-updates
better-dnf list-updates -c kernel
better-dnf list-updates -i critical
```

### Options

| Option | Alias | Default | Description |
|--------|-------|---------|-------------|
| `--category <name>` | `-c` | — | Filter by update category |
| `--importance <level>` | `-i` | — | Filter by importance level |
| `--all` | `-a` | `false` | Show all updates without filtering |

### Category values for `-c`

| Value | Meaning |
|-------|---------|
| `security` | Security vulnerability patches (CVE fixes) |
| `kernel` | Linux kernel and related packages |
| `driver` | Hardware drivers (NVIDIA, Mesa, etc.) |
| `system` | Core system components (systemd, glibc) |
| `official` | Standard Fedora repository packages |
| `user_app` | User-installed applications |
| `other` | Miscellaneous packages |

> ⚠️ Note the spelling: the **filter** is `user_app` (singular), while the **analyze strategy** is `user_apps` (plural).

### Importance values for `-i`

| Value | Meaning |
|-------|---------|
| `critical` | Must install immediately (active exploits) |
| `high` | Should install soon (crash fixes, stability) |
| `medium` | Recommended (bug fixes, improvements) |
| `low` | Optional (cosmetic, minor fixes) |

### Examples

```bash
better-dnf list-updates                     # all updates, grouped by category
better-dnf list-updates -c kernel           # kernel updates only
better-dnf list-updates -c driver           # driver updates only
better-dnf list-updates -c user_app         # user applications only
better-dnf list-updates -i critical         # critical updates only
better-dnf list-updates -c security -i high # security + high importance
better-dnf list-updates --all               # everything at once
```

---

## `security`

Show security updates; with `--apply`, list and apply them in one go.

```bash
better-dnf security
better-dnf security -a
```

### Options

| Option | Alias | Default | Description |
|--------|-------|---------|-------------|
| `--apply` | `-a` | `false` | Apply security updates after listing |

### Examples

```bash
better-dnf security        # list security updates
better-dnf security -a     # list + confirm + apply security updates
```

When applying, the same safety flow runs: plan summary → preview → confirmation → `pre` snapshot → apply → `post` snapshot.

---

## `snapshot`

Manage btrfs snapshots (via snapper) for safe rollback.

```bash
better-dnf snapshot create
better-dnf snapshot list
better-dnf snapshot rollback <snapshot-id>
```

### Actions

| Action | Description |
|--------|-------------|
| `create` | Create a snapshot (default type `pre`) |
| `list` | List all available snapshots |
| `rollback` | Roll back to a specific snapshot (requires id) |

### Options (for `create`)

| Option | Alias | Default | Description |
|--------|-------|---------|-------------|
| `--type <type>` | `-t` | `pre` | Snapshot type: `pre`, `post`, or `single` |
| `--pre-number <n>` | — | latest `pre` | Pre snapshot to pair a `post` with |
| `--description <text>` | `-d` | — | Optional description for the snapshot |

### Snapshot types

| Type | Meaning |
|------|---------|
| `pre` | BEFORE an update (system state before changes) |
| `post` | AFTER an update (system state after changes) |
| `single` | Standalone snapshot (timeline / manual) |

### Examples

```bash
better-dnf snapshot create                      # new 'pre' snapshot
better-dnf snapshot create post                 # 'post' paired with the latest pre
better-dnf snapshot create post --pre-number 307  # pair with a specific pre
better-dnf snapshot create single               # standalone snapshot
better-dnf snapshot create -t post -d "after kernel update"
better-dnf snapshot list                        # list all snapshots
better-dnf snapshot rollback 307                # roll back to snapshot #307
```

> 💡 Better DNF auto-creates `pre` + `post` pairs during updates. `create post` is for completing a pair manually (e.g. after a failed update). If pairing is refused, a standalone `single` snapshot is created as a fallback.

---

## `history`

Show recent DNF transactions — useful to verify changes and find a transaction to undo.

```bash
better-dnf history
better-dnf history -l 10
```

### Options

| Option | Alias | Default | Description |
|--------|-------|---------|-------------|
| `--limit <n>` | `-l` | `5` | Number of recent transactions to show |

### Examples

```bash
better-dnf history          # last 5 transactions
better-dnf history -l 10    # last 10
better-dnf history -l 20    # last 20
```

To undo a transaction:

```bash
sudo dnf history undo <transaction-id>
```

---

## `version`

Show the installed version (useful for bug reports).

```bash
better-dnf version
```

Example output:

```
Better DNF v1.0.0
```

---

## 🧭 Interactive Keys

| Key | Action |
|-----|--------|
| `↑` / `↓` | Move between options |
| `space` | Toggle selection (checkbox mode) |
| `a` | Toggle all selections (checkbox mode) |
| `i` | Invert selection (checkbox mode) |
| `enter` | Confirm |
| `esc` | Cancel / exit |
| `⬅️ Back` option | Return to the previous menu |

Every menu includes a way back or a cancel option — you never get trapped in a flow.
