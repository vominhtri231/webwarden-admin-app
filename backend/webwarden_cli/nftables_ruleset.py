"""Generate the `inet kidfilter` nftables ruleset (the enforcement boundary).

For each locked user (keyed on ``meta skuid <uid>``):
  * redirect that UID's DNS (udp/tcp 53 + 853) to its own dnsmasq port,
  * allow loopback egress (the redirected DNS + harmless local sockets),
  * allow tcp 80/443 only to that user's allow_v4 / allow_v6 sets,
  * reject everything else for that UID.
Non-locked users (including the admin) match no rule and pass via policy accept.

Text generation only; never runs nft.

LINUX-VERIFY (plan Phase 04 / Phase 10): that ``meta skuid`` works in the nat
``output`` redirect and that IPv6 matching works in the ``inet`` table. Both are
isolated below; if redirect-in-output misbehaves, split into ip/ip6 tables.
"""
import subprocess
import sys

from . import paths, state, users


def render_ruleset(specs):
    """Render the full ruleset. ``specs`` = [{'username','uid','port'}]."""
    specs = sorted(specs, key=lambda s: s["uid"])
    lines = [
        "#!/usr/sbin/nft -f",
        "# Managed by webwarden. Do not edit by hand.",
        "",
        "# Idempotent reload: ensure-exists, delete, recreate.",
        "table inet kidfilter",
        "delete table inet kidfilter",
        "",
        "table inet kidfilter {",
    ]
    for s in specs:
        v4, v6 = paths.set_names(s["username"])
        lines.append("    set {} {{ type ipv4_addr; }}".format(v4))
        lines.append("    set {} {{ type ipv6_addr; }}".format(v6))
    if specs:
        lines.append("")

    lines.append("    chain dnsredirect {")
    lines.append("        type nat hook output priority -100; policy accept;")
    for s in specs:
        uid, port = s["uid"], s["port"]
        lines.append("        meta skuid {} udp dport {{ 53, 853 }} redirect to :{}".format(uid, port))
        lines.append("        meta skuid {} tcp dport {{ 53, 853 }} redirect to :{}".format(uid, port))
    lines.append("    }")
    lines.append("")

    lines.append("    chain egress {")
    lines.append("        type filter hook output priority 0; policy accept;")
    for s in specs:
        uid = s["uid"]
        v4, v6 = paths.set_names(s["username"])
        lines.append("        # {} (uid {})".format(s["username"], uid))
        lines.append("        meta skuid {} ip daddr 127.0.0.0/8 accept".format(uid))
        lines.append("        meta skuid {} ip6 daddr ::1 accept".format(uid))
        lines.append("        meta skuid {} tcp dport {{ 80, 443 }} ip daddr @{} accept".format(uid, v4))
        lines.append("        meta skuid {} tcp dport {{ 80, 443 }} ip6 daddr @{} accept".format(uid, v6))
        lines.append("        meta skuid {} reject with icmpx type admin-prohibited".format(uid))
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def build_specs():
    """Specs for every locked user we can resolve (uid + port), sorted by uid."""
    specs = []
    for name in sorted(state.read_locked()):
        uid = users.uid_of(name)
        port = state.get_port(name)
        if uid is None or port is None:
            continue
        specs.append({"username": name, "uid": uid, "port": port})
    return specs


def write_ruleset(specs=None):
    if specs is None:
        specs = build_specs()
    text = render_ruleset(specs)
    state.atomic_write(paths.ruleset_file(), text, mode=0o600)
    return text


def flush_set_commands(username):
    """argv lists that empty a user's sets (used on disallow). Executed by services."""
    v4, v6 = paths.set_names(username)
    fam, table = paths.NFT_TABLE_FAMILY, paths.NFT_TABLE
    return [
        [paths.NFT_BIN, "flush", "set", fam, table, v4],
        [paths.NFT_BIN, "flush", "set", fam, table, v6],
    ]


def validate_ruleset(path):
    """Run `nft -c -f` (check-only) on a ruleset file (Linux only)."""
    if not sys.platform.startswith("linux"):
        return True, "skipped (non-Linux dev host)"
    try:
        r = subprocess.run([paths.NFT_BIN, "-c", "-f", path], capture_output=True, text=True)
        return r.returncode == 0, (r.stderr or r.stdout).strip()
    except OSError as e:
        return False, str(e)
