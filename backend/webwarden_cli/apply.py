"""Reconcile the running system with policy state (Linux runtime).

Order (fail-closed): regenerate + VALIDATE per-user dnsmasq configs, regenerate +
VALIDATE the nftables ruleset, load it, then reconcile per-user dnsmasq instances.
The ruleset is rebuilt with empty sets on every load (delete+recreate), so a full
apply also clears stale IPs after a ``disallow``; restarting already-active
instances makes dnsmasq drop its cache and repopulate the sets.

Nothing is loaded or (re)started until BOTH the dnsmasq configs and the ruleset
validate. The instance reconcile attempts every user and aggregates failures, so
one crash-looping instance can't silently leave the rest in a stale state.
"""
from . import dnsmasq_config, nftables_ruleset, paths, services


def apply(reason=""):
    specs = nftables_ruleset.build_specs()
    desired = {s["username"] for s in specs}

    # 1. regenerate + validate every per-user dnsmasq config (fail-closed)
    for s in specs:
        dnsmasq_config.write_user_dnsmasq(s["username"])
        ok, msg = dnsmasq_config.validate_conf(paths.dnsmasq_conf_path(s["username"]))
        if not ok:
            raise RuntimeError(
                "dnsmasq config for {} failed validation, aborting: {}".format(s["username"], msg))

    # 2. regenerate + validate ruleset BEFORE loading (fail-closed)
    path = paths.ruleset_file()
    nftables_ruleset.write_ruleset(specs)
    ok, msg = nftables_ruleset.validate_ruleset(path)
    if not ok:
        raise RuntimeError("nftables ruleset failed validation, aborting: " + msg)

    # 3. load ruleset (recreates table + empty sets)
    services.load_ruleset(path)

    # 4. reconcile dnsmasq instances; attempt all, aggregate failures
    current = services.list_active_instances()
    errors = []
    for name in sorted(desired):
        try:
            if name in current:
                services.restart_instance(name)        # repopulate after set rebuild
            else:
                services.enable_start_instance(name)    # newly locked
        except services.CommandError as e:
            errors.append(str(e))
    for name in sorted(current - desired):
        try:
            services.stop_disable_instance(name)        # newly unlocked
        except services.CommandError as e:
            errors.append(str(e))
    if errors:
        raise RuntimeError("some dnsmasq instances failed to reconcile: " + "; ".join(errors))
