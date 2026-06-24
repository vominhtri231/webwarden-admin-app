# Phase 02 — Backend CLI Core & State Model

**Context:** `phase-01-foundations-and-conventions.md` · SPEC §4.1, §4.4 · backend-filtering report.
**Priority:** Critical · **Status:** pending · **Linux-only:** no for logic; user enumeration uses `pwd`/`grp` (Linux modules) so unit-test with monkeypatched fakes on Windows.

## Overview
The CLI backbone: argparse dispatch, the `/etc/webwarden` state layer (locked users, per-user
allowlists, stable port index), and human/user enumeration. All pure logic — no kernel/services
yet (those land in 03–05). Mutating subcommands write state + call `apply` (stubbed until 05).

## Key Insights
- **Stable port index** must not shift when a user unlocks/relocks. Persist an explicit map in `ports.json` `{username: N}`; allocate lowest free N on first lock; never reuse until fully removed. Port = `PORT_BASE + N`.
- All mutations **idempotent** and **exit non-zero with clear stderr** on error (§4.4).
- Never shell-interpolate: subcommands take argv lists; domains validated before storage.
- `users` = real accounts `1000 <= uid < 65534` from `pwd.getpwall()`; `has_sudo` = member of `sudo` or `adm` group (`grp.getgrnam`) or in sudoers — keep to group check (KISS, matches spec's `deluser <u> sudo`).

## Requirements
- Functional: implement `lock/unlock/allow/disallow/list/users/status/apply` arg parsing + state effects; `list`/`users`/`status` produce data structures (JSON formatting in Phase 06 but stub now).
- Non-functional: atomic file writes (temp + `os.replace`); create `/etc/webwarden` tree with correct modes when run as root; clear errors when not root for mutating ops.

## Architecture / Data flow
```
cli.py argparse → handler → state.py (read/normalize/write) → apply.py (regen configs+ruleset) [Phase 05]
users.py: pwd+grp → [{username, uid, locked, has_sudo, allow_count, dns_service_active}]
state.py: locked-users.txt (set), users/<u>/allowlist.txt (one domain/line), ports.json (index map)
```

## Related Code Files
- Create: `cli.py`, `__main__.py`, `state.py`, `users.py`, fill `paths.py`.
- Stub-call: `apply.py` (Phase 05), `jsonapi.py` (Phase 06).

## Implementation Steps
1. `argparse` with subparsers for every contract command; `--json` flags accepted now, formatting deferred to Phase 06.
2. `state.py`: `read_locked()/write_locked()`, `read_allowlist(u)/add_domains(u, [..])/remove_domains(u, [..])`, `alloc_port(u)/free_port(u)/get_port(u)` over `ports.json`. Atomic writes, create dirs `0750`.
3. `users.py`: `list_users()` (uid filter), `has_sudo(u)`, `uid_of(u)`. Make the `pwd`/`grp` import lazy/injectable so tests run on Windows with fakes.
4. Handlers: `allow` → validate each domain (reject invalid, non-zero), dedupe, append, call `apply`. `disallow` → remove, call `apply`. `lock` → add to locked set, alloc port, call `apply`. `unlock` → remove from locked, stop service (Phase 05), free port, call `apply`.
5. Root check for mutating commands; friendly stderr + exit 2 if not root.
6. Idempotency: locking an already-locked user, allowing an existing domain → exit 0, no-op.

## Todo
- [ ] argparse dispatch for all 9 contract commands
- [ ] `state.py` with atomic writes + port index
- [ ] `users.py` with injectable pwd/grp
- [ ] mutating handlers (validate → state → apply stub)
- [ ] root check + non-zero error contract
- [ ] unit tests: port allocation stability, idempotency, validation rejection, allowlist add/remove

## Success Criteria
Unit tests (Windows, fakes for pwd/grp/fs via tmp dir) prove: port indices stable across unlock/relock; invalid domains rejected with non-zero; idempotent re-runs; allowlist round-trips.

## Risk Assessment
- Port reuse causing wrong-user redirect if a freed index is reassigned while old service lingers → only free port after service fully disabled (Phase 05); test the alloc/free ordering.

## Security Considerations
- Mutating ops require root (enforced by Polkit at the GUI layer, re-checked here). Validate domains/usernames before any filesystem path construction (`username` must match an existing passwd entry — reject arbitrary strings to prevent path traversal in `users/<u>/`).

## Next Steps
Unblocks 03/04 (config generators consume allowlist + port + uid) and 06 (JSON builders consume these structures).
