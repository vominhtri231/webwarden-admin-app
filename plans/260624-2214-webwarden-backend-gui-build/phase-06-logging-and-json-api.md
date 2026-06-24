# Phase 06 — Logging & JSON API

**Context:** phases 02–05 · SPEC §4.2, §4.3, §4.4, §6 · backend-filtering + systemd reports.
**Priority:** Critical (completes the GUI's API) · **Status:** pending · **Linux-only:** parse logic = no; **exact log-format verification = YES**.

## Overview
Parse per-user dnsmasq logs into blocked-attempt records and finalize every `--json` accessor so
the GUI never touches raw files. Add logrotate. Parsing is pure logic (unit-test with captured log
samples on Windows); the **exact blocked-line format must be confirmed on real dnsmasq** before
trusting the parser.

## Key Insights (from research — IMPORTANT)
- Spec claims blocked line = `config <domain> is 0.0.0.0`. Research found real dnsmasq more likely logs `<domain> is 0.0.0.0` / `<domain> is [::]` for an `address=`-configured answer; "config" keyword is uncertain. **Parser must match a verified-on-Linux regex, not the spec's guess.**
- A **block** = answer is the configured null address (`0.0.0.0` or `::`/`[::]`). Allowed visits = `forwarded …` + `reply … is <real-ip>` → NOT blocks.
- Log line carries dnsmasq's timestamp (syslog-style, no year by default) → need to reconstruct ISO8601 with current year/tz; consider `log-facility` + parsing the leading timestamp. Per-user file means `user` is known from filename.
- Dedup/count for `--summary`: group by (user, domain), keep max time as `last_seen`.

## Requirements
- Functional (exact outputs per §4.4):
  - `log --json [--user U] [--since ISO] [--limit N]` → `[{time, user, domain}]` newest-first.
  - `log --summary --json` → `[{user, domain, count, last_seen}]`.
  - `status --json` → `{users:[{username,uid,locked,has_sudo,allow_count,dns_service_active}], firewall_loaded}`.
  - `list <u> --json` → `{username, domains:[...]}`. `users --json` → all uid≥1000 with locked flag.
- Non-functional: tolerant parser (skip malformed lines); bounded memory (stream large logs, honor `--limit`).

## Architecture
```
/var/log/webwarden/<u>.log ──logparse.parse_blocked(file,user,since)──▶ [BlockedRow]
jsonapi.py: log_json / log_summary_json / status_json / list_json / users_json
  status_json.firewall_loaded = `nft list table inet kidfilter` succeeds
  dns_service_active = services.is_instance_active(u)
```

## Related Code Files
- Implement `logparse.py`, `jsonapi.py`; wire `--json` flags in `cli.py` (stubbed in Phase 02).
- Create `logrotate/webwarden`.

## Implementation Steps
1. `logparse.py`: regex(es) for blocked lines (parameterized so the verified pattern can be swapped); timestamp→ISO8601; `--since`/`--limit` filtering; read newest-first.
2. `jsonapi.py`: build all five structures; print compact JSON to stdout; stable key order.
3. logrotate config: weekly, rotate 4, compress, missingok, notifempty; `postrotate` sends **SIGUSR2** to each dnsmasq instance to reopen logs (per research; verify vs copytruncate). Dir 750 root:adm.
4. **Linux verification step (Phase 10):** capture real blocked + allowed log lines, save as test fixtures, finalize regex, assert parser matches.

## Todo
- [ ] `logparse.py` (regex param, ts→ISO, since/limit, newest-first)
- [ ] `jsonapi.py` all 5 builders matching §4.4 schemas exactly
- [ ] logrotate config + SIGUSR2 postrotate
- [ ] unit tests on captured sample logs (blocked vs allowed vs malformed)
- [ ] [Linux] capture real dnsmasq lines → finalize & re-test regex

## Success Criteria
JSON outputs validate against §4.4 schemas; parser unit tests pass on sample fixtures; on Linux, parser correctly classifies real blocked vs allowed lines from a live instance.

## Risk Assessment
- **Wrong log regex = silent empty/incorrect blocked table** (#1 project risk). Mitigate: parameterized regex + mandatory Linux capture-and-verify before sign-off; log a warning if a logfile exists but zero lines parse.
- Timestamp year/tz ambiguity across year boundary → use file mtime/current year heuristic; document.

## Security Considerations
- Log content is untrusted text (contains user-visited domains) → never `eval`/format into shell; treat as data. `/var/log/webwarden` 750 root:adm so only admin/adm-group read (spec §6). GUI reads via CLI (pkexec) or adm-group membership.

## Next Steps
CLI contract complete → GUI phases 07–08 can build against real JSON.
