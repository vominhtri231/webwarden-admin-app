# Phase 11 — Docs & Handoff

**Context:** all prior phases · SPEC §7.4, §7.5, §6 · `.claude/rules/documentation-management.md`.
**Priority:** High (deliverables §7.4/§7.5) · **Status:** pending · **Linux-only:** no.

## Overview
Finalize user + project documentation: an updated `README.md` (install, daily use, privilege model,
security limits, UNINSTALL) and the `docs/` set the project rules require. This is a shipped
deliverable, not an afterthought.

## Requirements (deliverables §7.4, §7.5)
- `README.md`: what it is; install (`install.sh` + apt deps); daily use of each screen; the Polkit
  privilege model; **inherited security limits** (locked user must be non-admin; physical/BIOS/live-USB
  bypass needs BIOS password + disk encryption; rare ECH sites need explicit allowlisting — §6/§5.4);
  and an **UNINSTALL** section pointing at `uninstall.sh`.
- `docs/`: `development-roadmap.md` (phases + status), `project-changelog.md` (features/fixes per build),
  `system-architecture.md` (the dnsmasq+nftables+systemd+Polkit+GUI design), `code-standards.md`
  (Python snake_case, <200 lines, try/except, argv arrays, validation boundary), `acceptance-checklist.md`
  (from Phase 10).

## Implementation Steps
1. Rewrite `README.md` per §7.4 (the scaffold README already covers most — fill install/daily-use/UNINSTALL gaps and reconcile any drift with the final code).
2. Write `docs/system-architecture.md` with a diagram (use `/mermaidjs-v11` skill) of the data/enforcement flow: GUI → pkexec → CLI → state → {dnsmasq instances, nftables, systemd} → logs → JSON → GUI.
3. Fill `development-roadmap.md` (this plan's phases + status) and `project-changelog.md`.
4. `code-standards.md`: capture conventions actually used (validation boundary, no-shell argv, atomic writes, module split).
5. Cross-check all docs against final code (no stale paths/commands).

## Todo
- [ ] README: install + daily use + privilege model + security limits + UNINSTALL
- [ ] `docs/system-architecture.md` (+ mermaid diagram)
- [ ] `docs/development-roadmap.md` + `project-changelog.md`
- [ ] `docs/code-standards.md`
- [ ] cross-reference / link check vs final code

## Success Criteria
A household admin can install, use, and uninstall from the README alone (spec §5.4 "understand every
screen without docs" — README is backup). All `docs/` files present, accurate, internally linked.

## Risk Assessment
- Docs drifting from code → write last, after Tier A green + Tier B runbook finalized; verify every command.

## Security Considerations
- README must clearly state the inherited limits so admins don't assume protection the model can't give
  (non-admin requirement, physical bypass, ECH). Misunderstanding these is itself a security risk.

## Next Steps
Run `/ck:journal` for a technical journal entry. Then begin implementation at Phase 01 via `/ck:cook`.
