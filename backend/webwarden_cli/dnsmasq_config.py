"""Generate a per-user dnsmasq instance config (allowlist resolver + logger).

Each locked user gets an isolated dnsmasq instance that:
  * listens only on 127.0.0.1:<port>,
  * forwards ALLOWED domains to upstream resolvers and records their resolved
    IPs into that user's nftables sets (so the firewall can permit them),
  * answers EVERYTHING ELSE with 0.0.0.0 / :: (the default-deny catch-all),
  * logs every query so blocked attempts can be reported.

This module only renders text + writes files; it never runs dnsmasq.

LINUX-VERIFY (plan Phase 03 / Phase 10): the ``address=/#/`` catch-all vs
per-domain ``server=`` precedence, and the exact ``nftset=`` family routing,
must be confirmed against the target's dnsmasq (2.90 on Ubuntu 24.04). Both are
isolated below so a fix is a one-line change.
"""
import subprocess
import sys

from . import paths, state

_HEADER = "# Managed by webwarden for user {user}. Do not edit by hand."


def _nftset_line(domain, username):
    """One directive listing both sets; dnsmasq routes A->v4 set, AAAA->v6 set."""
    v4, v6 = paths.set_names(username)
    fam, table = paths.NFT_TABLE_FAMILY, paths.NFT_TABLE
    return "nftset=/{d}/{f}#{t}#{v4},{f}#{t}#{v6}".format(
        d=domain, f=fam, t=table, v4=v4, v6=v6)


def render_dnsmasq_conf(username, port, allowlist, upstreams=paths.DEFAULT_UPSTREAMS):
    lines = [
        _HEADER.format(user=username),
        "port={}".format(port),
        "listen-address=127.0.0.1",
        "bind-interfaces",
        "no-resolv",
        "log-queries",
        "log-facility={}".format(paths.user_log_path(username)),
        "min-cache-ttl=60",
        "",
        "# Default-deny: anything not explicitly allowed resolves to 0.0.0.0 / ::",
        "address=/#/0.0.0.0",
        "address=/#/::",
    ]
    if allowlist:
        lines += ["", "# Allowed domains (forward upstream + populate nft sets)"]
        for d in sorted(set(allowlist)):
            for up in upstreams:
                lines.append("server=/{d}/{up}".format(d=d, up=up))
            lines.append(_nftset_line(d, username))
    return "\n".join(lines) + "\n"


def write_user_dnsmasq(username, upstreams=paths.DEFAULT_UPSTREAMS):
    """Render and atomically write a user's dnsmasq.conf. Returns the text."""
    port = state.get_port(username)
    if port is None:
        raise ValueError("user {} has no allocated port (not locked?)".format(username))
    conf = render_dnsmasq_conf(username, port, state.read_allowlist(username), upstreams)
    state.atomic_write(paths.dnsmasq_conf_path(username), conf, mode=0o644)
    return conf


def validate_conf(path):
    """Run `dnsmasq --test` on a config (Linux only). Returns (ok, message)."""
    if not sys.platform.startswith("linux"):
        return True, "skipped (non-Linux dev host)"
    try:
        r = subprocess.run([paths.DNSMASQ_BIN, "--test", "--conf-file=" + path],
                           capture_output=True, text=True)
        return r.returncode == 0, (r.stderr or r.stdout).strip()
    except OSError as e:
        return False, str(e)
