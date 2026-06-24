# Phase 08 — GUI Views (Users / Allowlist / Blocked Log / Status)

**Context:** `phase-07-gui-shell-and-cli-client.md` · SPEC §5.3, §5.4, §6 · gtk4-pygobject report.
**Priority:** Critical · **Status:** pending · **Linux-only:** running = YES; model/filter logic = no (unit-testable).

## Overview
Implement the four screens against `CliClient`. Keep each view < 200 lines; push list/sort/filter
model logic into small testable helpers. Every mutation: confirm → pkexec → toast result → refresh.

## Key Insights (from research)
- Tables = `Gtk.ColumnView` + `Gio.ListStore` + `Gtk.SortListModel` + `Gtk.FilterListModel` (TreeView deprecated). Verbose factory wiring — encapsulate in `models/`.
- Auto-refresh = `GLib.timeout_add_seconds(3, poll)`; reuse the in-flight guard so polls don't stack; `return True` to keep ticking, `GLib.source_remove` on view teardown.
- Confirm dialogs = `Gtk.AlertDialog`; toasts via Phase 07 helper.

## Requirements (per screen, from §5.3)
1. **Users panel:** list uid≥1000 (`users --json`); per-row `Gtk.Switch` Locked toggle (→ `lock`/`unlock`); **sudo warning badge** when locked-or-to-be-locked user `has_sudo`, with one-line fix hint (`deluser <u> sudo`); never auto-remove sudo.
2. **Allowlist editor** (selected user): show `list <u> --json` domains; add box accepts `example.com` or pasted URL → normalize (strip scheme/path, lowercase) + validate, else inline error; remove button per row; note "approving a domain also covers its subdomains." Calls `allow`/`disallow` then refresh.
3. **Blocked-attempts log:** ColumnView (time, user, domain, [count in summary]); sortable; filter by user + free text; quick ranges last 24h / 7d (→ `--since`); one-click **"Allow this domain for this user"** (→ `allow`, confirm, toast); auto-refresh poll of `log --json` + manual Refresh.
4. **Status/health bar:** from `status --json` — firewall_loaded indicator + per-locked-user `dns_service_active`; clear error styling when a service is down.

## Architecture
```
views/users_view.py     ─ uses CliClient.run_json(users), run_mutation(lock/unlock)
views/allowlist_view.py ─ list/allow/disallow ; normalize+validate in cli_args/validation
views/log_view.py       ─ ColumnView(models/log_model) + filters + allow-from-row + poll
views/status_view.py    ─ status --json → indicators
models/{log_model,user_model}.py ─ ListStore item GObjects + sorter/filter builders (testable shape)
```

## Related Code Files
- Create the four `views/*.py`, `models/log_model.py`, `models/user_model.py`. Reuse `cli_client`, `cli_args`, `validation`, `widgets`.

## Implementation Steps
1. `models/`: GObject row classes + sorter/filter factory functions; keep pure-enough helpers (e.g. URL-paste normalization, "last 24h" → ISO) in `cli_args`/`validation` for unit tests.
2. Users view: load + render switches + sudo badge; wire toggle → confirm → mutation → refresh + toast.
3. Allowlist view: domain entry normalize/validate + inline error; add/remove → mutation → refresh; subdomain note label.
4. Log view: ColumnView + sort/filter + quick-range buttons + allow-from-row + 3s poll (guarded) + manual refresh; summary-mode toggle (`log --summary`).
5. Status view: indicators + down-service error surface.
6. Wire all four into the Phase 07 `Gtk.Stack`.

## Todo
- [ ] models (row GObjects + sorter/filter)
- [ ] Users panel (toggle + sudo badge + fix hint)
- [ ] Allowlist editor (paste-URL normalize + validate + add/remove + subdomain note)
- [ ] Blocked log (ColumnView, sort/filter, quick ranges, allow-from-row, poll + manual refresh, summary toggle)
- [ ] Status/health bar
- [ ] unit tests: URL→domain normalization, "last 24h/7d"→ISO, filter predicate, summary grouping shape

## Success Criteria (maps to §8 acceptance)
On Linux: toggling Locked locks/unlocks; allow/disallow reflected after refresh; a real blocked visit appears as a row attributed to the right user/domain/time; "Allow this domain" makes the site work and stops new blocks; status reflects service down/up. On Windows: normalization/filter/grouping unit tests pass.

## Risk Assessment
- ColumnView wiring complexity → encapsulate once in `models/`, reuse; budget extra time. 
- Poll overlap / leak → single guarded timeout, removed on teardown.
- Paste-URL edge cases (ports, userinfo, IDN) → normalize then validate; reject what fails regex with clear inline message.

## Security Considerations
- All domain input normalized + validated before argv (defense in depth). No destructive action without confirm (§5.4). GUI never writes `/etc/webwarden`; only via CLI.

## Next Steps
Phase 09 packages app + Polkit so mutations actually authenticate.
