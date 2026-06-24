# System Architecture

> Living document. Expanded with a full data-flow diagram in Phase 11.

## Components
- **Backend CLI (`webwarden`, Python 3, `/usr/local/sbin/webwarden`)** — the only
  privileged component. Manages per-user allowlists, generates per-user dnsmasq
  configs and the `inet kidfilter` nftables ruleset, drives systemd, parses logs,
  and exposes a stable JSON contract.
- **Per-user dnsmasq instances** — one per locked user on loopback port `5354 + index`;
  resolve only allowlisted domains, answer everything else `0.0.0.0`/`::`, auto-populate
  per-user nftables IP sets, and log queries.
- **nftables `inet kidfilter`** — per-UID (`meta skuid`) default-deny egress; redirects each
  locked UID's DNS to its dnsmasq instance; permits tcp 80/443 only to that user's allow sets.
- **systemd** — `webwarden-dns@<user>.service` (templated) + `webwarden-nft.service` (oneshot)
  restore state at boot.
- **GTK4 GUI (`webwarden-admin`, unprivileged)** — drives the CLI via `pkexec` (Polkit);
  reads JSON, never writes `/etc/webwarden` directly.

## Trust boundary
Domain input is normalized + validated (`validation.py`) before being passed to the CLI as
argv arrays — never shell-interpolated. Mutations require admin auth via the shipped Polkit policy.

## Stable CLI contract
See `plans/260624-2214-webwarden-backend-gui-build/plan.md` (the GUI's API).
