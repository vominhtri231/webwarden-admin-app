# Phase 09 — Packaging: Polkit, .desktop, install / uninstall

**Context:** phases 05–08 · SPEC §5.2, §6, §7 · systemd-polkit report.
**Priority:** Critical (deliverables §7.2/§7.3/§7.5) · **Status:** pending · **Linux-only:** YES.

## Overview
Make it installable: Polkit policy authorizing `pkexec webwarden`, a `.desktop` launcher, and an
idempotent `install.sh` that validates before activating + an `uninstall.sh`. This is what turns
the code into the shipped product.

## Key Insights (from research — IMPORTANT)
- **Only `argv1` is matched** by `org.freedesktop.policykit.exec.argv1`. A single action can't whitelist each subcommand via argv. Pattern: one action for `/usr/local/sbin/webwarden` with `auth_admin_keep` (admin authenticates once, cached ~5 min). Subcommand safety comes from the CLI itself (validates args, idempotent).
- **Group-gating** (sudo/adm only) goes in a polkit **`.rules`** JS file (`/etc/polkit-1/rules.d/50-webwarden.rules`: `subject.isInGroup("sudo")` → `polkit.Result.YES`/`AUTH_ADMIN_KEEP`), not the `.policy`. polkit ≥0.106 (Ubuntu 24.04 = 124) supports rules.
- pkexec scrubs env + uses no shell → CLI must hardcode tool paths (`/usr/sbin/nft`, `/usr/sbin/dnsmasq`, `/usr/bin/systemctl`).
- install order: prereqs → copy CLI+GUI → **validate (`nft -c -f`, `dnsmasq --test`)** → install units + `daemon-reload` → polkit → logrotate → create `/var/log/webwarden` 750 root:adm → `.desktop`. Fail early, no partial state.

## Requirements
- Functional: `install.sh` installs backend (`/usr/local/sbin/webwarden` + package to e.g. `/usr/share/webwarden`), GUI (`/opt/webwarden-admin` + wrapper `/usr/local/bin/webwarden-admin`), units, polkit policy+rules, logrotate, `.desktop`, log dir. `uninstall.sh` reverses (optionally keep `/etc/webwarden` + logs, prompt).
- Non-functional: idempotent (`install -D`, re-runnable); abort on any validation failure; clear progress output.

## Related Code Files
- Create `install.sh`, `uninstall.sh`, `backend/polkit/org.webwarden.admin.policy`, `backend/polkit/50-webwarden.rules`, `gui/data/webwarden-admin.desktop`, wrapper scripts `backend/webwarden`, `gui/webwarden-admin`.

## Implementation Steps
1. Polkit `.policy`: one action `org.webwarden.admin.run`, `exec.path=/usr/local/sbin/webwarden`, `<defaults>` `allow_active=auth_admin_keep`, `exec.allow_gui` annotation.
2. Polkit `.rules`: gate to `sudo`/`adm` group members (deny others even with password) — confirm desired strictness with spec §5.2 ("authorizes ... for users in the sudo/adm group").
3. `.desktop`: `Type=Application`, Name, Comment, `Exec=webwarden-admin`, Icon, `Categories=System;Settings;Security;`, `Terminal=false`.
4. `install.sh`: dependency check (python3-gi, gir1.2-gtk-4.0, dnsmasq, nftables, policykit), copy, **validate**, install units+reload, polkit, logrotate, `install -d -m750 -o root -g adm /var/log/webwarden`, desktop, `update-desktop-database`.
5. `uninstall.sh`: disable+remove units, remove files, optional purge of `/etc/webwarden` + logs (prompt), `daemon-reload`.
6. Dry-run/validate mode for install if feasible.

## Todo
- [ ] `org.webwarden.admin.policy` (single action, auth_admin_keep)
- [ ] `50-webwarden.rules` (group gating)
- [ ] `webwarden-admin.desktop` + icon
- [ ] wrapper scripts (backend + GUI entry points)
- [ ] `install.sh` (validate-before-activate, idempotent)
- [ ] `uninstall.sh` (reverse, prompt to keep data)

## Success Criteria (Linux)
Fresh install on Mint VM: GUI launches from menu, mutations trigger exactly one Polkit dialog (then cached), reads need no extra prompt; non-admin user denied; `nft -c -f`/`dnsmasq --test` run in install path (§8); uninstall leaves no dangling units/policy.

## Risk Assessment
- Polkit rules syntax/cache → `systemctl restart polkit` after install; test deny path for non-sudo user.
- `auth_admin_keep` UX vs security: cached auth ~5 min — acceptable per spec (authenticate once); document.
- Wrong tool paths after env scrub → grep CLI for any bare command names; hardcode absolute paths.

## Security Considerations
- The Polkit action is the entire trust gate. Restrict to the single binary path; rely on CLI validation for args (argv1-only matching limitation). No way to disable filtering without admin auth (§6). Log dir 750 root:adm.

## Next Steps
Phase 10 runs the full §8 acceptance suite on a Mint VM.
