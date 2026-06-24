"""Filesystem paths and constants for the webwarden backend.

Path roots are resolved through functions that honor environment overrides
(``WEBWARDEN_ETC`` / ``WEBWARDEN_LOG_DIR``) so unit tests can redirect all state
into a temp directory. Defaults are the Linux runtime locations.
"""
import os

# Path roots (overridable for tests) -----------------------------------------
DEFAULT_ETC = "/etc/webwarden"
DEFAULT_LOG_DIR = "/var/log/webwarden"          # mode 750, owner root:adm


def etc_root():
    return os.environ.get("WEBWARDEN_ETC", DEFAULT_ETC)


def log_dir():
    return os.environ.get("WEBWARDEN_LOG_DIR", DEFAULT_LOG_DIR)


# NOTE: these are Linux target paths that also get embedded verbatim into config
# files (e.g. dnsmasq log-facility). Always join with "/" so a Windows dev host
# never emits backslashes; forward-slash paths still work for local file I/O.
def users_dir():
    return etc_root() + "/users"                # users/<username>/{allowlist.txt,dnsmasq.conf}


def locked_file():
    return etc_root() + "/locked-users.txt"


def settings_file():
    return etc_root() + "/settings.json"          # app settings (log retention, ...)


def port_index_file():
    return etc_root() + "/ports.json"           # {"username": stable_index}


def ruleset_file():
    return etc_root() + "/nftables.ruleset"


def user_dir(username):
    return users_dir() + "/" + username


def allowlist_path(username):
    return user_dir(username) + "/allowlist.txt"


def dnsmasq_conf_path(username):
    return user_dir(username) + "/dnsmasq.conf"


def user_log_path(username):
    return log_dir() + "/" + username + ".log"


# nftables --------------------------------------------------------------------
NFT_TABLE_FAMILY = "inet"
NFT_TABLE = "kidfilter"


def set_names(username):
    """nftables IPv4 and IPv6 set names for a user."""
    return ("allow_v4_" + username, "allow_v6_" + username)


# dnsmasq port allocation -----------------------------------------------------
PORT_BASE = 5354                                # user port = PORT_BASE + stable_index


def user_port(index):
    return PORT_BASE + index


# User account selection ------------------------------------------------------
MIN_UID = 1000
MAX_UID = 65533                                 # excludes nobody (65534)

# Hardcoded tool paths: pkexec scrubs PATH, so never rely on a lookup ---------
NFT_BIN = "/usr/sbin/nft"
DNSMASQ_BIN = "/usr/sbin/dnsmasq"
SYSTEMCTL_BIN = "/usr/bin/systemctl"

# Default upstream resolvers for allowed domains ------------------------------
DEFAULT_UPSTREAMS = ("1.1.1.1", "8.8.8.8")
