# Phase 07 — GUI Shell & Async CLI Client

**Context:** `plan.md` (CLI contract) · SPEC §5 · gtk4-pygobject report.
**Priority:** Critical (GUI foundation) · **Status:** pending · **Linux-only:** running = YES; cli-client logic + arg-building = no (unit-test on Windows without GTK import).

## Overview
Build the GTK4 application shell and the **async pkexec CLI client** that every view uses. The
client never blocks the UI thread and is the only place that shells out. Keep GTK widgets out of
the testable logic (arg-building, JSON parsing) so it runs under pytest on Windows.

## Key Insights (from research)
- Plain `Gtk.Application` + `Gtk.ApplicationWindow` (skip libadwaita — Cinnamon theming). `activate` builds the window with a view switcher (`Gtk.Stack` + `Gtk.StackSwitcher`).
- **Async subprocess = `Gio.Subprocess` + `communicate_utf8_async()` + callback** (GTK-native, stable). pkexec's password dialog blocks inside polkit, not your loop; callback fires after auth. Guard overlapping calls per command with a busy flag.
- Read JSON from stdout; on non-zero exit, surface stderr via toast/alert. Backend-missing (`pkexec`/`webwarden` not found) → graceful "backend not installed — run install.sh" screen (spec §5.4).
- Separate **pure** `cli_args.py` (builds argv lists, validates) from `cli_client.py` (does the Gio call) so the former is unit-testable without GTK.

## Requirements
- Functional: `CliClient.run_json(args, on_done, on_error)` (read commands) and `run_mutation(args, on_done, on_error)` (prefixes `pkexec`); JSON parse; error routing. Detect backend presence on startup.
- Non-functional: UI never freezes; one in-flight guard per logical action; all argv as arrays (no shell).

## Architecture
```
views ──▶ CliClient
  run_json(["webwarden","status","--json"], cb)         # read (direct or pkexec per §5.2)
  run_mutation(["webwarden","allow",u,d], cb)           # pkexec webwarden allow u d
        └─ Gio.Subprocess(argv, STDOUT|STDERR) .communicate_utf8_async(cb)
              └─ on exit 0: json.loads(stdout) → on_done ; else → on_error(stderr)
cli_args.py (pure): build_allow_args(u, domains)->argv, validate via validation.py
```

## Related Code Files
- Create `app.py`, `window.py`, `cli_client.py`, `cli_args.py`, `widgets/toast.py`, `widgets/confirm.py`, `__main__.py`. Reuse `validation.py` (Phase 01 copy).

## Implementation Steps
1. `app.py`/`window.py`: Application, window, `Gtk.Stack` with 4 named pages (placeholders now), header bar, load `webwarden-admin.css`.
2. `cli_args.py`: pure builders for every contract command (validate domains/usernames, return argv list). Unit-test on Windows.
3. `cli_client.py`: `Gio.Subprocess` async wrappers; JSON parse; error callback with stderr; backend-presence check (`shutil.which`/probe).
4. `widgets/toast.py`: revealer/infobar toast (no Adw); `widgets/confirm.py`: `Gtk.AlertDialog` confirm helper (spec §5.4).
5. Graceful-degrade screen when backend missing; disable mutating UI.

## Todo
- [ ] App + window + Stack/switcher + CSS load
- [ ] `cli_args.py` pure argv builders (+ unit tests on Windows)
- [ ] `cli_client.py` async run_json/run_mutation + JSON parse + error routing
- [ ] toast + confirm-dialog helpers
- [ ] backend-missing graceful degradation
- [ ] in-flight guard

## Success Criteria
On Linux: app launches, switches between (empty) views, a probe call (`status --json`) renders or shows backend-missing message; password dialog appears only on mutations. On Windows: `cli_args` + JSON-parse unit tests pass; `py_compile` clean.

## Risk Assessment
- Importing GTK in a module that tests import → keep GTK strictly in app/window/views/widgets; logic modules import only stdlib. 
- Overlapping async calls → busy flag per action; disable button while in-flight.

## Security Considerations
- Only place that executes commands; always argv arrays, never string concat. Validate every domain/username via `validation.py` before building argv (defense in depth — backend also validates).

## Next Steps
Phase 08 fills the four views using this client.
