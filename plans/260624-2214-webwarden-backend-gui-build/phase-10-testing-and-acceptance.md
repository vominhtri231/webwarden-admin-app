# Phase 10 — Testing & Acceptance

**Context:** all prior phases · SPEC §8 (acceptance), §6 (security) · all reports.
**Priority:** Critical (gate to "done") · **Status:** pending · **Linux-only:** unit tests = no; **§8 integration/acceptance = YES (Mint VM)**.

## Overview
Two tiers. **Tier A (Windows, now):** pure-logic unit tests for everything not needing the kernel.
**Tier B (Linux Mint, later):** live integration + the §8 acceptance checklist. The plan ships
Tier A green and a documented, runnable Tier B the user executes on real Mint.

## Tier A — Windows-runnable unit tests (pytest)
- `validation` — valid/invalid/injection domains (backend + GUI copies identical).
- `state` — port-index stability across unlock/relock; idempotent allow/lock; allowlist round-trip.
- `dnsmasq_config` — golden render; v4+v6 nftset lines; empty allowlist; only-validated domains.
- `nftables_ruleset` — golden render N users; set-name derivation; rule ordering (accepts before reject); no admin UID matched.
- `apply` — reconcile logic with a **faked services layer** (start/stop/enable/disable/free-port ordering).
- `logparse` — blocked vs allowed vs malformed on **captured sample log fixtures**; since/limit; ts→ISO.
- `jsonapi` — outputs validate against §4.4 schemas (jsonschema asserts).
- GUI `cli_args` — argv builders per command; URL-paste normalization; "last 24h/7d"→ISO; filter predicate; summary grouping.
- Lint/compile: `py_compile` all `.py`; `pyflakes`; GTK never imported in tested modules.

## Tier B — Linux Mint acceptance (the §8 checklist)
Run on a Mint VM after `install.sh`. Each maps to a SPEC §8 item:
- [ ] Lock A, allow only `wikipedia.org`: from A, wikipedia loads; `example.com` + raw-IP fetch fail; admin unaffected.
- [ ] Two locked users, different allowlists, independently enforced.
- [ ] Blocked visit by A → row in GUI attributed to A, correct domain + timestamp. **(validates Phase 06 regex)**
- [ ] "Allow this domain for this user" makes site work within seconds; new blocks stop.
- [ ] `disallow` stops a site promptly (sets flushed).
- [ ] Policy survives reboot (units re-enabled, rules reloaded).
- [ ] DoH/DoT + pointing browser at `8.8.8.8` do NOT bypass.
- [ ] GUI prompts only via standard Polkit dialog on mutations; unprivileged otherwise.
- [ ] `nft -c -f` + `dnsmasq --test` exercised in install/apply path.
- **Early-verify (do first on Linux):** confirm `meta skuid` redirect works (Phase 04 risk) + capture real dnsmasq blocked-line format (Phase 06 risk) → feed back into code/fixtures before full run.

## Implementation Steps
1. Build Tier A suite incrementally per phase (each phase lists its tests); CI script runs all on Windows.
2. Author Tier B as a `docs/acceptance-checklist.md` runbook (commands + expected results) the user executes on Mint.
3. On Linux: run early-verify items first; fix code if format/skuid differ from assumptions; then full §8.
4. Record results; no failing test ignored (project rule).

## Todo
- [ ] Tier A suite green on Windows (all modules above)
- [ ] CI/check script (py_compile + pyflakes + pytest)
- [ ] `docs/acceptance-checklist.md` runbook
- [ ] [Linux] early-verify: skuid redirect + log-line format
- [ ] [Linux] full §8 acceptance pass

## Success Criteria
Tier A fully green on Windows. Tier B: every §8 box checked on a Mint VM. The two top risks (log format, skuid) resolved with evidence.

## Risk Assessment
- Can't run Tier B here → deliver it as a precise runbook; flag that sign-off requires the user's Mint run.
- Hidden coupling making logic untestable off-Linux → enforced module separation from Phase 01.

## Security Considerations
- Acceptance explicitly tests the security posture: admin-unaffected, raw-IP blocked, DoH/DoT/8.8.8.8 bypass-resistance, Polkit-only escalation. These are pass/fail gates, not nice-to-haves.

## Next Steps
Phase 11 documents install/use/limits and updates project docs.
