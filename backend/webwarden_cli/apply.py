"""Reconcile the running system with policy state.

The real orchestration (regenerate dnsmasq configs + nftables ruleset, drive
systemd, flush IP sets) lands in Phase 05. Until then this raises so callers
fail loudly rather than silently leaving policy unenforced.
"""


def apply(reason=""):
    raise NotImplementedError(
        "apply() is implemented in Phase 05 (systemd / nftables orchestration)"
    )
