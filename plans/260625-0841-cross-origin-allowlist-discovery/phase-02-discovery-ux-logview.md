# Phase 02 — Discovery UX in the Log view (GUI)

**Context:** [plan.md](plan.md) · depends on **Phase 01** (`--group` flag + `broad` field).
Grounds: `gui/webwarden_admin/views/log_view.py`, `cli_args.py`, `models/{row_items,log_filter}.py`,
`cli_client.py` (busy-key), `views/allowlist_view.py` (dropdown pattern to copy).

## Overview
- **Priority:** High. **Status:** ✅ coded — Windows tests green; GTK behavior Mint-verify pending.
- **Goal:** Turn the existing Log view into the discovery workflow: filter blocked attempts by user,
  see them collapsed to registrable domains with a "broad" warning, multi-select the domains a site
  needs, and approve them in one privileged `allow` call. **Edit `log_view.py` in place — no new view.**

## Key insights
- 70% exists: Summary toggle + `log --summary` + ranked rows + "Allow selected". We add a user filter,
  grouping, a broad badge, and multi-select approve.
- **Approve is free at the CLI:** `allow` is `nargs="+"`, so N selected domains for a user = one
  `allow_args(user, [d1, d2, …])` mutation. No backend change in this phase.
- **Gotcha #1 is a live trap here:** the new user dropdown loads users via `users_args()`. It MUST
  use a distinct busy-key `"log-users"` — sharing `"users"`/`"allowlist-users"` gets it silently dropped.

## Requirements
- Functional:
  - User filter dropdown in the toolbar: "All users" + each username. Selecting one passes `user=` to
    `log_args` and reloads.
  - Summary mode passes `group=True` (grouped registrable domains). A "Broad?" column shows a warning
    for `broad` rows; visible only in summary mode (like the existing Count column).
  - Multi-select rows; "Allow selected" approves *all* selected, grouped by user → one `allow` per user.
    Confirm dialog states the count ("Allow 3 domains for alice?").
- Non-functional: `log_view.py` stays < 200 lines (extract approve-grouping to a pure model helper);
  approve-grouping + arg-building unit-tested on Windows; GTK behavior manual on Mint.

## Architecture / changes
**`cli_args.log_args`** — add `group=False`; append `--group` when `summary and group`:
```python
def log_args(user=None, since=None, limit=None, summary=False, group=False):
    args = [WEBWARDEN, "log", "--json"]
    if summary: args.append("--summary")
    if summary and group: args.append("--group")
    ...
```

**`models/row_items.LogItem`** — add `broad = GObject.Property(type=bool, default=False)`; ctor arg
`broad=False`.

**New `models/approve_grouping.py`** (pure, no GTK — testable):
```python
def group_domains_by_user(rows):
    """rows: iterable of {'user','domain'} -> {user: [unique domains, in order]}."""
    out = {}
    for r in rows:
        seen = out.setdefault(r["user"], [])
        if r["domain"] and r["domain"] not in seen:
            seen.append(r["domain"])
    return out
```

**`views/log_view.py`** — modify in place:
1. Toolbar: add `Gtk.DropDown` (expression `PropertyExpression(StringObject, None, "string")`, copy
   allowlist_view.py:26) before the range buttons. Default item "All users". `notify::selected` sets
   `self._user` (None for "All") and reloads. Load names via
   `self.client.run_json(users_args(), self._populate_users, self._err, key="log-users")` — **distinct key**.
2. `reload()`: pass `user=self._user` and `group=self._summary` to `log_args`.
3. `_populate`: read `r.get("broad", False)` into `LogItem`; toggle the new "Broad?" column visible
   with `self._summary` (mirror `_count_col`).
4. Selection: `Gtk.SingleSelection` → `Gtk.MultiSelection(model=self.store)`.
5. `_allow_selected`: read `selection.get_selection()` (Gtk.Bitset) → collect `LogItem`s → dicts →
   `group_domains_by_user` → for each user `run_mutation(allow_args(user, domains), …, key="allow:"+user)`;
   confirm dialog summarizes counts; on done refresh. Empty selection → existing "select a row" notice.
6. "Broad?" column: text "⚠ broad" when `broad` else "" (reuse `_add_column`, bind on a derived label
   or add a small bind that maps bool→text).

## Related code files
- **Create:** `gui/webwarden_admin/models/approve_grouping.py`; `gui/tests/test_approve_grouping.py`.
- **Modify:** `views/log_view.py`, `cli_args.py`, `models/row_items.py`;
  extend `gui/tests/test_cli_args.py` (group flag).
- **Delete:** none.

## Implementation steps
1. `cli_args.log_args` group param + test.
2. `LogItem.broad` property.
3. `approve_grouping.py` + unit tests (multi-user split, dedup, empty, blank domain).
4. Rework `log_view.py`: user dropdown (distinct key), group on summary, broad column, MultiSelection,
   batch approve. Keep < 200 lines (extract toolbar build if needed).
5. `pwsh scripts/check.ps1` green.
6. Docs: update `docs/system-architecture.md` (discovery flow), `docs/project-changelog.md`, CLI-contract
   note (`log --summary --group`). Add the `"log-users"` busy-key to CLAUDE.md gotchas if it isn't covered.

## Todo
- [x] `log_args(group=…)` + test
- [x] `LogItem.broad`
- [x] `approve_grouping.py` + tests
- [x] `log_view.py`: user dropdown (key `"log-users"`), group-on-summary, broad column, MultiSelection, batch approve
- [x] keep `log_view.py` < 200 lines (170)
- [x] `scripts/check.ps1` green
- [x] docs updated
- [ ] **Mint manual acceptance** (the real end-to-end test) — pending on target

## Success criteria
- Windows: `check.ps1` green; `approve_grouping` + `log_args` covered.
- **Mint (manual — the real test):** lock alice, allow only `youtube.com`, open it. In Log view:
  select alice in the user filter, toggle Summary → blocked deps show **grouped**
  (`googlevideo.com`, `ytimg.com`, …) with `googleapis.com`/`gstatic.com` flagged **broad**.
  Multi-select the needed domains → "Allow selected" → one Polkit prompt → re-open youtube → it loads.
- Dropdown populates (busy-key not dropped); no regression to existing log filter/poll/clear.

## Risks / mitigations
- **`log_view.py` exceeds 200 lines** → extract toolbar construction into a small private builder or a
  `widgets/` helper; keep approve-grouping in the model (already planned).
- **MultiSelection + ColumnView quirks** are GTK-version-sensitive → verify on Mint (GTK 4.14); the
  bitset-iteration is the one bit not unit-testable on Windows.
- **Admin approves a `broad` domain unknowingly** → the column warns, but it's advisory; acceptable per
  the human-in-the-loop model. Do **not** block or auto-skip broad domains.

## Security
- Approve path is the existing `pkexec → webwarden allow` (no new Polkit action; argv-agnostic policy).
- No auto-approval anywhere — every domain is an explicit admin selection. Default-deny is preserved.

## Next
v1 done. Future: site bundles (deferred), DoH egress blocking (docs note now).
