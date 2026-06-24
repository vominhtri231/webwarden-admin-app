# webwarden — Security & Correctness Review

Date: 2026-06-24
Reviewer: code-reviewer (staff-eng pass)
Branch: feat/webwarden-implementation
Scope: enforcement-critical backend + packaging + GUI client. Static review only
(no Linux runtime: nft/dnsmasq/systemd/GTK semantics reasoned, not executed).

## Verdict
The enforcement model is fundamentally sound: per-UID match, accepts-before-reject
ordering, admin/root never referenced (no skuid 0), v4+v6 covered, argv-only (no
shell anywhere), validate-before-load fail-closed in both `apply.py` and the nft
systemd unit. No default-deny *leak* found in the rendered ruleset. The issues
below are mostly correctness/robustness and a few hardening gaps; one HIGH can
silently break enforcement for a locked user, and two HIGH affect allowed-site
usability. Nothing CRITICAL-as-in-bypass in the static text, but see CRITICAL-1
(trust-boundary divergence risk) and the verify-on-target list.

---

## CRITICAL

### C1. dnsmasq `address=/#/::` may not be valid syntax → instance fails to start (verify, but high-confidence defect)
`dnsmasq_config.py:46-47` emits BOTH:
```
address=/#/0.0.0.0
address=/#/::
```
dnsmasq's `address=/<domain>/<ip>` infers family from the IP. The `/#/` form is
the wildcard. Two separate `address=/#/` lines (one v4, one v6) is the documented
way to null-route both families, so this is likely correct — BUT `--test` must
confirm 2.90 accepts the bare `::` (some builds need `address=/#/::` exactly,
others reject `#` wildcard with IPv6). If `dnsmasq --test` fails, the per-user
`webwarden-dns@<user>` unit fails to start. Then: redirect still sends the UID's
:53 to a dead local port → all DNS fails → user resolves nothing → effectively
still denied (fail-closed for the user, good) BUT allowed sites also break and
`status` shows `service-down`.
Fix: keep as-is but make this the #1 `dnsmasq --test` gate on target. If it
fails, the known-good fallback is `address=/#/0.0.0.0` + `address=/#/::` already
present; if `--test` still rejects, drop to `server=/#/` returning NXDOMAIN is
NOT equivalent (would forward) — instead use `address=/#/0.0.0.0` only and rely
on no AAAA being answerable. Decide on target. **(verify-on-target, but treat as
release-gating.)**

---

## HIGH

### H1. `apply()` is not fail-closed against a per-user dnsmasq config that fails validation — and never runs `validate_conf` at all
`apply.py:18-20` writes every user's dnsmasq.conf but **never calls
`dnsmasq_config.validate_conf()`**, while `validate_conf` exists and is tested.
Consequence: a malformed dnsmasq.conf (e.g. from the C1 family-syntax risk, or a
future bad upstream) is written and the unit is started/restarted regardless. The
nft side is validated; the DNS side is not. If `enable_start_instance` /
`restart_instance` then fails, `apply()` raises mid-reconcile (services._run
raises CommandError) — but only after the ruleset is already loaded and possibly
some instances toggled, leaving partial state.
Fix: after writing each user's conf in step 1, call `validate_conf(path)` and
`raise RuntimeError` on failure BEFORE loading the ruleset, mirroring the nft
gate. Validate all configs first, then load nft, then reconcile.

### H2. `apply()` partial-failure leaves inconsistent runtime; no aggregation/rollback
`apply.py:32-40` iterates start/restart/stop. Any single `systemctl` failure
raises `CommandError` (services.py:23) and aborts the loop, so later users are
never reconciled (e.g. alice started, bob never started, carol never stopped).
The CLI prints the error and exits non-zero (good), but runtime is now a mix of
old and new. For a security tool, a failed `restart_instance` on an already-locked
user means that user keeps running with **stale allowlist sets** (cache holds old
IPs) while the admin believes the change applied.
Fix: collect failures per-user, continue reconciling the rest, then raise an
aggregated error listing which users failed. At minimum, reconcile in an order
that prioritizes *stopping* now-unlocked users first is NOT what you want
(stopping frees enforcement) — keep stops last, but ensure every desired user is
attempted even if one fails.

### H3. QUIC / HTTP-3 (UDP 443) to allowed sites is rejected → allowed sites degrade or fail
`nftables_ruleset.py:59-60` accepts only `tcp dport { 80, 443 }` to the allow
sets. Modern browsers reach many sites over **UDP 443 (QUIC/HTTP3)** first.
A locked user visiting an allowed site: UDP 443 to the allowed IP is caught by
the final `reject` (admin-prohibited). Browsers *usually* fall back to TCP, but
(a) some resources stall, (b) the reject generates noise, (c) for security this
is fine (no bypass) but it violates the acceptance test spirit "wikipedia.org
loads". This is a usability defect, not a hole.
Fix: add `meta skuid <uid> udp dport 443 ip daddr @<v4> accept` and the v6 line,
OR explicitly document that QUIC is blocked by design and rely on TCP fallback.
Recommend allowing UDP 443 to the *allow sets only* (still default-deny for
everything else) to match user expectation. Decide deliberately.

### H4. dnsmasq.conf written world-readable (0644); discloses each user's full allowlist
`dnsmasq_config.py:63` writes mode `0644` under `/etc/webwarden/users/<user>/`.
`/etc/webwarden` is 0750 (state.py `_ensure_dir` default 0750; install.sh makes
the root 0750), so the *directory* gates traversal — but the file mode is still
0644 and `users_dir()`/`user_dir()` are created by `state._ensure_dir` at 0750,
which blocks `other`. Net effect today: protected by directory mode. However the
allowlist *content* (browsing policy, mildly sensitive) sits at 0644 and would be
exposed if the dir mode ever loosens or the file is copied. Defense-in-depth:
write dnsmasq.conf at `0640` (root:root). It must remain readable by the dnsmasq
process — dnsmasq starts as root and reads the conf before dropping privileges,
so 0640 root-owned is fine. **(file-mode reasoning is verify-on-target for the
dnsmasq drop-priv timing, but root reads conf pre-drop, so safe.)**

---

## MEDIUM

### M1. `cmd_allow`/`cmd_disallow` mutate state, then `apply()` — but `apply()` failure leaves state and runtime divergent with a zero-ish error path
`cli.py:47-48` (and 61-62): `state.add_domains(...)` commits to disk, THEN
`apply_module.apply(...)`. If apply raises (see H1/H2), main()'s top guard
(cli.py:219) returns exit 1 with the message — good, non-zero exit — but the
allowlist file is already updated while enforcement was not (fully) re-applied.
Re-running `webwarden apply` reconciles, but the transient window shows success
on disk / failure in kernel. Acceptable for a single-admin tool; document that on
apply error the admin must re-run `apply`. Consider catching apply failure in the
command and printing "state saved but enforcement not applied; run 'webwarden
apply'".

### M2. `cmd_lock` validates user & root, but allocates index/locks BEFORE confirming apply succeeds; sudo warning is cosmetic
`cli.py:67-79`: order is set_locked → alloc_index → apply → sudo warning. If the
user is in `sudo`/`admin`, the lock is silently defeated (skuid rule never matches
an admin's processes because... actually it DOES match by UID regardless of group
— see M3). The warning is printed but the user is still marked locked and an
instance starts. That's the spec's intent ("do not auto-remove sudo; just warn").
Fine. No change required; flagged for awareness.

### M3. Admin-group membership does NOT actually bypass the nft rule — the bypass is `sudo` (escalation), and the tool can't see that nuance
`users.has_sudo` (users.py) checks `sudo`/`admin` groups. The nft rule matches
`meta skuid <uid>` for the locked user's own UID. A locked user who is ALSO in
`sudo` is still filtered for processes running as their own UID — the "defeat" is
that they can `sudo` to root (skuid 0, unmatched) and disable webwarden entirely.
The warning text "has admin (sudo) rights, which defeats the lock" is accurate in
spirit. No code defect; ensure README explains the real bypass is privilege
escalation, not the group flag per se.

### M4. `logparse._BLOCK_RE` is brittle and the `_extract_iso` year handling can misdate December/January logs
`logparse.py:20-21,30-37`: timestamps from dnsmasq omit the year; caller passes
`datetime.date.today().year` (cli.py:144). A log line written on Dec 31 read on
Jan 1 will be stamped with the *new* year → `--since` filtering and ordering
wrong across the year boundary, and after logrotate the compressed prior-year
logs are misdated. Low blast radius (cosmetic on a household tool) but real.
Fix: when month > current month, assume previous year. Also `_BLOCK_RE` allows
domain chars `[A-Za-z0-9.\-]` — fine, but anchor/escape verified; confirm the
exact dnsmasq 2.90 line format on target (already flagged LINUX-VERIFY) — if the
real format is `config example.com is 0.0.0.0` the regex matches; if it's
`/etc/.../dnsmasq.conf example.com is <NXDOMAIN>` it won't. **(verify-on-target.)**

### M5. `services.list_active_instances` parses `systemctl` glob output positionally; `--state=active` excludes `activating`/`failed`, so reconcile may double-start
`services.py:53-65`: only `--state=active` units are "current". A unit that is
`activating` or `failed` (crash-looping per the unit's StartLimitBurst=3) is NOT
in `current`, so `apply` takes the `enable_start_instance` branch (`enable --now`)
for an already-enabled-but-failed unit. `enable --now` on an already-enabled unit
is idempotent-ish but `start` on a failed unit hit by StartLimit returns non-zero
→ `_run` raises → H2 abort. Net: a crash-looping user breaks the whole apply.
Fix: query `--state=active,activating,failed` (or list all `webwarden-dns@*` and
branch on load/active state), and prefer `restart` for any already-loaded unit.

### M6. `uninstall.sh` does not `systemctl daemon-reload` semantics issue + leaves `webwarden-dns@*` enabled symlinks if instances were never "active"
`uninstall.sh:17-19` enumerates `--all` units matching the glob and disables them
— good. But instances enabled but never started (no active state) may still have
`/etc/systemd/system/multi-user.target.wants/webwarden-dns@user.service` symlinks
that `list-units` won't show if not loaded. After `rm` of the template, these
become dangling symlinks. `daemon-reload` runs (line 34). Minor; `systemctl` will
warn about dangling links on next boot. Consider `systemctl disable
'webwarden-dns@*'` via `list-unit-files` too, or `find` the wants dir.
**(verify-on-target.)**

### M7. `install.sh` runs `webwarden apply` (line 63) before enabling the nft unit, and apply loads the ruleset directly via `nft -f` — fine — but if apply fails, install.sh aborts (set -e) AFTER copying files, leaving a half-install
`install.sh:5` is `set -euo pipefail`. If `/usr/local/sbin/webwarden apply` (line
63) exits non-zero (e.g. C1 dnsmasq syntax on this distro), the installer dies
with files in place but services not enabled. Not dangerous (default-deny means
nothing is loaded → no users filtered yet → no lock-out), but leaves a confusing
state. Add a trailing message or `|| { echo "apply failed — fix and re-run"; }`
so the admin knows. Posture is not weakened (fail-closed = nothing enforced =
no broken lock).

---

## LOW

### L1. `validation.normalize_domain` strips port via first `:` — IPv6 literals and odd input normalize to garbage but are then rejected by regex (safe)
`validation.py:42-43`: `"[::1]:443"` → split on `:` → `"[["`-ish → fails
DOMAIN_RE → rejected. Trust boundary holds (regex is allowlist `[a-z0-9-.]`
only, anchored, lowercased). No argv injection possible: no shell, all argv
arrays. Confirmed sound. No fix.

### L2. `DOMAIN_RE` rejects single-label and trailing-dot-only, and rejects valid IDN/punycode upper bound but accepts `xn--` (correct). Also accepts a 1-char TLD? No — `[a-z]{2,}`. Good. Underscore (`_dmarc`) rejected — fine for web allowlist.
No fix; note that wildcard/leading-`*` is rejected (good).

### L3. `state._atomic_write` swallows chmod errors (state.py:26-27)
On Linux as root this won't fail; the `except OSError: pass` is for the Windows
dev host. Acceptable, but on Linux a genuine chmod failure (e.g. immutable file)
is silently ignored, leaving a file at the umask default. Low risk under root.
Consider logging on Linux. Also `.tmp` sidecar in the same dir is fine for
atomicity (same filesystem).

### L4. `cli._is_root()` treats Windows (no geteuid) as root
`cli.py:21-24`: intentional for the dev host so tests exercise the mutate path.
Correct given side effects are mocked. On Linux, `geteuid()==0` is enforced. No
fix; documented in the docstring.

### L5. `cmd_unlock` doesn't check `user_exists`
`cli.py:82-89`: intentional — lets an admin unlock/cleanup a deleted account's
stale state. Idempotent. Fine. Just confirm `state.set_locked(name, False)` +
`free_index` tolerate unknown names (they do — discard/del-if-present).

### L6. `dnsmasq_config` default `min-cache-ttl=60` + restart-to-repopulate
`apply.py` restarts active instances to flush cache after a disallow. With
`min-cache-ttl=60`, a just-removed domain's IP could linger in the nft set for up
to the restart. Restart drops cache → repopulates only allowed → stale IPs gone
on the next nft reload (delete+recreate empties sets). Order in apply.py is: nft
reload (empties sets) THEN restart instances (repopulate). Correct. No fix; good
design, just verify the set is truly emptied by delete+recreate on target.

---

## Verify-on-target (NOT defects — confirm on Linux Mint/Ubuntu 24.04)
- nat `redirect to :port` in the `inet` table `output` hook (the module already
  flags this; if it misbehaves, split to ip/ip6 tables). The whole DNS-capture
  enforcement rests on this.
- `meta skuid` matching in `inet` filter + nat for both v4 and v6.
- dnsmasq 2.90: `address=/#/0.0.0.0` + `address=/#/::` both accepted by `--test`
  AND that `server=/domain/` wins over the `/#/` catch-all (precedence). (C1)
- `nftset=/domain/inet#table#setv4,inet#table#setv6` family routing (A→v4, AAAA→v6).
- dnsmasq retains CAP_NET_ADMIN after privilege drop to populate nft sets (unit
  comment claims this; confirm the dnsmasq user can write the inet sets).
- Exact dnsmasq blocked-log line format vs `_BLOCK_RE` (M4).
- `reject with icmpx type admin-prohibited` valid in `inet` egress (vs needing
  per-family icmp/icmpv6).

---

## Top 3 to fix before shipping
1. **C1 / H1**: Add `dnsmasq --test` gating in `apply.py` (call `validate_conf`
   and raise before loading nft), and confirm the `address=/#/::` line passes
   `--test` on the target. Today the DNS side has zero validation despite a
   ready, tested `validate_conf`. This is the difference between fail-closed and
   silent breakage.
2. **H2 / M5**: Make `apply()` reconcile resilient — query active+activating+failed,
   attempt every desired user even if one systemctl call fails, aggregate errors.
   A single crash-looping instance currently aborts the whole apply and leaves
   stale enforcement.
3. **H3**: Decide QUIC (UDP 443) policy explicitly — either allow UDP 443 to the
   allow sets (recommended for "allowed sites just work") or document the TCP-only
   block. As-is, allowed sites may intermittently fail on modern browsers.

---

## Unresolved questions
- Should a locked user be allowed UDP 443 to allowed IPs (QUIC) or is TCP-only
  intentional hardening? (drives H3)
- On `apply` partial failure, is best-effort-continue + aggregate error preferred
  over abort-on-first? (drives H2)
- Confirm whether `/etc/webwarden/users/<u>/` is created 0750 by `state` on the
  real install (it is via `_ensure_dir` default) so H4's 0644 file is
  dir-gated — still recommend 0640 defense-in-depth.

**Status:** DONE_WITH_CONCERNS
**Summary:** Enforcement text is sound (per-UID, accepts-before-reject, no skuid 0,
v4+v6, argv-only, nft fail-closed). No default-deny leak in the rendered ruleset.
Main concerns: the DNS side is never validated before activation (H1) despite a
ready validator, reconcile aborts on any single systemctl failure leaving stale
enforcement (H2/M5), and QUIC/UDP-443 to allowed sites is rejected (H3). Several
items (redirect-in-inet-output, dnsmasq catch-all syntax/precedence, log format)
can only be confirmed on real Linux and are listed as verify-on-target, not flagged
as defects.
**Report:** C:\Users\vomin\CodeWorkspace\learning\webwarden-admin-app\plans\reports\code-reviewer-260624-2229-webwarden-implementation.md
