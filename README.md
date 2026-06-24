# webwarden Admin App

A simple, offline, single-machine admin tool for managing **per-user website allowlists** and viewing a **log of blocked attempts** on Linux Mint / Ubuntu. It is a thin GUI layer over the existing, validated `webwarden` backend (per-UID nftables + dnsmasq filtering).

The full build specification lives in [`SPEC.md`](./SPEC.md).

---

## What it does

For an administrator on a single Linux Mint machine, this app lets you:

1. **Choose which user accounts are restricted** (locked).
2. **Manage per-user website allowlists** — exactly which sites each restricted user may visit; everything else is blocked.
3. **View a log of blocked attempts** — which site was blocked, for which user, when, and how often — and allow a domain in one click straight from a blocked row.

## Design constraints

- **Offline / standalone.** No central server, no cloud, no dependence on other machines. Each computer runs its own copy.
- **Linux Mint (Ubuntu base):** systemd, apt, nftables, dnsmasq.
- **Bypass-resistant.** Filtering is enforced in the kernel per-UID, not in the browser. Restricted users must be non-admin.

## Architecture at a glance

- **Backend (`webwarden` CLI + systemd units):** per-user allowlists, one dnsmasq instance per locked user, per-user nftables IP sets and rules keyed on `meta skuid <uid>`, query logging, and JSON accessors. The GUI depends only on the stable CLI JSON contract (see §4.4 of the spec).
- **GUI (recommended Python 3 + GTK 4 / PyGObject):** runs unprivileged as the admin desktop user. All mutating actions go through the `webwarden` CLI via **`pkexec`** (Polkit), so the admin authenticates once via the standard system password dialog. The GUI never writes to `/etc/webwarden` directly.

## Privilege & security model

- GUI runs unprivileged; mutations are authorized by a shipped Polkit policy (`org.webwarden.admin.policy`).
- Domain inputs are validated (`^[a-z0-9]([a-z0-9-]*\.)+[a-z]{2,}$`) and passed as argv arrays — never shell-interpolated.
- No telemetry, no network calls from the app itself.
- Logs may contain sensitive browsing data → `/var/log/webwarden` is `750`, owned `root:adm`, rotated weekly with capped retention.

## Inherited limits (from the backend)

- A locked user **must be non-admin** — sudo/admin rights defeat the lock. The app warns but does not auto-remove sudo.
- Physical / BIOS / live-USB bypass needs a BIOS password + disk encryption.
- Rare ECH sites may need explicit allowlisting.

## Install

Run on the target Linux Mint / Ubuntu machine as an admin:

```bash
# 1. Dependencies
sudo apt install python3 python3-gi gir1.2-gtk-4.0 dnsmasq nftables policykit-1

# 2. Install webwarden (from the repo root)
sudo ./install.sh
```

`install.sh` installs the `webwarden` CLI (`/usr/local/sbin`), the GTK4 GUI, the
templated systemd units, the Polkit policy, logrotate, and creates
`/var/log/webwarden` (`750 root:adm`). It validates the nftables ruleset
(`nft -c -f`) and generates an initial ruleset before enabling anything.

## Daily use

Launch **webwarden Admin** from the system menu (or run `webwarden-admin`). The
GUI runs unprivileged; the first mutating action shows one standard Polkit
password dialog, then caches the authorization for the session.

- **Users** — toggle a user **Locked**. A locked user may only visit their
  allowlist. A warning badge flags any locked user who still has admin rights
  (run `deluser <user> sudo` to fix; the app never removes sudo for you).
- **Allowlist** — pick a user, add domains (`example.com` or a pasted URL — the
  app strips the scheme/path and validates it). Approving a domain also covers
  its subdomains. Remove with one click.
- **Blocked Log** — every refused request, attributed to a user with a timestamp.
  Search, filter by last 24h / 7d, switch to a deduped **Summary**, and
  **Allow selected** to approve a blocked domain in one click. Auto-refreshes.
- **Status** — firewall-loaded indicator and each locked user's resolver health.

CLI equivalents (used by the GUI, usable directly as root):
`webwarden lock <user>`, `webwarden allow <user> <domain>…`, `webwarden log --json`,
`webwarden status --json`. See `SPEC.md` §4.4 for the full contract.

## Uninstall

```bash
sudo ./uninstall.sh            # removes the program, keeps policy + logs
sudo ./uninstall.sh --purge    # also removes /etc/webwarden and /var/log/webwarden
```

## Status

Implementation complete (backend CLI, GTK4 GUI, packaging) with a full
Windows-runnable unit-test suite. Kernel/service/GTK behavior is validated on a
Linux Mint machine via the acceptance runbook in
[`docs/acceptance-checklist.md`](./docs/acceptance-checklist.md). Tracked against
[`SPEC.md`](./SPEC.md).

## Development tooling

This repo carries a local `.claude/` toolkit (Claude Code agents, hooks, skills). It is intentionally **gitignored** — it is development tooling, not part of the shipped deliverable.
