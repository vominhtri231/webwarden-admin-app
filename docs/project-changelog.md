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

### Security review
- Fail-closed DNS validation added to `apply` (configs validated before activation).
- Instance reconcile aggregates failures instead of aborting on the first.
- dnsmasq config tightened to mode `0640`.
