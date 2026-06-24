# Phase 01 — Foundations & Conventions

**Context:** `../../SPEC.md` · `plan.md` · all three researcher reports.
**Priority:** Critical (everything references this) · **Status:** pending · **Linux-only:** no.

## Overview
Pin down the canonical repo layout, Python tooling, the shared domain-validation contract,
and the docs scaffold so every later phase references one fixed structure (no divergence).

## Key Insights
- Both backend and GUI are Python → one toolchain, but they install to different locations and must not import each other at runtime.
- Domain validation must be **byte-identical** in both. KISS choice: duplicate the tiny function, guard with a shared test fixture (no shared installed package — avoids site-packages coupling).
- GTK cannot import on Windows → keep all GTK code out of unit-testable modules; syntax-check with `py_compile`/`pyflakes` only.

## Requirements
- Functional: canonical directory tree exists; `validation.py` defined once with normalization + regex `^[a-z0-9]([a-z0-9-]*\.)+[a-z]{2,}$`; docs/ files scaffolded.
- Non-functional: every code file < 200 lines; kebab-case module names where idiomatic (Python uses snake_case per ecosystem); no secrets committed.

## Architecture (canonical layout — authoritative)
```
backend/
  webwarden                      # wrapper -> exec python3 -m webwarden_cli (installed /usr/local/sbin/webwarden)
  webwarden_cli/
    __main__.py  cli.py          # argparse dispatch + subcommand wiring
    state.py     users.py        # /etc/webwarden I/O, port-index; uid>=1000 + sudo detection
    dnsmasq_config.py  nftables_ruleset.py
    apply.py     services.py     # orchestration + systemctl wrappers
    logparse.py  jsonapi.py      # blocked-line parse; status/list/users/log builders
    validation.py                # domain regex + normalize (canonical copy)
    paths.py                     # all /etc, /var/log, port-base constants
  systemd/ polkit/ logrotate/    # webwarden-dns@.service, webwarden-nft.service, *.policy, logrotate cfg
  tests/                         # pytest (Windows-runnable)
gui/
  webwarden_admin/
    __main__.py app.py window.py cli_client.py validation.py
    views/{users_view,allowlist_view,log_view,status_view}.py
    widgets/  models/
  data/{webwarden-admin.desktop, webwarden-admin.css, icons/}
  webwarden-admin                # wrapper script
  tests/                         # pytest pure-logic (no GTK import)
docs/{development-roadmap,project-changelog,system-architecture,code-standards}.md
install.sh  uninstall.sh
```

## Constants to fix now (`backend/webwarden_cli/paths.py`)
- `ETC = /etc/webwarden`, `USERS_DIR = /etc/webwarden/users/<u>/{allowlist.txt,dnsmasq.conf}`
- `LOCKED_FILE = /etc/webwarden/locked-users.txt`, `PORT_INDEX = /etc/webwarden/ports.json`
- `LOG_DIR = /var/log/webwarden` (mode 750, root:adm), `<u>.log` per user.
- `NFT_TABLE = inet kidfilter`, `PORT_BASE = 5354`, `MIN_UID = 1000`.

## Implementation Steps
1. Create the tree above with empty `__init__.py` and stub modules (raise `NotImplementedError`).
2. Write `validation.py` (backend) — `normalize_domain(raw)` strips scheme/path/`www.`? (no — keep `www.`), lowercases, trims; `is_valid_domain(d)` regex check. Copy verbatim to `gui/webwarden_admin/validation.py`.
3. Add `backend/tests/test_validation.py` with a shared fixture list of valid/invalid domains + pasted-URL cases; mirror in `gui/tests/`.
4. Tooling: `pyproject.toml` per package (or one root) with `pytest`, `pyflakes`; add `scripts/check.ps1`/`check.sh` running `py_compile` over all `.py` + `pyflakes` + `pytest backend gui`.
5. Scaffold `docs/` files with headers (roadmap phases, empty changelog, architecture stub, code-standards: snake_case, <200 lines, try/except, argv arrays).

## Todo
- [ ] Directory tree + stubs
- [ ] `validation.py` (+ identical GUI copy) + shared fixture
- [ ] Validation unit tests pass on Windows
- [ ] `pyproject.toml` + check script
- [ ] docs/ scaffold

## Success Criteria
`pytest` runs green on Windows for validation; `py_compile` passes on all stub files; tree matches layout.

## Risk Assessment
- Drift between the two `validation.py` copies → mitigate with identical fixture tests in both suites (a later CI step diffs the two files).

## Security Considerations
- Validation is the single trust boundary for domain input before it reaches argv → must reject anything not matching the regex; tests must include injection-shaped inputs (`a.com; rm -rf`, spaces, unicode).

## Next Steps
Unblocks Phase 02 (uses `paths.py`, `validation.py`, `state.py` stub).
