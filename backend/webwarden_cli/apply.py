"""Reconcile the running system with policy state (Linux runtime).

Order (fail-closed): regenerate per-user dnsmasq configs, regenerate + VALIDATE
the nftables ruleset, load it, then reconcile per-user dnsmasq instances. The
ruleset is rebuilt with empty sets on every load (delete+recreate), so a full
apply also clears stale IPs after a ``disallow``; restarting already-active
instances makes dnsmasq drop its cache and repopulate the sets.

Never tears down protection on a validation failure.
"""
from . import dnsmasq_config, nftables_ruleset, paths, services


def apply(reason=""):
    specs = nftables_ruleset.build_specs()
    desired = {s["username"] for s in specs}

    # 1. regenerate per-user dnsmasq configs
    for s in specs:
        dnsmasq_config.write_user_dnsmasq(s["username"])

    # 2. regenerate + validate ruleset BEFORE loading (fail-closed)
    path = paths.ruleset_file()
    nftables_ruleset.write_ruleset(specs)
    ok, msg = nftables_ruleset.validate_ruleset(path)
    if not ok:
        raise RuntimeError("nftables ruleset failed validation, aborting: " + msg)

    # 3. load ruleset (recreates table + empty sets)
    services.load_ruleset(path)

    # 4. reconcile dnsmasq instances against the active set
    current = services.list_active_instances()
    for name in sorted(desired):
        if name in current:
            services.restart_instance(name)        # repopulate after set rebuild
        else:
            services.enable_start_instance(name)    # newly locked
    for name in sorted(current - desired):
        services.stop_disable_instance(name)        # newly unlocked
