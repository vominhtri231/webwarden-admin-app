# Webwarden: systemd, Polkit, Packaging Technical Reference

**Date:** 2026-06-24  
**Scope:** Implementation-grade syntax and gotchas for systemd instance units, Polkit authorization, pkexec argument passing, logrotate, .desktop launcher, and install.sh orchestration.  
**Target:** Linux Mint (Ubuntu 24.04), systemd 255+, Polkit 0.105+, unprivileged GTK4 GUI → `pkexec` → `/usr/local/sbin/webwarden` root CLI.

---

## 1. Systemd Templated Instance Units

### 1.1 Instance Unit Basics

**Template naming:** `webwarden-dns@.service` (notice the `@` before `.service`).  
**Instance activation:** `systemctl enable webwarden-dns@alice.service` instantiates the template with instance name `alice`.

### 1.2 Specifier Substitution: %i vs %I

| Specifier | Behavior | Use Case |
|-----------|----------|----------|
| `%i` | Instance name, **escaped** for safe filesystem use (@ → -40, / → -2f) | PIDFile, config file paths, unique identifiers |
| `%I` | Instance name, **verbatim**, unescaped | Service description, command-line args where shell won't interpret special chars |
| `%n` | Full unit name (e.g., `webwarden-dns@alice.service`) | Logging, comments |
| `%N` | Full unit name prefix (e.g., `webwarden-dns@alice`) | Not usually needed |

**Example escaping:** If instance name is `user@domain`, `%i` → `user-40domain` (@ = 0x40).

### 1.3 Per-User DNS Instance Unit Template

**File:** `/etc/systemd/system/webwarden-dns@.service`

```ini
[Unit]
Description=Webwarden DNS proxy for user %I
Documentation=https://webwarden.local/docs
PartOf=webwarden.target
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=%i
Group=%i
WorkingDirectory=/var/lib/webwarden/%i

# dnsmasq will run as the unprivileged user with its own conf and port
ExecStart=/usr/sbin/dnsmasq \
  --no-daemon \
  --conf-file=/etc/webwarden/dns-%i.conf \
  --log-facility=/var/log/webwarden/dns-%i.log \
  --pid-file=/run/webwarden/dns-%i.pid

ExecReload=/bin/kill -HUP $MAINPID

# Automatic restart on crash; avoid loops with StartLimitInterval
Restart=on-failure
RestartSec=5s
StartLimitInterval=60s
StartLimitBurst=3

# Security: no root, read-only /sys and /proc
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
NoNewPrivileges=yes
ProtectKernelTunables=yes
ProtectKernelLogs=yes

StandardOutput=journal
StandardError=journal
SyslogIdentifier=webwarden-dns-%i

[Install]
WantedBy=multi-user.target
```

**Key notes:**
- `User=%i` runs dnsmasq as that user (must exist).
- `%i` in paths is safe for filenames; dnsmasq processes own conf and log per user.
- `ExecReload=/bin/kill -HUP $MAINPID` tells systemd how to reload (used by `systemctl reload`).
- `Restart=on-failure` + `StartLimitBurst=3` prevents restart loops.

### 1.4 One-Shot nftables Ruleset Unit

**File:** `/etc/systemd/system/webwarden-nft.service`

```ini
[Unit]
Description=Webwarden nftables firewall rules
Documentation=https://webwarden.local/docs
PartOf=webwarden.target
After=network-pre.target
Before=network.target
DefaultDependencies=no

[Service]
Type=oneshot
RemainAfterExit=yes

# Validate before loading
ExecStartPre=/usr/sbin/nft -c -f /etc/nftables.d/webwarden.nft
# Load rules
ExecStart=/usr/sbin/nft -f /etc/nftables.d/webwarden.nft
# Flush rules on stop
ExecStop=/usr/sbin/nft flush ruleset

StandardOutput=journal
StandardError=journal
SyslogIdentifier=webwarden-nft

[Install]
WantedBy=multi-user.target
```

**Key notes:**
- `Type=oneshot`: systemd waits for the command to exit; unit considered started immediately.
- `RemainAfterExit=yes`: Unit stays "active" after script exits; allows `systemctl status webwarden-nft` to report "active" even after one-shot completes.
- `ExecStartPre` validates syntax before loading (prevents boot breakage).
- `DefaultDependencies=no` + `Before=network.target` ensures nftables loads before network stack comes up.
- `ExecStop` flushes rules on `systemctl stop webwarden-nft`; optional but clean.

### 1.5 Grouping Unit (webwarden.target)

**File:** `/etc/systemd/system/webwarden.target`

```ini
[Unit]
Description=Webwarden system
Documentation=https://webwarden.local/docs
Wants=webwarden-nft.service
Wants=webwarden-dns@alice.service
Wants=webwarden-dns@bob.service
# ... add per-instance wants as users are added

[Install]
WantedBy=multi-user.target
```

**Usage:**
```bash
# Start all webwarden services at once
systemctl start webwarden.target

# Check status of all
systemctl status webwarden.target
```

---

## 2. Polkit Authorization Policy

### 2.1 Policy File Structure

**Location:** `/usr/share/polkit-1/actions/org.webwarden.admin.policy`

**Permissions:** 644 (world-readable), owned `root:root`.

**Format:** XML with action definitions.

### 2.2 Core Policy: Allow Running webwarden CLI

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
  "http://www.freedesktop.org/software/polkit/policyconfig-1.dtd">
<policyconfig>

  <action id="org.webwarden.admin.run">
    <description>Run Webwarden administration CLI</description>
    <description xml:lang="es">Ejecutar CLI de administración Webwarden</description>
    <message>Authentication required to manage Webwarden</message>
    <message xml:lang="es">Se requiere autenticación para administrar Webwarden</message>
    <icon_name>application-x-executable</icon_name>

    <annotate key="org.freedesktop.policykit.exec.path">/usr/local/sbin/webwarden</annotate>
    <annotate key="org.freedesktop.policykit.exec.allow_gui">true</annotate>

    <defaults>
      <allow_any>no</allow_any>
      <allow_inactive>no</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
  </action>

</policyconfig>
```

**Breakdown:**
- `<action id="org.webwarden.admin.run">`: Unique identifier; used in rules and pkexec.
- `<description>`: User-facing message explaining what the action does.
- `<icon_name>`: Used by Polkit authentication dialogs (e.g., GNOME unlock dialog).
- `<annotate key="org.freedesktop.policykit.exec.path">`: The binary path pkexec must match. **Gotcha:** This is checked by pkexec; the actual binary path passed to pkexec must match this value exactly.
- `<annotate key="org.freedesktop.policykit.exec.allow_gui">true</annotate>`: Allows GUI authentication (vs. terminal-only).
- `<defaults>`:
  - `<allow_any>no</allow_any>`: Non-local sessions (SSH, VNC) → deny without auth.
  - `<allow_inactive>no</allow_inactive>`: Inactive sessions → deny without auth.
  - `<allow_active>auth_admin_keep</allow_active>`: Active (logged-in) sessions → require admin auth, but cache for ~5 min (like `sudo -l`).

### 2.3 Authentication Keywords

| Keyword | Behavior | Use Case |
|---------|----------|----------|
| `no` | Always deny | Disable action for unprivileged users |
| `yes` | Always allow (no auth) | Non-critical actions |
| `auth_self` | Authenticate as **own user** | User-specific resource access |
| `auth_admin` | Authenticate as **admin/sudoer** | Privileged operations (ask each time) |
| `auth_admin_keep` | Like `auth_admin` but **cache for ~5 min** | Privileged operations with repeated access |

For webwarden: `auth_admin_keep` is standard — unprivileged user unlocks once, then has 5 min of cached authorization.

### 2.4 Group-Gating via Rules (Optional)

If you want to restrict authorization to specific groups (e.g., only `sudo` or `adm` group members), use a **rules.d JavaScript file** instead of group tags in the .policy file.

**Location:** `/etc/polkit-1/rules.d/50-webwarden-admin.rules`

**Permissions:** 644, owned `root:root`.

```javascript
polkit.addRule(function(action, subject) {
    // Action ID matches
    if (action.id == "org.webwarden.admin.run") {
        // Check if subject is in sudoers/admin group
        if (subject.isInGroup("sudo") || subject.isInGroup("adm")) {
            return polkit.Result.AUTH_ADMIN_KEEP;
        }
        // Deny non-group members
        return polkit.Result.NO;
    }
});
```

**Result values:**
- `polkit.Result.YES`: Allow immediately.
- `polkit.Result.NO`: Deny.
- `polkit.Result.AUTH_SELF`: Require self auth.
- `polkit.Result.AUTH_ADMIN`: Require admin auth (ask each time).
- `polkit.Result.AUTH_ADMIN_KEEP`: Require admin auth with 5-min cache.

**When to use rules.d:**
- Group membership checks.
- Dynamic policies (time-based, context-aware).
- Complex logic.

**When to use .policy only:**
- Simple action definitions.
- Avoid rules.d if not needed (reduces complexity).

For webwarden: Start with .policy only; add rules.d if you need group gating.

---

## 3. pkexec Argument Passing

### 3.1 How pkexec Works

1. **No shell invocation:** `pkexec /usr/local/sbin/webwarden domain.com alice` passes args as-is; **no shell parsing**.
2. **PATH search (if path not absolute):** pkexec searches PATH only if the executable is not absolute; since we use `/usr/local/sbin/webwarden` (absolute), PATH is not consulted.
3. **Environment scrubbing:** pkexec **does NOT inherit user's environment by default**. Key variables like `HOME`, `SHELL`, `DISPLAY` may be reset or sanitized.
4. **Argv[0] matching:** Only `argv[0]` (the program name) is validated by pkexec against the `.policy` annotations (`exec.path`, `exec.argv1`). Additional args (`argv[1]`, `argv[2]`, ...) are **passed as-is**, untouched.

### 3.2 Argv Safety for GUI

Since pkexec does not parse a shell, passing arguments directly is safe:

```python
# In GTK4 GUI (unprivileged)
import subprocess
import os

# Safe: no shell interpretation
args = [
    "pkexec",
    "/usr/local/sbin/webwarden",
    "dns-add-rule",
    "example.com",      # argv[2]
    "192.168.1.100",    # argv[3]
]
result = subprocess.run(args, capture_output=True, text=True)
```

**This is safe because:**
- No shell (`shell=False` implicit).
- Each arg is a separate list element; no word-splitting or quote interpretation.
- Special characters (spaces, `$`, backticks, etc.) in `"example.com"` are literal.

### 3.3 Exec.argv1 Annotation Gotcha

**Only argv[1] (the first argument to the binary) is matched.**

```xml
<!-- CORRECT: matches only argv[1] -->
<annotate key="org.freedesktop.policykit.exec.argv1">subcommand</annotate>
```

If you call:
```bash
pkexec /usr/local/sbin/webwarden subcommand arg1 arg2
```

Polkit checks: does `argv[1]` == `"subcommand"`? If yes, authorization proceeds. `arg1`, `arg2` are **not checked** and not constrained.

**Use case:** If webwarden has many subcommands (dns-add-rule, dns-rm-rule, nft-reload), you could create separate actions per subcommand:

```xml
<action id="org.webwarden.admin.dns-add">
  <annotate key="org.freedesktop.policykit.exec.path">/usr/local/sbin/webwarden</annotate>
  <annotate key="org.freedesktop.policykit.exec.argv1">dns-add-rule</annotate>
  ...
</action>

<action id="org.webwarden.admin.dns-rm">
  <annotate key="org.freedesktop.policykit.exec.path">/usr/local/sbin/webwarden</annotate>
  <annotate key="org.freedesktop.policykit.exec.argv1">dns-rm-rule</annotate>
  ...
</action>
```

Then each subcommand can have different auth requirements.

### 3.4 Environment Notes

The webwarden CLI should **not rely on** inherited environment variables:
- `$HOME`: Likely set to the unprivileged user's home; use absolute paths.
- `$PATH`: Not inherited reliably; hardcode paths to tools.
- `$LD_LIBRARY_PATH`: May be sanitized; avoid dynamic library loading from user-writable paths.

**Recommendation:** webwarden CLI should validate all inputs and use absolute paths for external tools (dnsmasq, nft, systemctl).

---

## 4. logrotate Configuration

### 4.1 logrotate File for Webwarden

**Location:** `/etc/logrotate.d/webwarden`

**Permissions:** 644, owned `root:root`.

```
/var/log/webwarden/dns-*.log
/var/log/webwarden/nft.log
/var/log/webwarden/webwarden.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    sharedscripts
    
    postrotate
        # Signal all dnsmasq instances to close/reopen log files
        for pidfile in /run/webwarden/dns-*.pid; do
            if [ -f "$pidfile" ]; then
                kill -USR2 $(cat "$pidfile") 2>/dev/null || true
            fi
        done
    endscript
}
```

### 4.2 Directives Explained

| Directive | Value | Purpose |
|-----------|-------|---------|
| `weekly` | — | Rotate logs weekly (default: daily). |
| `rotate` | 4 | Keep 4 rotated copies (dns-alice.log, dns-alice.log.1.gz, .log.2.gz, .log.3.gz, .log.4.gz). |
| `compress` | — | gzip rotated logs. |
| `delaycompress` | — | Delay compression until next rotation cycle (important for signal-based reopening). |
| `missingok` | — | Don't error if log file doesn't exist (e.g., first install). |
| `notifempty` | — | Don't rotate if log is empty. |
| `copytruncate` | — | Copy file, then truncate original (vs. move + signal). Simplifies dnsmasq handling. |
| `sharedscripts` | — | Run `postrotate` once per file group (not per log). |

### 4.3 SIGUSR2 Signal for dnsmasq

**Signal:** `SIGUSR2` (not SIGHUP; SIGHUP is already used by dnsmasq for config reload).

When dnsmasq receives `SIGUSR2` with `--log-facility=/path/to/file`, it:
1. Closes the current log file.
2. Opens the new log file (same path; logrotate has already moved the old one).
3. Continues writing.

**Alternative:** `copytruncate` (shown above) copies the log, then truncates it in-place. This avoids signals but is less clean for TCP connections; `delaycompress` mitigates the TCP issue.

### 4.4 Directory Setup

**Create at install time:**
```bash
mkdir -p /var/log/webwarden
chmod 750 /var/log/webwarden
chown root:adm /var/log/webwarden
```

Ownership `root:adm` allows `adm` group members (often sudoers) to read logs without running as root.

---

## 5. Desktop Launcher (.desktop File)

### 5.1 GTK4 GUI Launcher

**Location:** `/usr/share/applications/webwarden-admin.desktop`

**Permissions:** 644, owned `root:root`.

```ini
[Desktop Entry]
Type=Application
Version=1.0

Name=Webwarden Admin
Comment=Manage DNS filtering and firewall rules
Icon=webwarden
Categories=System;Utility;Network;

Exec=webwarden-admin-gui
Terminal=false
StartupNotify=true
```

### 5.2 Desktop Entry Fields

| Field | Value | Notes |
|-------|-------|-------|
| `Type` | `Application` | Standard value for executable launchers. |
| `Name` | `Webwarden Admin` | Displayed in application menus. |
| `Comment` | `Manage DNS filtering...` | Tooltip/description. |
| `Icon` | `webwarden` | Icon name (e.g., `webwarden.svg` in `/usr/share/icons/`), or full path. |
| `Categories` | `System;Utility;Network;` | Menu placement; semicolon-separated. |
| `Exec` | `webwarden-admin-gui` | Command to run (absolute path or in `$PATH`). |
| `Terminal` | `false` | No terminal window (GUI only). |
| `StartupNotify` | `true` | Show "launching..." indicator. |

### 5.3 Important Notes

- **Exec path:** Can be absolute (`/usr/bin/webwarden-admin-gui`) or relative (assumed in `$PATH`). Use absolute for clarity.
- **GUI invocation:** The launcher runs the GUI directly; the GUI internally calls `pkexec /usr/local/sbin/webwarden` for privileged operations.
- **Icon:** Provide a `.svg` icon at `/usr/share/icons/hicolor/scalable/apps/webwarden.svg` for crisp display.

---

## 6. Install.sh and Orchestration

### 6.1 Install Script Skeleton

**File:** `./install.sh` (in git repo root)

```bash
#!/bin/bash
set -e

# Color output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# === Step 1: Check prerequisites ===
log_info "Checking prerequisites..."

if ! command -v dnsmasq &> /dev/null; then
    log_error "dnsmasq not found. Install: sudo apt install dnsmasq"
    exit 1
fi

if ! command -v nft &> /dev/null; then
    log_error "nft not found. Install: sudo apt install nftables"
    exit 1
fi

if ! command -v systemctl &> /dev/null; then
    log_error "systemd not found."
    exit 1
fi

log_info "Prerequisites OK."

# === Step 2: Install binaries ===
log_info "Installing binaries..."
install -D -m 755 ./src/cli/webwarden /usr/local/sbin/webwarden
install -D -m 755 ./src/gui/webwarden-admin-gui /usr/local/bin/webwarden-admin-gui
log_info "Binaries installed."

# === Step 3: Install nftables rules ===
log_info "Installing nftables rules..."
mkdir -p /etc/nftables.d
install -D -m 644 ./etc/nftables.d/webwarden.nft /etc/nftables.d/webwarden.nft

# Validate before proceeding
log_info "Validating nftables rules..."
if ! nft -c -f /etc/nftables.d/webwarden.nft; then
    log_error "nftables validation failed. Check /etc/nftables.d/webwarden.nft"
    exit 1
fi
log_info "nftables rules validated."

# === Step 4: Install systemd units ===
log_info "Installing systemd units..."
install -D -m 644 ./etc/systemd/system/webwarden.target /etc/systemd/system/webwarden.target
install -D -m 644 ./etc/systemd/system/webwarden-dns@.service /etc/systemd/system/webwarden-dns@.service
install -D -m 644 ./etc/systemd/system/webwarden-nft.service /etc/systemd/system/webwarden-nft.service

# Reload systemd daemon
log_info "Reloading systemd daemon..."
systemctl daemon-reload

# Enable units (but don't start yet)
log_info "Enabling systemd units..."
systemctl enable webwarden.target
systemctl enable webwarden-nft.service

log_info "Systemd units installed and enabled."

# === Step 5: Install Polkit policy ===
log_info "Installing Polkit policy..."
install -D -m 644 ./etc/polkit-1/actions/org.webwarden.admin.policy /usr/share/polkit-1/actions/org.webwarden.admin.policy
log_info "Polkit policy installed."

# Optional: Install rules.d for group gating
if [ -f ./etc/polkit-1/rules.d/50-webwarden-admin.rules ]; then
    log_info "Installing Polkit rules..."
    install -D -m 644 ./etc/polkit-1/rules.d/50-webwarden-admin.rules /etc/polkit-1/rules.d/50-webwarden-admin.rules
    log_info "Polkit rules installed."
fi

# === Step 6: Install logrotate config ===
log_info "Installing logrotate configuration..."
install -D -m 644 ./etc/logrotate.d/webwarden /etc/logrotate.d/webwarden
log_info "logrotate config installed."

# === Step 7: Create log directory ===
log_info "Creating log directory..."
mkdir -p /var/log/webwarden
chmod 750 /var/log/webwarden
chown root:adm /var/log/webwarden
log_info "Log directory created and configured."

# === Step 8: Install .desktop file ===
log_info "Installing desktop launcher..."
install -D -m 644 ./etc/applications/webwarden-admin.desktop /usr/share/applications/webwarden-admin.desktop
log_info "Desktop launcher installed."

# Optional: Install icon
if [ -f ./etc/icons/webwarden.svg ]; then
    log_info "Installing application icon..."
    install -D -m 644 ./etc/icons/webwarden.svg /usr/share/icons/hicolor/scalable/apps/webwarden.svg
    log_info "Icon installed."
fi

# === Step 9: Verify installation ===
log_info "Verifying installation..."

# Check binaries
if [ ! -f /usr/local/sbin/webwarden ]; then
    log_error "CLI binary not installed."
    exit 1
fi

if [ ! -f /usr/local/bin/webwarden-admin-gui ]; then
    log_error "GUI binary not installed."
    exit 1
fi

# Check Polkit policy
if [ ! -f /usr/share/polkit-1/actions/org.webwarden.admin.policy ]; then
    log_error "Polkit policy not installed."
    exit 1
fi

# Check systemd units
if ! systemctl list-unit-files | grep -q webwarden; then
    log_error "Systemd units not installed."
    exit 1
fi

log_info "Installation verified."

# === Final Summary ===
log_info "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Create per-user systemd instances:"
echo "   sudo systemctl enable webwarden-dns@alice.service"
echo "   sudo systemctl enable webwarden-dns@bob.service"
echo ""
echo "2. Start services:"
echo "   sudo systemctl start webwarden.target"
echo ""
echo "3. Launch GUI:"
echo "   webwarden-admin-gui"
echo ""
```

### 6.2 Uninstall Script Skeleton

**File:** `./uninstall.sh`

```bash
#!/bin/bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_info "Removing Webwarden..."

# Stop services
log_info "Stopping services..."
systemctl stop webwarden.target 2>/dev/null || true
systemctl disable webwarden.target 2>/dev/null || true
systemctl disable webwarden-nft.service 2>/dev/null || true

# Remove systemd units
log_info "Removing systemd units..."
rm -f /etc/systemd/system/webwarden.target
rm -f /etc/systemd/system/webwarden-dns@.service
rm -f /etc/systemd/system/webwarden-nft.service
systemctl daemon-reload

# Remove binaries
log_info "Removing binaries..."
rm -f /usr/local/sbin/webwarden
rm -f /usr/local/bin/webwarden-admin-gui

# Remove Polkit policy
log_info "Removing Polkit policy..."
rm -f /usr/share/polkit-1/actions/org.webwarden.admin.policy
rm -f /etc/polkit-1/rules.d/50-webwarden-admin.rules

# Remove logrotate config
log_info "Removing logrotate config..."
rm -f /etc/logrotate.d/webwarden

# Remove .desktop file
log_info "Removing desktop launcher..."
rm -f /usr/share/applications/webwarden-admin.desktop
rm -f /usr/share/icons/hicolor/scalable/apps/webwarden.svg

# Remove nftables rules (optional; ask user)
read -p "Remove nftables rules? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f /etc/nftables.d/webwarden.nft
fi

# Remove log directory (optional; ask user)
read -p "Remove log directory and logs? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf /var/log/webwarden
fi

log_info "Removal complete."
```

### 6.3 Install Script Best Practices

| Practice | Why |
|----------|-----|
| **Check prerequisites first** | Fail early; don't partially install. |
| **Use `install -D` for files** | Creates parent dirs; handles permissions and ownership in one step. |
| **Validate configs before activation** | `nft -c -f`, `dnsmasq --test`. Prevent boot breakage. |
| **`systemctl daemon-reload` before enable** | Picks up new unit files. |
| **Don't `start` units; only `enable`** | Users may not want services running immediately. |
| **Idempotent operations** | Script should succeed even if run twice. Use `-f` flags to overwrite. |
| **Log every step** | Helps debugging. |
| **Verify installation** | Check that critical files exist and units are enabled. |

### 6.4 Idempotency Patterns

```bash
# Safe to run multiple times:
install -D -m 644 source dest      # Overwrites without error
mkdir -p /var/log/webwarden        # Succeeds if exists
chmod 750 /var/log/webwarden       # Idempotent
chown root:adm /var/log/webwarden  # Idempotent
systemctl daemon-reload            # Idempotent
systemctl enable unit.service      # Idempotent (just creates symlink)
```

**Pattern to avoid:**
```bash
# NOT idempotent (fails if dir exists):
mkdir /var/log/webwarden

# NOT idempotent (fails if file exists):
cp source dest
```

---

## 7. Validation Checklist for Deployment

Use this before `systemctl start webwarden.target`:

```bash
#!/bin/bash

echo "=== Webwarden Pre-Deployment Validation ==="

# 1. nftables syntax
echo "[1/5] Validating nftables rules..."
if ! nft -c -f /etc/nftables.d/webwarden.nft; then
    echo "FAIL: nftables rules invalid"
    exit 1
fi
echo "OK: nftables rules valid"

# 2. dnsmasq config (per-user; sample)
echo "[2/5] Validating dnsmasq config (alice)..."
if [ -f /etc/webwarden/dns-alice.conf ]; then
    if ! dnsmasq --test --conf-file=/etc/webwarden/dns-alice.conf; then
        echo "FAIL: dnsmasq config invalid"
        exit 1
    fi
fi
echo "OK: dnsmasq config valid"

# 3. Systemd unit files
echo "[3/5] Checking systemd units..."
if ! systemctl list-unit-files | grep -q webwarden; then
    echo "FAIL: systemd units not found"
    exit 1
fi
echo "OK: systemd units found"

# 4. Polkit policy
echo "[4/5] Checking Polkit policy..."
if [ ! -f /usr/share/polkit-1/actions/org.webwarden.admin.policy ]; then
    echo "FAIL: Polkit policy not found"
    exit 1
fi
echo "OK: Polkit policy found"

# 5. Log directory
echo "[5/5] Checking log directory..."
if [ ! -d /var/log/webwarden ] || [ $(stat -c '%a' /var/log/webwarden) != 750 ]; then
    echo "FAIL: log directory missing or bad permissions"
    exit 1
fi
echo "OK: log directory OK"

echo ""
echo "=== All checks passed. Ready for deployment. ==="
```

---

## 8. Gotchas and Edge Cases

### 8.1 Systemd Instance Substitution

**Gotcha:** `%i` is escaped; `%I` is verbatim. If user name is `user@domain`:
- `%i` in path: `/run/webwarden/dns-user-40domain.pid` (safe for filesystem).
- `%I` in description: "Webwarden DNS proxy for user user@domain" (readable).

**Mitigation:** Use `%i` in file paths; `%I` in descriptions.

### 8.2 Polkit Annotation Matching

**Gotcha:** `exec.path` must match exactly. If you specify `/usr/local/sbin/webwarden` in the policy, then `pkexec /usr/local/sbin/webwarden` works, but `pkexec webwarden` (from PATH) does not.

**Mitigation:** Always use absolute paths in both .policy annotation and GUI code.

### 8.3 pkexec and Environment

**Gotcha:** `$HOME`, `$PATH`, `$LD_LIBRARY_PATH` are sanitized by pkexec. webwarden CLI cannot rely on inherited environment.

**Mitigation:** Hardcode tool paths (e.g., `/usr/bin/systemctl`, `/usr/sbin/nft`) in the CLI.

### 8.4 logrotate and TCP Connections

**Gotcha:** If dnsmasq has long-lived TCP connections, the old log file remains open in child processes for up to 150s after rotation. Compression too soon can cause issues.

**Mitigation:** Use `delaycompress` to delay gzip to the next rotation cycle.

### 8.5 systemd daemon-reload Required

**Gotcha:** After copying new unit files, systemd doesn't auto-detect them. `systemctl daemon-reload` is required.

**Mitigation:** Always call `systemctl daemon-reload` in install.sh after installing unit files.

### 8.6 Polkit Rules.d Cache Invalidation

**Gotcha:** Changes to `/etc/polkit-1/rules.d/*.rules` may not take effect immediately. Polkit caches decision data.

**Mitigation:** After updating rules.d, run `systemctl restart polkit` (or restart the user session).

### 8.7 nftables Load Order

**Gotcha:** If nftables rules reference kernel modules that aren't loaded, loading fails. Example: `ct helper` rules need kernel support.

**Mitigation:** Test on target OS. Use `ExecStartPre` for validation before `ExecStart`.

### 8.8 Group Membership Timing

**Gotcha:** If using Polkit rules.d to gate by group (e.g., `sudo` group), the user must log in after being added to the group. Group membership is cached per login session.

**Mitigation:** Ask user to log out and back in after adding to group. Alternatively, use `pkexec -u <user>` to validate.

---

## 9. Quick Reference: File Locations

| File | Location | Permissions | Owner | Purpose |
|------|----------|-------------|-------|---------|
| CLI binary | `/usr/local/sbin/webwarden` | 755 | root:root | Root CLI |
| GUI binary | `/usr/local/bin/webwarden-admin-gui` | 755 | root:root | Unprivileged GUI |
| systemd template | `/etc/systemd/system/webwarden-dns@.service` | 644 | root:root | Per-user DNS instance |
| systemd nft | `/etc/systemd/system/webwarden-nft.service` | 644 | root:root | One-shot nftables |
| systemd target | `/etc/systemd/system/webwarden.target` | 644 | root:root | Service grouping |
| nftables rules | `/etc/nftables.d/webwarden.nft` | 644 | root:root | Firewall rules |
| dnsmasq per-user | `/etc/webwarden/dns-<user>.conf` | 644 | root:root | Per-user DNS config |
| Polkit policy | `/usr/share/polkit-1/actions/org.webwarden.admin.policy` | 644 | root:root | Authorization policy |
| Polkit rules.d | `/etc/polkit-1/rules.d/50-webwarden-admin.rules` | 644 | root:root | Optional rules |
| logrotate | `/etc/logrotate.d/webwarden` | 644 | root:root | Log rotation |
| .desktop file | `/usr/share/applications/webwarden-admin.desktop` | 644 | root:root | Launcher |
| Application icon | `/usr/share/icons/hicolor/scalable/apps/webwarden.svg` | 644 | root:root | Icon |
| Log directory | `/var/log/webwarden` | 750 | root:adm | Logs |
| Log files | `/var/log/webwarden/*.log` | 640 | root:adm | Per-service logs |
| PID files | `/run/webwarden/*.pid` | 644 | user:user | Runtime PID tracking |
| Runtime dir | `/run/webwarden` | 755 | root:root | Runtime directory |

---

## 10. Unresolved Questions & Caveats

1. **Per-user dnsmasq config generation:** How does webwarden generate `/etc/webwarden/dns-<user>.conf`? This research assumes configs exist; actual generation logic not addressed.

2. **User/group creation for dnsmasq:** Should install.sh create system users for dnsmasq instances, or assume users exist? If creating, `useradd` vs. UPG (user private group)?

3. **nftables rule structure:** Specific nft rules for DNS proxy and TCP/UDP port forwarding are not detailed; implementation depends on network topology and filtering requirements.

4. **GUI authentication caching:** Polkit caches for ~5 min. If the GUI makes multiple `pkexec` calls within that window, subsequent calls should not re-prompt. Verify GTK4 + Polkit integration handles this correctly.

5. **Log permissions for adm group:** Is `adm` group present on all systems? On some minimal installs, it may not exist. Fallback strategy?

6. **systemd socket activation:** Could webwarden CLI be exposed via a socket + activation unit instead of direct pkexec? This research uses direct pkexec; socket approach is more complex but decouples privilege escalation from process lifetime.

7. **Sudo vs. Polkit:** Why not just wrap the CLI in `sudo`? Polkit integrates with desktop session, shows auth dialogs in GUI context; sudo is CLI-focused. For desktop apps, Polkit is standard, but consider if the project needs both.

8. **Rollback strategy:** If install.sh fails partway (e.g., systemd unit invalid), does it clean up partial state? Current skeleton does not include rollback; may need `trap` for cleanup on error.

---

## Sources

- [Systemd Unit Files: Working with systemd unit files to customize and optimize your system](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_systemd_unit_files_to_customize_and_optimize_your_system/assembly_working-with-systemd-unit-files_working-with-systemd)
- [systemd: Template unit files - Fedora Magazine](https://fedoramagazine.org/systemd-template-unit-files/)
- [Creating templated Systemd services - iBug](https://ibug.io/blog/2019/07/systemd-service-template/)
- [How to Implement systemd Template Units for Multi-Instance Services](https://oneuptime.com/blog/post/2026-03-04-implement-systemd-template-units-for-dynamic-multi-instance-services/view)
- [What sysadmins need to know about systemd's oneshot service type](https://www.redhat.com/en/blog/systemd-oneshot-service)
- [Simple vs Oneshot - Choosing a systemd Service Type](https://trstringer.com/simple-vs-oneshot-systemd-service/)
- [Polkit - ArchWiki](https://wiki.archlinux.org/title/Polkit)
- [Linux Polkit: Implementing user space authorization on embedded platforms](https://www.timesys.com/security/linux-polkit-implementing-user-space-authorization-on-embedded-platforms/)
- [pkexec: Execute a command as another user](https://www.mankier.com/1/pkexec)
- [How to rotate dnsmasq log files - Red Hat Customer Portal](https://access.redhat.com/solutions/7127311)
- [SIGUSR2 signal to use alternative logrotate strategies](https://discourse.pi-hole.net/t/sigusr2-signal-to-use-alternative-logrotate-strategies/33778)
- [dnsmasq-logrotate: logrotate setup for dnsmasq](https://github.com/m-grant-prg/dnsmasq-logrotate)
- [Desktop entries - ArchWiki](https://wiki.archlinux.org/title/Desktop_entries)
- [Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry/latest-single/)
- [Setting up logrotate in Linux](https://www.redhat.com/en/blog/setting-logrotate)
- [A Complete Guide to Managing Log Files with Logrotate](https://betterstack.com/community/guides/logging/how-to-manage-log-files-with-logrotate-on-ubuntu-20-04/)
- [nftables Guide: Configure Linux Firewall Rules](https://oneuptime.com/blog/post/2026-01-24-nftables-firewall-rules/view)
- [How to Save and Restore nftables Rules Across Reboots](https://oneuptime.com/blog/post/2026-03-20-save-restore-nftables-rules-reboots/view)

---

**End of Report**
