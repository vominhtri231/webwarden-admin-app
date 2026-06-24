# System Architecture

## Data / enforcement flow

```mermaid
flowchart LR
    GUI["GTK4 GUI<br/>(unprivileged)"] -->|pkexec + argv| CLI["webwarden CLI<br/>(root)"]
    CLI --> STATE["/etc/webwarden<br/>locked-users, allowlists, ports"]
    CLI -->|apply| DNS["per-user dnsmasq<br/>127.0.0.1:5354+N"]
    CLI -->|apply| NFT["nftables<br/>inet kidfilter"]
    DNS -->|nftset=| NFT
    DNS -->|log-queries| LOG["/var/log/webwarden/&lt;user&gt;.log"]
    NFT -->|meta skuid: redirect DNS,<br/>allow 80/443 to sets, reject rest| KERN["locked user's traffic"]
    LOG -->|log --json| CLI
    CLI -->|status/list/users/log JSON| GUI
```

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
- **Log retention** — `settings.log_retention_days` (in `/etc/webwarden/settings.json`) bounds
  blocked-log growth. Old entries are pruned at the end of every `apply`, by a daily
  `webwarden-logprune.timer`, and on demand; `webwarden log --clear` truncates all user logs.
  Pruning rewrites each file in place (preserving inode/owner, like logrotate `copytruncate`).

## Trust boundary
Domain input is normalized + validated (`validation.py`) before being passed to the CLI as
argv arrays — never shell-interpolated. Mutations require admin auth via the shipped Polkit policy.

## Stable CLI contract
See `plans/260624-2214-webwarden-backend-gui-build/plan.md` (the GUI's API). Additive commands:
`webwarden settings [--json | --set-retention-days N]` and `webwarden log [--prune [--days N] | --clear]`.
