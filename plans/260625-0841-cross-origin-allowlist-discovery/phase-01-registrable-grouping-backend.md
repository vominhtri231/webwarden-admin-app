# Phase 01 — Registrable-domain grouping (backend CLI)

**Context:** [plan.md](plan.md) · grounds: `backend/webwarden_cli/{logparse,jsonapi,cli}.py`,
tests `backend/tests/test_{logparse,jsonapi,cli}.py`.

## Overview
- **Priority:** High (keystone — Phase 02 depends on it).
- **Status:** ✅ done — implemented; backend tests green.
- **Goal:** Add an opt-in `--group` mode to `log --summary` that collapses blocked subdomains to
  their registrable domain (eTLD+1) and flags multi-tenant "broad" CDNs. Pure logic; fully
  Windows-testable. **Additive** to the stable contract.

## Key insights
- The summary path is exactly one chain: `cmd_log(--summary)` → `jsonapi.log_summary_json` →
  `logparse.summarize(collect_blocked(...))`. Grouping plugs into `summarize` with one new param.
- `summarize` output shape is `{user, domain, count, last_seen}`. Grouped mode keeps that shape,
  sets `domain` = registrable domain, sums `count`, and **adds** `broad: bool`. GUI changes stay tiny.
- dnsmasq suffix-matches, so approving the *registrable* domain (e.g. `googlevideo.com`) already
  covers every dynamic subdomain. Grouping is purely a presentation/dedup win for the admin.

## Requirements
- Functional: `webwarden log --summary --group [--json]` returns rows keyed by registrable domain,
  count = sum of member subdomain counts, plus `broad`. `--summary` **without** `--group` is byte-identical
  to today (back-compat). Heuristic eTLD+1; no network, no data-file download.
- Non-functional: new module < 100 lines; no new third-party deps; no circular imports.

## Architecture
New module `backend/webwarden_cli/domain_groups.py` (snake_case — Python import rules; matches
`dnsmasq_config.py` convention). No deps on other webwarden modules → importable from `logparse`.

```python
# domain_groups.py  — heuristic eTLD+1 + advisory broad-CDN set (NOT the full PSL; YAGNI)
_MULTI_LABEL_SUFFIXES = {           # where eTLD+1 = last THREE labels
    "co.uk", "org.uk", "gov.uk", "ac.uk", "co.jp", "com.au", "net.au", "org.au",
    "com.br", "com.cn", "com.hk", "co.in", "co.kr", "co.nz", "co.za", "com.sg", "com.tw",
}

def registrable(domain):
    """Best-effort eTLD+1. A human approves the result, so rare misses are acceptable."""
    d = (domain or "").strip(".").lower()
    labels = [x for x in d.split(".") if x]
    if len(labels) <= 2:
        return d
    if ".".join(labels[-2:]) in _MULTI_LABEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])

_BROAD_DOMAINS = {                  # multi-tenant CDNs: allowing one opens many sites
    "cloudfront.net", "amazonaws.com", "akamai.net", "akamaihd.net", "akamaiedge.net",
    "fastly.net", "googleusercontent.com", "googleapis.com", "gstatic.com",
    "azureedge.net", "cloudflare.net", "windows.net",
}

def is_broad(registrable_domain):
    return registrable_domain in _BROAD_DOMAINS
```

`logparse.summarize` gains `group=False`:
```python
from . import domain_groups   # add to existing imports

def summarize(rows, group=False):
    agg = {}
    for r in rows:
        dom = domain_groups.registrable(r["domain"]) if group else r["domain"]
        key = (r["user"], dom)
        a = agg.setdefault(key, {"user": r["user"], "domain": dom,
                                 "count": 0, "last_seen": None})
        if group:
            a["broad"] = domain_groups.is_broad(dom)
        a["count"] += 1
        if r["time"] and (a["last_seen"] is None or r["time"] > a["last_seen"]):
            a["last_seen"] = r["time"]
    out = list(agg.values())
    out.sort(key=lambda a: (a["last_seen"] or "", a["count"]), reverse=True)
    return out
```

`jsonapi.log_summary_json(user, since, year, group=False)` → forwards `group` to `summarize`.
`cli.py`: add `sp.add_argument("--group", action="store_true", ...)` to the `log` parser; in
`cmd_log` pass `group=args.group`; the human-readable summary print path is unchanged (extra `broad`
key ignored).

## Related code files
- **Create:** `backend/webwarden_cli/domain_groups.py`; `backend/tests/test_domain_groups.py`.
- **Modify:** `logparse.py` (`summarize` param), `jsonapi.py` (`log_summary_json` param),
  `cli.py` (`--group` flag + pass-through).
- **Delete:** none.

## Implementation steps
1. Write `domain_groups.py` (`registrable`, `is_broad`, the two data sets).
2. Add `group=False` to `logparse.summarize`; import `domain_groups`.
3. Thread `group` through `jsonapi.log_summary_json` and `cli.cmd_log` + `--group` arg.
4. Tests: `test_domain_groups.py` (plain/multi-label/edge: IP-like, single-label, trailing dot, empty,
   `www.a.b.co.uk`); extend `test_logparse.py` (group sums counts, picks latest `last_seen`, `broad`
   set correctly, ungrouped unchanged); extend `test_jsonapi.py`/`test_cli.py` (flag wiring).
5. `pwsh scripts/check.ps1` → py_compile + pytest green.

## Todo
- [x] `domain_groups.py` with `registrable` + `is_broad`
- [x] `summarize(group=…)`
- [x] `log_summary_json(group=…)` + `cmd_log` `--group`
- [x] tests (domain_groups, logparse group, cli/jsonapi wiring)
- [x] `scripts/check.ps1` green

## Success criteria
- `webwarden log --summary --json` output unchanged vs main (diff-clean).
- `webwarden log --summary --group --json` collapses subdomains to eTLD+1, sums counts, adds `broad`.
- All existing tests still pass; new tests cover heuristic edges + grouping.
- **Mint pre-flight (acceptance, not blocking code):** lock a test user, allow only `youtube.com`,
  load it, then `webwarden log --summary --group --json` — confirm `googlevideo.com`, `ytimg.com`,
  etc. appear as grouped rows. Validates the whole premise before Phase 02 UI work.

## Risks / mitigations
- **Heuristic misgroups exotic suffixes** (e.g. `s3.dualstack.us-east-1.amazonaws.com` → `amazonaws.com`,
  which is also correctly flagged `broad`). Acceptable: human approves; extend `_MULTI_LABEL_SUFFIXES`
  if a real miss bites. Documented as intentional.
- **`broad` set drifts** as CDNs change. It's advisory only; keep it small and curated; refine on Mint.

## Security
- Read-only command path; no privilege change. Grouping never *widens* what gets allowed — it only
  changes how blocked attempts are *displayed*; the admin still explicitly approves each domain.

## Next
Phase 02 consumes `--group` + `broad` in the Log view.
