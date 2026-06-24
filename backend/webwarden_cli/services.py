"""Thin wrappers around systemctl and nft (argv arrays, captured output).

Side-effecting and Linux-only. apply.py composes these; unit tests fake this
whole module so the reconcile logic is testable off-Linux.
"""
import subprocess

from . import paths

DNS_UNIT = "webwarden-dns@{}.service"
NFT_UNIT = "webwarden-nft.service"
_DNS_PREFIX = "webwarden-dns@"
_DNS_SUFFIX = ".service"


class CommandError(RuntimeError):
    pass


def _run(argv):
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode != 0:
        raise CommandError("{}: {}".format(" ".join(argv),
                                           (r.stderr or r.stdout).strip()))
    return r.stdout


def systemctl(*args):
    return _run([paths.SYSTEMCTL_BIN, *args])


def load_ruleset(path):
    _run([paths.NFT_BIN, "-f", path])


def flush_sets(commands):
    for argv in commands:
        _run(argv)


def enable_start_instance(username):
    systemctl("enable", "--now", DNS_UNIT.format(username))


def stop_disable_instance(username):
    systemctl("disable", "--now", DNS_UNIT.format(username))


def restart_instance(username):
    systemctl("restart", DNS_UNIT.format(username))


def list_active_instances():
    """Usernames with an active webwarden-dns@ instance."""
    out = subprocess.run(
        [paths.SYSTEMCTL_BIN, "list-units", "--type=service", "--state=active",
         "--no-legend", "--plain", _DNS_PREFIX + "*" + _DNS_SUFFIX],
        capture_output=True, text=True).stdout
    names = set()
    for line in out.splitlines():
        parts = line.split()
        unit = parts[0] if parts else ""
        if unit.startswith(_DNS_PREFIX) and unit.endswith(_DNS_SUFFIX):
            names.add(unit[len(_DNS_PREFIX):-len(_DNS_SUFFIX)])
    return names


def is_instance_active(username):
    r = subprocess.run([paths.SYSTEMCTL_BIN, "is-active", "--quiet",
                        DNS_UNIT.format(username)])
    return r.returncode == 0


def firewall_loaded():
    r = subprocess.run(
        [paths.NFT_BIN, "list", "table", paths.NFT_TABLE_FAMILY, paths.NFT_TABLE],
        capture_output=True, text=True)
    return r.returncode == 0
