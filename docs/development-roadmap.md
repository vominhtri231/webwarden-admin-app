# Development Roadmap

Living tracker for the webwarden build. Source plan:
`plans/260624-2214-webwarden-backend-gui-build/`.

## Phases

| # | Phase | Status |
|---|-------|--------|
| 01 | Foundations & conventions | In progress |
| 02 | Backend CLI core & state model | Pending |
| 03 | dnsmasq per-user config generation | Pending |
| 04 | nftables ruleset generation | Pending |
| 05 | Apply orchestration & systemd units | Pending |
| 06 | Logging & JSON API | Pending |
| 07 | GUI shell & async CLI client | Pending |
| 08 | GUI views (users/allowlist/log/status) | Pending |
| 09 | Packaging: Polkit, .desktop, install/uninstall | Pending |
| 10 | Testing & acceptance | Pending |
| 11 | Docs & handoff | Pending |

## Milestones
- **Backend complete:** phases 02–06 (CLI contract usable).
- **GUI complete:** phases 07–08 (against the CLI JSON contract).
- **Shippable:** phases 09–11 (installable + documented + accepted on Mint).

## Notes
- Developed on Windows; kernel/service/GTK behavior validated on Linux Mint (see Phase 10 acceptance runbook).
