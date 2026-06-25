---
title: Cross-origin allowlist discovery (registrable-domain grouping + Log-view discovery UX)
slug: cross-origin-allowlist-discovery
date: 2026-06-25
status: implemented — both phases coded, 136 Windows tests green (124 baseline + 12 new), code-reviewed (DONE_WITH_CONCERNS, LOW only); Mint acceptance pending
mode: auto (codebase fully scoped inline; no researchers needed)
blockedBy: []
blocks: []
owner: Tri Vo
---

# Cross-origin allowlist discovery

**Problem.** A modern site spans many registrable domains (youtube.com needs googlevideo.com,
ytimg.com, ggpht.com, gstatic.com, googleapis.com…). Allowlisting `youtube.com` alone leaves the
page broken — every sister domain sinkholes to `0.0.0.0`. Domain-allowlisting filters by *origin*;
the web's trust unit is the *page*, which crosses origins. This is the product's core usability flaw.

**What we are NOT fixing.** dnsmasq `server=/d/` + `nftset=/d/` are already *suffix* matches, so
allowlisting `googlevideo.com` already covers `*.googlevideo.com`. The dynamic-subdomain half is
solved. We do **not** add wildcard syntax or a new blocking mechanism.

**Strategy (empirical discovery, human-in-the-loop).** The Log view *already* polls
`log --summary --json`, ranks `{user, domain, count}`, and has an "Allow selected" button — ~70% of
"discovery" exists. Two gaps remain: (1) the summary floods with dynamic subdomains
(`r3---sn-x.googlevideo.com` ×200) instead of collapsing to `googlevideo.com`; (2) the view isn't
sharpened for the "what broke for this user, approve the set" workflow. We close both. Bundles
(a curated catalog) are deferred — they're an accelerator, not the fix (YAGNI).

## Decisions (confirmed with maintainer)
- **v1 scope:** registrable-domain grouping + Log-view discovery UX. **Bundles deferred.**
- **Approve UX:** multi-DOMAIN batch approve for one user, one privileged `allow` call. (This is
  *not* the multi-USER feature dropped in `260625-0710` — that stays dropped.)
- **Grouping:** heuristic (last-2-labels + a small multi-label-suffix exceptions set). **No full PSL**
  — a human approves every entry, so rare misgroupings are corrected at approval time (KISS).

## Phases (sequential — Phase 02 needs Phase 01's `--group` flag + `broad` field)
| # | Phase | Layer | Windows-testable | Status |
|---|-------|-------|------------------|--------|
| 01 | [Registrable-domain grouping](phase-01-registrable-grouping-backend.md) | backend CLI | ✅ pure logic | ✅ done (tests green) |
| 02 | [Discovery UX in Log view](phase-02-discovery-ux-logview.md) | GUI | ⚠ logic yes, GTK manual on Mint | ✅ coded (Mint verify pending) |

## Implementation notes (260625)
- Backend: new `domain_groups.py` (`registrable` heuristic + `is_broad`); `summarize(group=)`,
  `log_summary_json(group=)`, additive `log --summary --group` flag. `log --summary` alone byte-identical.
- GUI: `log_view.py` reworked in place (170 lines) — per-user dropdown (key `"log-users"`), Summary⇒group,
  "Broad?" column, `MultiSelection` + batch approve via new pure `models/approve_grouping.py`. Poll pauses
  while rows are selected. `cli_args.log_args(group=)`, `LogItem.broad`.
- Review (DONE_WITH_CONCERNS): additive-contract/busy-key/Polkit/no-widening all PASS. Applied the
  redundant-reload guard. **Known limitations (deferred, by design):** (1) a multi-select batch is
  all-or-nothing — if a selected (malformed) logged domain fails backend validation the whole per-user
  batch is rejected; (2) changing the filter/search/user mid-selection discards the selection.
- **Mint acceptance still required** (the real test): allow only `youtube.com`, load it, filter to that
  user + Summary → confirm grouped deps appear with `broad` flags, batch-approve, re-open → site loads.

## Branch & commits
One feature branch off latest `main` (phases are dependent → avoid PR stacking):
`feat/cross-origin-discovery`, two focused conventional commits (`feat(cli): …`, then `feat(gui): …`).

## Key constraints
- **Stable CLI contract = additive only.** `--summary` alone unchanged; new opt-in `--group` flag;
  grouped rows gain a `broad` field. No new subcommand, no new Polkit action (argv-agnostic).
- **Gotcha #1 (busy-key):** the new per-user dropdown in Log view loads users — give it a distinct
  key (`"log-users"`), never share `"users"`/`"allowlist-users"`, or its load is silently dropped.
- **200-line file guard:** `log_view.py` is 143 lines; extract approve-grouping into a pure
  `models/` helper (also unit-testable) to stay under 200.
- **Dev = Windows.** Grouping + arg-building + selection-grouping are unit-tested on Windows. The
  end-to-end discovery loop (visit youtube → grouped blocks → approve → site loads) is **Mint-only**.

## Out of scope (documented, not built)
- Site bundles / curated catalog (separate future plan).
- DoH bypass: a locked user using DNS-over-HTTPS sidesteps dnsmasq entirely. Note in docs that
  nftables must block outbound 853 + known DoH endpoints; not addressed here.
- Shared-CDN leakage is *inherent* to domain allowlisting — we surface it (`broad` flag), not solve it.

## Docs to update on completion
`docs/system-architecture.md` (discovery flow + grouping), `docs/project-changelog.md`,
CLI-contract note for `log --summary --group`.
