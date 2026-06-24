---
title: webwarden — backend (from scratch) + GTK4 admin GUI
slug: webwarden-backend-gui-build
date: 2026-06-24
status: in_progress
mode: hard (research done, 3 researcher reports)
blockedBy: []
blocks: []
owner: Tri Vo
---

# webwarden — Backend + GTK4 Admin App

Build the complete `webwarden` system **from scratch** per `SPEC.md`: a per-UID website
allowlist (dnsmasq + nftables, one dnsmasq instance per locked user) with blocked-attempt
logging, a stable JSON CLI contract, and an unprivileged **Python 3 + GTK 4** admin GUI that
drives the CLI through `pkexec` (Polkit).

## Key decisions (locked with user)
- **Backend: build from scratch** — full CLI + dnsmasq/nftables/systemd, not a patch.
- **Backend language: Python 3** (not bash) — shared validation with GUI, native JSON, argv-safe, unit-testable. Installed to `/usr/local/sbin/webwarden`.
- **GUI: Python 3 + GTK 4 (PyGObject)**, plain GTK4 (no libadwaita on Cinnamon).
- **Test strategy: code now on Windows, validate on Linux Mint later.** Phases flag which steps are Linux-only. Pure logic is unit-tested on Windows.

## The stable CLI contract (the GUI's API — §4.4)
```
webwarden status --json
webwarden users --json
webwarden list <username> --json
webwarden allow <username> <domain>...
webwarden disallow <username> <domain>...
webwarden lock <username> | unlock <username>
webwarden log --json [--user U] [--since T] [--limit N]
webwarden log --summary --json
webwarden apply
```

## Phases
| # | Phase | Status | Linux-only? |
|---|-------|--------|-------------|
| 01 | [Foundations & conventions](phase-01-foundations-and-conventions.md) | pending | no |
| 02 | [Backend CLI core & state model](phase-02-backend-cli-core-and-state.md) | pending | no (logic) |
| 03 | [dnsmasq per-user config generation](phase-03-dnsmasq-config-generation.md) | pending | test only |
| 04 | [nftables ruleset generation](phase-04-nftables-ruleset-generation.md) | pending | test only |
| 05 | [Apply orchestration & systemd units](phase-05-apply-orchestration-and-systemd.md) | pending | **yes (apply)** |
| 06 | [Logging & JSON API](phase-06-logging-and-json-api.md) | pending | parse logic no; format verify **yes** |
| 07 | [GUI shell & async CLI client](phase-07-gui-shell-and-cli-client.md) | pending | run **yes**; logic no |
| 08 | [GUI views (users/allowlist/log/status)](phase-08-gui-views.md) | pending | run **yes**; logic no |
| 09 | [Packaging: Polkit, .desktop, install/uninstall](phase-09-packaging-polkit-install.md) | pending | **yes** |
| 10 | [Testing & acceptance](phase-10-testing-and-acceptance.md) | pending | unit no; §8 **yes** |
| 11 | [Docs & handoff](phase-11-docs-and-handoff.md) | pending | no |

## Dependencies (build order)
01 → 02 → {03, 04} → 05 → 06 → 07 → 08 → 09 → 10 → 11.
GUI (07–08) depends only on the **CLI contract**, so it can start once 06 stabilizes the JSON.

## Research inputs
- `plans/reports/researcher-260624-2214-backend-filtering-stack.md` (dnsmasq + nftables)
- `plans/reports/researcher-260624-2214-systemd-polkit-packaging.md` (systemd/Polkit/install)
- `plans/reports/researcher-260624-2214-gtk4-pygobject-gui.md` (GTK4 GUI)

## Top risks (see phase files)
1. **dnsmasq blocked-log line format** unverified on real dnsmasq (logging crux). → Phase 06.
2. **`meta skuid` in nat/redirect output chain** + dual-stack `inet` IPv6 behavior. → Phase 04/05.
3. **Cannot integration-test on Windows** — all kernel/service behavior validated only on Mint. → Phase 10.
4. **IP-set staleness / shared-CDN over-allow** — inherent to address-set filtering. → Phase 03.
