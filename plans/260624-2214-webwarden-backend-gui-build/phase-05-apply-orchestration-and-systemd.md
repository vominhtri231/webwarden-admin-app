# Phase 05 — Apply Orchestration & systemd Units

**Context:** phases 02–04 · SPEC §4.1, §3 · systemd-polkit report.
**Priority:** Critical · **Status:** pending · **Linux-only:** YES (systemctl/nft/service lifecycle).

## Overview
Tie state → running system. `apply` regenerates every locked user's dnsmasq.conf + the nftables
ruleset, loads the ruleset, and reconciles the set of running `webwarden-dns@<u>` instances
(start newly-locked, stop newly-unlocked). Ship the templated dnsmasq unit + the one-shot
nft-load unit so policy survives reboot.

## Key Insights (from research)
- `webwarden-dns@.service` template: `%i` = username; `ExecStart=/usr/sbin/dnsmasq -k --conf-file=/etc/webwarden/users/%i/dnsmasq.conf` (`-k` foreground for systemd). `Restart=on-failure`, `StartLimitBurst=3`.
- `webwarden-nft.service`: `Type=oneshot`, `RemainAfterExit=yes`, `ExecStartPre=/usr/sbin/nft -c -f /etc/webwarden/nftables.ruleset`, `ExecStart=/usr/sbin/nft -f ...`, `After=network-pre.target`, `Before=network.target`, `WantedBy=multi-user.target`.
- Order on apply: (1) write configs+ruleset, (2) `nft -c -f` validate, (3) load ruleset (creates empty sets), (4) start/enable dnsmasq instances (they populate sets), (5) stop+disable removed instances, (6) free ports only after disable.
- Reconciliation must be idempotent (re-running `apply` converges, no flapping).

## Requirements
- Functional: `apply()` full reconcile; `lock/unlock/allow/disallow` call `apply` (allow/disallow can do a lighter path: regen that user's conf + `systemctl reload`/restart instance + flush sets).
- Non-functional: never leave a half-applied state — validate before load; on failure, abort with non-zero + stderr and do not disable existing protection.

## Architecture / data flow
```
state (locked, allowlists, ports)
  └─ apply():
       write_user_dnsmasq(u) ∀ locked       (Phase 03)
       write_ruleset(); nft -c -f; nft -f    (Phase 04)
       systemctl enable --now webwarden-dns@u ∀ newly-locked
       systemctl disable --now webwarden-dns@u ∀ newly-unlocked; flush+remove sets; free_port
```

## Related Code Files
- Implement `apply.py`, `services.py` (thin `systemctl`/`nft` argv wrappers, no shell).
- Create `systemd/webwarden-dns@.service`, `systemd/webwarden-nft.service`.

## Implementation Steps
1. `services.py`: `start_instance(u)`, `stop_instance(u)`, `enable_instance(u)`, `reload_instance(u)` (restart, since dnsmasq config change needs reload of nftset directives), `load_ruleset()`, `is_instance_active(u)` — all argv arrays via `subprocess.run(check=True)`, capture stderr.
2. `apply.py`: compute desired vs current (active instances via `systemctl is-active`), reconcile per ordering above.
3. `allow`/`disallow` fast path: regen that user's conf, `restart` instance, `flush_user_sets` on disallow (dnsmasq repopulates remaining). Confirm restart re-reads nftset.
4. Write the two unit files; install paths handled in Phase 09.
5. Reboot test (Linux, Phase 10): enabled units restore state.

## Todo
- [ ] `services.py` systemctl/nft wrappers (argv, stderr capture)
- [ ] `apply.py` idempotent reconcile (start/stop/enable/disable, port free ordering)
- [ ] allow/disallow fast path + set flush
- [ ] `webwarden-dns@.service` + `webwarden-nft.service`
- [ ] validate-before-load guard (abort on `nft -c` failure)
- [ ] unit tests for reconcile logic (mock services layer); Linux: live lock→browse, unlock→restore

## Success Criteria
On Linux: lock user → instance active + rules loaded; unlock → instance gone, port freed; `apply` idempotent; survives reboot (§8). Reconcile logic unit-tested on Windows with a faked `services` layer.

## Risk Assessment
- dnsmasq not re-reading `nftset` after `reload` (SIGHUP) → use full `restart` on allowlist change; verify sets repopulate. 
- Race: ruleset loaded (empty sets) before dnsmasq populates → brief block of allowed sites until first query; acceptable, document.
- Partial apply on error → guard: validate everything before any `disable`/`flush`.

## Security Considerations
- `apply` runs as root (via pkexec). It must refuse to run if ruleset validation fails rather than tearing down existing protection (fail-closed).

## Next Steps
Backend enforcement complete. Phase 06 adds logging/JSON so the GUI can read state.
