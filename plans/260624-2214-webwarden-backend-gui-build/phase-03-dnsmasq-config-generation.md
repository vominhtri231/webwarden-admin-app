# Phase 03 — dnsmasq Per-User Config Generation

**Context:** `phase-02-backend-cli-core-and-state.md` · SPEC §4.1, §4.2 · backend-filtering report.
**Priority:** Critical · **Status:** pending · **Linux-only:** generation = no; `dnsmasq --test` validation + running = yes.

## Overview
Generate one self-contained dnsmasq config per locked user that (a) listens only on
`127.0.0.1:PORT_BASE+N`, (b) resolves **only** allowlisted domains via upstream and answers
everything else `0.0.0.0`/`::`, (c) auto-populates that user's nftables IP sets, (d) logs queries
to that user's logfile. Pure string generation — unit-test the rendered file on Windows.

## Key Insights (from research)
- Catch-all deny: `address=/#/0.0.0.0` + `address=/#/::` ; allowed domains get `server=/<d>/<upstream>` so they forward instead of being caught. (Verify precedence: explicit `server=` beats `#` catch-all — confirm on Linux.)
- nftables population: `nftset=/<domain>/4#inet#kidfilter#allow_v4_<u>` and `.../6#inet#kidfilter#allow_v6_<u>` (requires dnsmasq ≥ 2.87; Ubuntu 24.04 ok). Sets must pre-exist (Phase 04).
- Instance isolation: `port=`, `listen-address=127.0.0.1`, `bind-interfaces`, `no-resolv` + explicit upstream `server=8.8.8.8`? No — keep system resolver: use `resolv-file` or fixed upstreams. KISS: configurable upstream list (default `1.1.1.1`,`8.8.8.8`), `no-resolv`.
- Logging: `log-queries`, `log-facility=/var/log/webwarden/<u>.log`. `min-cache-ttl=60` to bound stale-allow after disallow.
- Each instance: own `pid-file`, `conf-file` (no global `/etc/dnsmasq.d` include), `user=`/`group=` to drop privs (e.g. run as `dnsmasq` or `nobody`).

## Requirements
- Functional: `render_dnsmasq_conf(username, port, allowlist, upstreams)` → full conf text; write to `users/<u>/dnsmasq.conf` atomically.
- Non-functional: deterministic output (sorted domains) for stable diffs/tests; never emit a domain that failed validation.

## Architecture
```
allowlist.txt + port + upstreams ──render──▶ users/<u>/dnsmasq.conf
   per allowed domain d:  server=/d/<upstream>   nftset=/d/4#inet#kidfilter#allow_v4_<u>
                                                 nftset=/d/6#inet#kidfilter#allow_v6_<u>
   global:  port=N  listen-address=127.0.0.1  bind-interfaces  no-resolv
            address=/#/0.0.0.0  address=/#/::  log-queries  log-facility=...  min-cache-ttl=60
```

## Related Code Files
- Implement `dnsmasq_config.py`. Called by `apply.py` (Phase 05).

## Implementation Steps
1. `render_dnsmasq_conf(...)` building the global block then per-domain `server=` + `nftset=` lines (v4 + v6), domains sorted.
2. `write_user_dnsmasq(username)` → read state, compute port, render, atomic write `0644` (config is non-secret).
3. Empty allowlist case: still valid — only catch-all `0.0.0.0`/`::` (everything blocked), instance still runs so logging captures attempts.
4. Validation hook `validate_dnsmasq_conf(path)` → run `dnsmasq --test -C <path>` (Linux only; gate behind platform check, surface stderr).
5. Subdomain coverage note: `server=/example.com/...` already covers subdomains — document for admin (spec §5.2).

## Todo
- [ ] `render_dnsmasq_conf` (global + per-domain server/nftset)
- [ ] atomic writer + empty-allowlist case
- [ ] `dnsmasq --test` validation wrapper (Linux-gated)
- [ ] unit tests: golden-file render, sorted/deterministic, v4+v6 nftset lines, injection-safe domains only

## Success Criteria
Golden-file unit test matches expected conf for a sample allowlist (Windows). On Linux, `dnsmasq --test` passes for generated configs.

## Risk Assessment
- **`server=` vs `address=/#/` precedence** unverified → if catch-all wins, allowed domains break. VERIFY early on Linux; fallback is `--server` with `--local`/`--address` ordering or per-domain `address` removal. (Top risk for this phase.)
- Multi-A-record / CNAME chains may under-populate sets → confirm dnsmasq adds all answer IPs to nftset; document churn.

## Security Considerations
- Config is generated only from validated domains; no user free-text reaches the file unescaped. dnsmasq drops to unprivileged `user=`/`group=`.

## Next Steps
Pairs with Phase 04 (sets must exist before instance starts); both consumed by Phase 05 apply.
