# Phase 04 — nftables Ruleset Generation

**Context:** `phase-02-backend-cli-core-and-state.md`, `phase-03-dnsmasq-config-generation.md` · SPEC §4.1, §6 · backend-filtering report.
**Priority:** Critical (the enforcement boundary) · **Status:** pending · **Linux-only:** generation = no; `nft -c -f` + load = yes.

## Overview
Generate the single `inet kidfilter` ruleset: per-user IP sets, a NAT/redirect output chain that
forces each locked UID's DNS to its own dnsmasq port, and a filter output chain that permits each
locked UID only DNS + tcp 80/443 to its own allow sets, default-rejecting the rest. Non-locked
users (incl. admin) are untouched. Pure text generation — unit-test the rendered ruleset.

## Key Insights (from research)
- Table `inet kidfilter` holds both v4+v6; sets per user: `allow_v4_<u>` (`type ipv4_addr; flags interval`), `allow_v6_<u>` (`type ipv6_addr; flags interval`). Pre-created empty; dnsmasq fills via `nftset=`.
- **DNS redirect**: a `nat`/`output` chain, priority `dstnat`(-100), matching `meta skuid <uid>` + `udp/tcp dport {53,853}` → `redirect to :PORT` (loopback) OR `dnat ip to 127.0.0.1:PORT`. `redirect` keeps it on loopback. **VERIFY `meta skuid` works in nat output + redirect for both families** (flagged risk).
- **Filter**: `output` chain, priority `filter`(0), policy `accept` (so non-locked users pass), but per locked UID: accept loopback to its dnsmasq port; accept `tcp dport {80,443} ip daddr @allow_v4_<u>` / `ip6 daddr @allow_v6_<u>`; allow the redirected DNS; then `meta skuid <uid> reject with icmpx`. Final per-UID reject must come after the accepts.
- DoH/DoT bypass: default-reject + DNS redirect means an unprivileged UID can't reach external 53/853; pointing browser at 8.8.8.8 still hits the redirect. Optionally reject `udp dport {784,8853}` (DoQ).
- Reboot: persisted ruleset file loaded by `webwarden-nft.service` via `nft -f` (Phase 05).

## Requirements
- Functional: `render_ruleset(locked_users_with_uids_and_ports)` → full `nft` script (flush table + recreate). `render_set_names(u)` helper. `apply_ruleset()` runs `nft -f` (Linux).
- Non-functional: deterministic ordering; atomic file write to `/etc/webwarden/nftables.ruleset`.

## Architecture (ruleset skeleton)
```
table inet kidfilter {
  set allow_v4_<u> { type ipv4_addr; flags interval; }
  set allow_v6_<u> { type ipv6_addr; flags interval; }
  chain dnsredirect { type nat hook output priority -100;
    meta skuid <uid> udp dport {53,853} redirect to :<port>
    meta skuid <uid> tcp dport {53,853} redirect to :<port> }
  chain egress { type filter hook output priority 0; policy accept;
    meta skuid <uid> ip daddr 127.0.0.1 tcp dport <port> accept   # to own dnsmasq
    meta skuid <uid> ip daddr 127.0.0.1 udp dport <port> accept
    meta skuid <uid> tcp dport {80,443} ip daddr @allow_v4_<u> accept
    meta skuid <uid> tcp dport {80,443} ip6 daddr @allow_v6_<u> accept
    meta skuid <uid> reject with icmpx type admin-prohibited }   # repeat block per locked user
}
```

## Related Code Files
- Implement `nftables_ruleset.py`. Consumed by `apply.py` (Phase 05).

## Implementation Steps
1. `render_ruleset(users)` — emit sets, dnsredirect chain, egress chain, iterating locked users (uid+port from state).
2. Allow loopback to own dnsmasq port BEFORE the per-UID reject; ensure rule order correct.
3. `write_ruleset()` atomic to `/etc/webwarden/nftables.ruleset`.
4. `validate_ruleset(path)` → `nft -c -f <path>` (Linux-gated, surface stderr).
5. `flush_user_sets(u)` helper for `disallow` (so removed IPs drop promptly): `nft flush set inet kidfilter allow_v4_<u>` (+v6); dnsmasq repopulates allowed ones.

## Todo
- [ ] `render_ruleset` (sets + nat redirect + filter egress, per-user blocks)
- [ ] correct rule ordering (accepts before reject)
- [ ] atomic writer + `nft -c -f` validation (Linux-gated)
- [ ] `flush_user_sets` for disallow
- [ ] unit tests: golden ruleset for N users, set-name derivation, empty (no locked users) = minimal valid table

## Success Criteria
Golden-file unit test on Windows; on Linux `nft -c -f` validates; manual check that admin UID is never matched.

## Risk Assessment
- **`meta skuid` in nat/redirect output chain unproven** for this exact pattern (esp. IPv6 in `inet`). VERIFY first thing on Linux; fallback: split v4/v6 into `ip`/`ip6` tables, or use `tproxy`. This is the #2 project risk.
- Rule-order bug → either over-block (admin affected) or under-block (leak). Acceptance test §8 must cover admin-unaffected + raw-IP-blocked.

## Security Considerations
- Default-deny posture must never be weakened: `egress` policy is `accept` only because matching is per-UID reject; a locked UID with no matching accept hits its reject. Confirm no path lets a locked UID reach arbitrary IPs on 80/443.

## Next Steps
Phase 05 wires generation + load + service lifecycle into `apply`.
