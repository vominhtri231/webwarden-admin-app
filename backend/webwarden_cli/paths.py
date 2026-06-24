"""Filesystem paths and constants for the webwarden backend.

Centralized so every module and test agrees on the on-disk layout. The /etc and
/var/log paths are Linux runtime locations; on a non-Linux dev machine they are
only ever used as strings (rendered into configs, never opened) by unit tests.
"""
import os

# Policy storage --------------------------------------------------------------
ETC = "/etc/webwarden"
USERS_DIR = os.path.join(ETC, "users")          # users/<username>/{allowlist.txt,dnsmasq.conf}
LOCKED_FILE = os.path.join(ETC, "locked-users.txt")
PORT_INDEX = os.path.join(ETC, "ports.json")    # {"username": stable_index}
RULESET_FILE = os.path.join(ETC, "nftables.ruleset")

# Logging ---------------------------------------------------------------------
LOG_DIR = "/var/log/webwarden"                  # mode 750, owner root:adm

# nftables --------------------------------------------------------------------
NFT_TABLE_FAMILY = "inet"
NFT_TABLE = "kidfilter"

# dnsmasq port allocation -----------------------------------------------------
PORT_BASE = 5354                                # user port = PORT_BASE + stable_index

# User account selection ------------------------------------------------------
MIN_UID = 1000
MAX_UID = 65533                                 # excludes nobody (65534)

# Hardcoded tool paths: pkexec scrubs PATH, so never rely on a lookup ---------
NFT_BIN = "/usr/sbin/nft"
DNSMASQ_BIN = "/usr/sbin/dnsmasq"
SYSTEMCTL_BIN = "/usr/bin/systemctl"

# Default upstream resolvers for allowed domains ------------------------------
DEFAULT_UPSTREAMS = ("1.1.1.1", "8.8.8.8")


def user_dir(username):
    return os.path.join(USERS_DIR, username)


def allowlist_path(username):
    return os.path.join(user_dir(username), "allowlist.txt")


def dnsmasq_conf_path(username):
    return os.path.join(user_dir(username), "dnsmasq.conf")


def user_log_path(username):
    return os.path.join(LOG_DIR, username + ".log")


def set_names(username):
    """nftables IPv4 and IPv6 set names for a user."""
    return ("allow_v4_" + username, "allow_v6_" + username)


def user_port(index):
    """Loopback port for a user's dnsmasq instance, given its stable index."""
    return PORT_BASE + index
