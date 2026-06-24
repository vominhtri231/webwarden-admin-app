#!/usr/bin/env bash
# webwarden uninstaller. Removes the program and reverses install.sh. By default
# it KEEPS your policy (/etc/webwarden) and logs (/var/log/webwarden); pass
# --purge to remove those too. Run as root: sudo ./uninstall.sh [--purge]
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "uninstall.sh must run as root (use sudo)." >&2
    exit 1
fi

purge=0
[ "${1:-}" = "--purge" ] && purge=1

echo "Stopping services..."
# Stop every per-user resolver instance, then the ruleset loader.
for unit in $(systemctl list-units --type=service --all --no-legend --plain 'webwarden-dns@*.service' 2>/dev/null | awk '{print $1}'); do
    systemctl disable --now "$unit" 2>/dev/null || true
done
systemctl disable --now webwarden-nft.service 2>/dev/null || true
systemctl disable --now webwarden-logprune.timer 2>/dev/null || true
nft delete table inet kidfilter 2>/dev/null || true

echo "Removing files..."
rm -f /usr/local/sbin/webwarden
rm -f /usr/local/bin/webwarden-admin
rm -rf /usr/share/webwarden
rm -rf /usr/share/webwarden-admin
rm -f /usr/share/applications/webwarden-admin.desktop
rm -f /usr/share/icons/hicolor/scalable/apps/webwarden-admin.svg
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
rm -f /etc/systemd/system/webwarden-dns@.service
rm -f /etc/systemd/system/webwarden-nft.service
rm -f /etc/systemd/system/webwarden-logprune.service
rm -f /etc/systemd/system/webwarden-logprune.timer
rm -f /usr/share/polkit-1/actions/org.webwarden.admin.policy
rm -f /etc/polkit-1/rules.d/50-webwarden.rules
rm -f /etc/logrotate.d/webwarden
systemctl daemon-reload

if [ "$purge" -eq 1 ]; then
    echo "Purging policy + logs..."
    rm -rf /etc/webwarden /var/log/webwarden
else
    echo "Kept /etc/webwarden and /var/log/webwarden (use --purge to remove)."
fi

echo "webwarden uninstalled."
