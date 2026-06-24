# Development Roadmap

Living tracker for the webwarden build. Source plan:
`plans/260624-2214-webwarden-backend-gui-build/`.

## Phases

| # | Phase | Status |
|---|-------|--------|
| 01 | Foundations & conventions | Complete |
| 02 | Backend CLI core & state model | Complete |
| 03 | dnsmasq per-user config generation | Complete |
| 04 | nftables ruleset generation | Complete |
| 05 | Apply orchestration & systemd units | Complete |
| 06 | Logging & JSON API | Complete |
| 07 | GUI shell & async CLI client | Complete |
| 08 | GUI views (users/allowlist/log/status) | Complete |
| 09 | Packaging: Polkit, .desktop, install/uninstall | Complete |
| 10 | Testing & acceptance | Tier A complete; Tier B (Mint acceptance) pending on-target run |
| 11 | Docs & handoff | Complete |

## Remaining
- Run the Linux Mint acceptance suite (`docs/acceptance-checklist.md`), starting with
  the two early-verify items (dnsmasq blocked-log format, `meta skuid` redirect).

## Milestones
- **Backend complete:** phases 02–06 (CLI contract usable).
- **GUI complete:** phases 07–08 (against the CLI JSON contract).
- **Shippable:** phases 09–11 (installable + documented + accepted on Mint).

## Notes
- Developed on Windows; kernel/service/GTK behavior validated on Linux Mint (see Phase 10 acceptance runbook).
