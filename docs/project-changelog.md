# Changelog

All notable changes to webwarden. Format loosely follows Keep a Changelog.

## [Unreleased]

### Added
- Project foundations: canonical `backend/` + `gui/` layout, shared domain
  validation/normalization module (byte-identical backend + GUI copies, sync-tested),
  `paths.py` constants, pytest tooling (`scripts/check.ps1` / `check.sh`), docs scaffold.
- Backend `webwarden` CLI (Python 3): argparse dispatch, `/etc/webwarden` state
  (locked users, per-user allowlists, stable port index), human-user enumeration +
  sudo detection, full JSON contract (`status`/`users`/`list`/`log`/`log --summary`).
- Per-user dnsmasq config generation (allowlist resolver + catch-all block + nftset +
  query logging) and the `inet kidfilter` nftables ruleset (per-UID DNS redirect,
  default-deny egress, 80/443 + QUIC to allow-sets).
- `apply` orchestration (fail-closed: validates dnsmasq configs and ruleset before
  loading; resilient instance reconcile), templated `webwarden-dns@.service` +
  `webwarden-nft.service`, blocked-log parsing, logrotate.
- GTK4 admin GUI: async pkexec client, Users / Allowlist / Blocked-Log (ColumnView) /
  Status views, toast + confirm helpers, graceful backend-missing degradation.
- Packaging: Polkit policy + group-gating rules, `.desktop` launcher,
  `install.sh` / `uninstall.sh`.
- Tests: 109 Windows-runnable unit tests; Linux acceptance runbook
  (`docs/acceptance-checklist.md`).

### Added
- Blocked-log retention: `/etc/webwarden/settings.json` (`log_retention_days`, default 30,
  `0` = keep forever), privileged `webwarden settings` and `webwarden log --prune` / `--clear`,
  a daily `webwarden-logprune.timer`, and a GUI **Settings** view + Log-view **Clear all logs**
  button. Retention is also enforced at the end of every `apply` (#5).

### Fixed
- Allowlist user dropdown rendered blank — gave the `Gtk.DropDown` a `PropertyExpression` so
  usernames display and a user can be selected (#2).
- Silenced the startup `PyGIWarning` by pinning `Gdk` to `4.0` before import (#3).
- Replaced the stock launcher icon with a branded `webwarden-admin` shield SVG installed into
  the hicolor theme (#4).
- Taskbar/window icon showed the Python logo: the launcher runs `python3 -m webwarden_admin`, so the
  X11 `WM_CLASS` defaulted to `python3`. Pin the program name to the app id (`GLib.set_prgname`),
  install the icon under the app-id name, and add `StartupWMClass` so the window-list maps to our
  launcher (#4).

### Security review
- Fail-closed DNS validation added to `apply` (configs validated before activation).
- Instance reconcile aggregates failures instead of aborting on the first.
- dnsmasq config tightened to mode `0640`.
- Log deletion (`prune`/`clear`) is root-only via the existing Polkit-gated binary; paths are
  restricted to `*.log` under the log dir (no traversal); retention is validated to `0..365`.
