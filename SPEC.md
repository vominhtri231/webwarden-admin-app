# Build Spec — webwarden Admin App (per-user website allowlist + blocked-site log)

> Hand this file to Claude Code. It describes an admin application to be built **on top of the existing `webwarden` backend** (a validated nftables + dnsmasq per-user website allowlist for Linux Mint / Ubuntu). The backend tarball already exists; this spec extends it and adds a GUI.

---

## 1. Goal

A simple admin tool, run by the administrator on a single Linux Mint machine, that lets the admin:

1. Choose which **user accounts** are restricted.
2. Manage **per-user website allowlists** — which sites each restricted user may visit (everything else blocked).
3. View a **log of blocked attempts** — which site was blocked, for which user, when, and how often.

Constraints (inherited from the project):
- **Offline / standalone.** No central server, no cloud, no dependence on other machines being reachable. Each computer runs its own copy.
- **Linux Mint** (Ubuntu base): systemd, apt, nftables, dnsmasq.
- **Bypass-resistant.** Filtering is enforced in the kernel (per-UID), not in the browser. Restricted users must be non-admin.

---

## 2. Why build vs. adopt (context for the implementer)

No existing app fits all three constraints (per-user + offline/standalone + strict admin allowlist + blocked-site log). OpenSnitch is the closest but uses an interactive per-app firewall model, not an admin-managed per-user website allowlist; Pi-hole is network-wide, not per-user; CTParental is heavier and out-of-repo. We therefore build a thin admin layer over the existing, validated `webwarden` CLI/services.

---

## 3. Starting point: the existing backend

The `webwarden` package already provides (validated on Ubuntu 24.04 / Mint base):

- `/usr/local/sbin/webwarden` — root CLI with subcommands: `lock`, `unlock`, `allow`, `disallow`, `list`, `status`, `apply`.
- A restrictive **dnsmasq** instance on `127.0.0.1:5354` that resolves **only** allowlisted domains (everything else answered `0.0.0.0`/`::`) and auto-populates nftables IP sets.
- An **nftables** table `inet kidfilter` with per-UID default-deny egress; locked users' DNS (ports 53/853) is redirected to the local resolver; only ports 80/443 to allowlisted IPs are permitted.
- systemd units `webwarden-nft.service` and `webwarden-dns.service` that restore state at boot.

The current limitation to fix: a **single shared allowlist** for all locked users, and **no logging**. This spec upgrades both.

---

## 4. Required backend changes

### 4.1 Per-user allowlists
Replace the single allowlist with one allowlist per locked user.

- Policy storage: `/etc/webwarden/users/<username>/allowlist.txt` (one domain per line), plus `/etc/webwarden/locked-users.txt` for the set of locked accounts.
- Run **one dnsmasq instance per locked user**, each on its own loopback port `5354 + N` (N = stable index per user), generated config at `/etc/webwarden/users/<username>/dnsmasq.conf`.
- Per-user nftables IP sets: `allow_v4_<username>` / `allow_v6_<username>`; the user's dnsmasq populates only its own sets via `nftset=`.
- Per-user nftables rules keyed on `meta skuid <uid>`:
  - redirect that UID's DNS (udp/tcp 53 and 853) to that user's dnsmasq port;
  - accept that UID's tcp 80/443 only to that user's `allow_*` sets;
  - default reject for that UID.
- A per-user systemd instance unit, e.g. `webwarden-dns@<username>.service` (templated), is preferred over N hand-written units.

Keep the CLI commands but make them user-scoped:
- `webwarden allow <username> <domain>...`
- `webwarden disallow <username> <domain>...`
- `webwarden lock <username>` / `unlock <username>`
- `webwarden list [username]`

### 4.2 Blocked-site logging
- Enable query logging on each per-user dnsmasq instance:
  - `log-queries`
  - `log-facility=/var/log/webwarden/<username>.log`
- A **blocked attempt** is any log line of the form `config <domain> is 0.0.0.0` (and the `::` variant) — these are the domains the allowlist refused. Allowed visits appear as `forwarded …` / `reply …` lines and are NOT blocks.
- Add a machine-readable accessor so the GUI never has to parse raw logs itself:
  - `webwarden log --json [--user <username>] [--since <ISO8601>] [--limit N]`
  - Output: JSON array of objects `{ "time": ISO8601, "user": str, "domain": str }`, newest first. Deduplicate-and-count variant: `webwarden log --summary --json` → `[{ "user", "domain", "count", "last_seen" }]`.
- Logs must rotate (logrotate config under `/etc/logrotate.d/webwarden`, e.g. weekly, keep 4, compress) so they don't grow unbounded.

### 4.3 Status as JSON (for the GUI)
- `webwarden status --json` → `{ "users": [ { "username", "uid", "locked": bool, "has_sudo": bool, "allow_count", "dns_service_active": bool } ], "firewall_loaded": bool }`.
- This lets the GUI render state without scraping human-readable text.

### 4.4 Stable CLI contract
The GUI depends ONLY on these commands and their JSON outputs (treat as the API):
```
webwarden status --json
webwarden list <username> --json          # -> { "username", "domains": [..] }
webwarden allow <username> <domain>...
webwarden disallow <username> <domain>...
webwarden lock <username>
webwarden unlock <username>
webwarden log --json [--user U] [--since T] [--limit N]
webwarden log --summary --json
webwarden users --json                     # all human users uid>=1000, with locked flag
```
All mutating commands must be idempotent and exit non-zero with a clear stderr message on error.

---

## 5. The admin app (GUI)

### 5.1 Recommended technology
A **local desktop GUI** is preferred over a web server (no open port, simpler privilege story). Recommended: **Python 3 + GTK 4 (PyGObject)** to match the Mint/Cinnamon environment; PyQt is an acceptable alternative. Avoid bundling a browser/Electron — keep it lightweight.

If a web UI is chosen instead, it MUST bind to `127.0.0.1` only, require local admin, and never be exposed on the network.

### 5.2 Privilege model (important)
- The GUI itself runs as the normal admin desktop user (unprivileged).
- All **mutating** actions are performed by invoking the `webwarden` CLI through **`pkexec`** (Polkit), so the user authenticates once via the standard system password dialog. Ship a Polkit policy file (`org.webwarden.admin.policy`) that authorizes running `webwarden` as root for users in the `sudo`/`adm` group.
- **Reading** logs/status should also go through the CLI (via pkexec, or by making `/var/log/webwarden` readable by the `adm` group) so the GUI never needs root itself.
- The GUI must never write to `/etc/webwarden` directly.

### 5.3 Screens / features
1. **Users panel**
   - List all human accounts (uid ≥ 1000) with a Locked on/off toggle each.
   - Visual warning badge if a locked (or to-be-locked) user still has sudo/admin rights, with a one-line explanation that this defeats the lock and how to fix it (`deluser <user> sudo`). Do not auto-remove sudo; just warn.
2. **Allowlist editor** (per selected user)
   - Show the user's approved domains; add (text box, accepts `example.com` or a pasted URL — strip scheme/path, lowercase, validate) and remove.
   - Note shown to admin: "approving a domain also covers its subdomains."
   - Changes call `webwarden allow/disallow` and refresh.
3. **Blocked attempts log**
   - Table: time, user, domain, (count in summary mode). Sortable; filter by user and by text; date range / "last 24h / 7d" quick filters.
   - A one-click **"Allow this domain for this user"** action on a blocked row (calls `webwarden allow`).
   - Auto-refresh (poll `webwarden log --json` every few seconds) or a manual Refresh button.
4. **Status bar / health**
   - Indicators that the firewall is loaded and each locked user's resolver service is active (from `status --json`). Surface a clear error if a service is down.

### 5.4 UX requirements
- Every destructive/standing change shows a brief confirmation and a success/failure toast.
- The app must degrade gracefully if `webwarden` is not installed (show a clear "backend not installed — run install.sh" message).
- Keep it genuinely simple: a household admin should understand every screen without docs.

---

## 6. Security & correctness requirements

- Treat all log content and domain inputs as untrusted text; validate domains against `^[a-z0-9]([a-z0-9-]*\.)+[a-z]{2,}$` before passing to the CLI; never shell-interpolate user input (use argv arrays, not string concatenation).
- The GUI must not weaken the backend's default-deny posture or expose any way to disable filtering without admin authentication.
- No telemetry, no network calls from the app itself.
- Logs may contain sensitive browsing data → directory mode `750`, owned `root:adm`; rotate and cap retention.
- Document (in the app's README) the inherited limits the backend already carries: a locked user must be non-admin; physical/BIOS/live-USB bypass needs a BIOS password + disk encryption; rare ECH sites may need explicit allowlisting.

---

## 7. Deliverables

1. Patched `webwarden` backend implementing §4 (per-user allowlists, per-user dnsmasq instances, logging, JSON outputs, templated systemd unit, logrotate).
2. The GUI app (§5) with its Polkit policy file and a `.desktop` launcher entry.
3. An updated `install.sh` that installs backend + GUI + Polkit policy + logrotate, and creates `/var/log/webwarden` with correct ownership.
4. Updated `README.md` covering install, daily use, the privilege model, and the security limits.
5. A short `UNINSTALL` section/script.

---

## 8. Acceptance criteria (test checklist)

- [ ] Locking user A and allowing only `wikipedia.org` for A: from A's session, `wikipedia.org` loads; `example.com` and a raw-IP fetch both fail; the admin account is unaffected.
- [ ] Two locked users can have **different** allowlists, enforced independently (A's allowed site is blocked for B unless also allowed for B).
- [ ] Visiting a blocked site as user A produces a row in the GUI's blocked-attempts table attributed to A, with correct domain and timestamp.
- [ ] "Allow this domain for this user" on a blocked row makes the site work for that user within seconds, and stops new block entries for it.
- [ ] `disallow` makes a previously allowed site stop working promptly (IP sets flushed).
- [ ] All policy survives a reboot (services re-enabled; rules reloaded).
- [ ] DoH/DoT and pointing the browser at `8.8.8.8` do not bypass the per-user allowlist.
- [ ] GUI never prompts for a password except via the standard Polkit dialog on mutating actions; runs unprivileged otherwise.
- [ ] Validated with `nft -c -f` and `dnsmasq --test` in the install/apply path.

---

## 9. Out of scope (note for future, do not build now)

- Time-of-day scheduling / screen-time limits.
- Content-category filtering (adult/ads blocklists).
- Central multi-machine management (each machine stays standalone by design).
- SNI-level interception proxy (Squid peek-and-splice) for the rare shared-CDN edge case — possible later second layer; the current address-set model is sufficient for a household allowlist.
