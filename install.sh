#!/usr/bin/env bash
# webwarden installer: backend CLI + per-user systemd units + GTK4 admin GUI +
# Polkit policy + logrotate. Idempotent; validates the nftables ruleset before
# activating it. Run as root from the repo root: sudo ./install.sh
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "install.sh must run as root (use sudo)." >&2
    exit 1
fi

# --- dependency check -------------------------------------------------------
missing=""
for cmd in python3 nft dnsmasq pkexec systemctl; do
    command -v "$cmd" >/dev/null 2>&1 || missing="$missing $cmd"
done
if [ -n "$missing" ]; then
    echo "Missing required commands:$missing" >&2
    echo "Install them, e.g.: apt install python3 nftables dnsmasq policykit-1" >&2
    exit 1
fi
if ! python3 -c 'import gi; gi.require_version("Gtk","4.0")' >/dev/null 2>&1; then
    echo "WARNING: GTK4 Python bindings not found. The GUI needs:" >&2
    echo "  apt install python3-gi gir1.2-gtk-4.0" >&2
fi

echo "Installing webwarden backend..."
install -d /usr/share/webwarden
cp -rT "$SRC/backend/webwarden_cli" /usr/share/webwarden/webwarden_cli
install -m 0755 "$SRC/backend/webwarden" /usr/local/sbin/webwarden

echo "Installing admin GUI..."
install -d /usr/share/webwarden-admin
cp -rT "$SRC/gui/webwarden_admin" /usr/share/webwarden-admin/webwarden_admin
install -m 0644 "$SRC/gui/data/webwarden-admin.css" /usr/share/webwarden-admin/webwarden-admin.css
install -m 0755 "$SRC/gui/webwarden-admin" /usr/local/bin/webwarden-admin
install -d /usr/share/applications
install -m 0644 "$SRC/gui/data/webwarden-admin.desktop" /usr/share/applications/webwarden-admin.desktop

echo "Installing systemd units..."
install -m 0644 "$SRC/backend/systemd/webwarden-dns@.service" /etc/systemd/system/webwarden-dns@.service
install -m 0644 "$SRC/backend/systemd/webwarden-nft.service" /etc/systemd/system/webwarden-nft.service
systemctl daemon-reload

echo "Installing Polkit policy + rules..."
install -d /usr/share/polkit-1/actions
install -m 0644 "$SRC/backend/polkit/org.webwarden.admin.policy" /usr/share/polkit-1/actions/org.webwarden.admin.policy
install -d /etc/polkit-1/rules.d
install -m 0644 "$SRC/backend/polkit/50-webwarden.rules" /etc/polkit-1/rules.d/50-webwarden.rules

echo "Installing logrotate config..."
install -m 0644 "$SRC/backend/logrotate/webwarden" /etc/logrotate.d/webwarden

echo "Creating state + log directories..."
install -d -m 0750 /etc/webwarden
log_group=root
getent group adm >/dev/null 2>&1 && log_group=adm
install -d -m 0750 -o root -g "$log_group" /var/log/webwarden

echo "Generating + loading initial ruleset..."
/usr/local/sbin/webwarden apply
systemctl enable webwarden-nft.service

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database /usr/share/applications || true

echo "webwarden installed. Launch 'webwarden Admin' from the menu, or run: webwarden-admin"
