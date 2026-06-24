# Acceptance Checklist (Linux Mint)

Tier A (pure-logic unit tests) runs on any host: `python -m pytest` (or
`scripts/check.sh`). Tier B below is the **on-target** acceptance suite — run it
on a Linux Mint / Ubuntu 24.04 machine (or VM) after `sudo ./install.sh`. It maps
1:1 to SPEC §8. Check each box only after observing the stated result.

## Pre-flight: early-verify the two flagged risks FIRST
Both could not be validated on the Windows dev host; confirm before trusting the rest.

1. **dnsmasq blocked-log format** (drives the whole blocked-attempts feature)
   - Lock a test user, allow nothing, browse to `example.com` from their session.
   - `sudo tail /var/log/webwarden/<user>.log` — confirm blocked lines read
     `config example.com is 0.0.0.0` (and `... is ::`). If the wording differs,
     update `_BLOCK_RE` in `backend/webwarden_cli/logparse.py` and re-run
     `pytest backend/tests/test_logparse.py` against a captured sample.
   - `webwarden log --json` should then list the attempt.

2. **`meta skuid` redirect + IPv6 in the `inet` table**
   - After locking a user: `sudo nft list table inet kidfilter` shows the
     `dnsredirect` + `egress` chains and the user's sets.
   - From the locked session, `dig @8.8.8.8 example.com` must be answered by the
     local resolver (redirected), not 8.8.8.8. If redirect-in-output misbehaves,
     see the LINUX-VERIFY note in `nftables_ruleset.py` (fallback: split ip/ip6 tables).

## Tier B — SPEC §8 acceptance
- [ ] **Allowlist enforced.** Lock user A, `webwarden allow A wikipedia.org`. From A's
      session: `wikipedia.org` loads; `example.com` fails; `curl http://<raw-ip>` fails.
      The admin account is unaffected.
- [ ] **Per-user isolation.** Lock A and B with different allowlists. A's allowed site
      is blocked for B (and vice-versa) unless also allowed for B.
- [ ] **Blocked attempt logged + attributed.** Visiting a blocked site as A produces a
      row in the GUI Blocked-Log table attributed to A, correct domain + timestamp.
- [ ] **One-click allow.** "Allow selected" on a blocked row makes the site work for that
      user within seconds and stops new block entries for it.
- [ ] **Disallow takes effect.** `webwarden disallow A <domain>` (or GUI Remove) makes a
      previously allowed site stop working promptly (sets rebuilt on apply).
- [ ] **Reboot persistence.** After reboot: `webwarden-nft.service` active, rules reloaded,
      each locked user's `webwarden-dns@<user>` active; policy unchanged.
- [ ] **No DNS bypass.** From a locked session, DoT (`:853`), DoH, and pointing the browser
      at `8.8.8.8` do NOT bypass the allowlist.
- [ ] **Polkit-only escalation.** The GUI runs unprivileged; the only password prompt is the
      standard Polkit dialog on a mutating action. A non-sudo/adm user is denied.
- [ ] **Validation in apply/install path.** `nft -c -f` and `dnsmasq --test` are exercised
      (install runs `webwarden apply`, which validates before loading; instances run with
      configs that pass `dnsmasq --test`).
- [ ] **Graceful degradation.** Launch the GUI with the backend absent → "backend not
      installed" screen, no crash.

## Notes
- Tier A current status: `python -m pytest` → all green (validation, state, users, cli,
  dnsmasq_config, nftables_ruleset, apply, services, logparse, jsonapi, GUI cli_args/log_filter).
- No failing test may be ignored to make a build pass (project rule).
