"""Pure helpers for building webwarden CLI argv and small UI-logic bits.

No GTK imports here, so this is unit-testable on any platform. cli_client wraps
mutation argv in ``pkexec``. Domains are validated before they ever reach argv.
"""
import datetime

from . import validation

WEBWARDEN = "webwarden"   # on PATH (installed to /usr/local/sbin/webwarden)


def status_args():
    return [WEBWARDEN, "status", "--json"]


def users_args():
    return [WEBWARDEN, "users", "--json"]


def list_args(username):
    return [WEBWARDEN, "list", username, "--json"]


def log_args(user=None, since=None, limit=None, summary=False):
    args = [WEBWARDEN, "log", "--json"]
    if summary:
        args.append("--summary")
    if user:
        args += ["--user", user]
    if since:
        args += ["--since", since]
    if limit is not None:
        args += ["--limit", str(limit)]
    return args


def settings_args():
    return [WEBWARDEN, "settings", "--json"]


def set_retention_args(days):
    return [WEBWARDEN, "settings", "--set-retention-days", str(int(days))]


def log_clear_args():
    return [WEBWARDEN, "log", "--clear"]


def log_prune_args(days=None):
    args = [WEBWARDEN, "log", "--prune"]
    if days is not None:
        args += ["--days", str(int(days))]
    return args


def allow_args(username, domains):
    return [WEBWARDEN, "allow", username, *domains]


def disallow_args(username, domains):
    return [WEBWARDEN, "disallow", username, *domains]


def lock_args(username):
    return [WEBWARDEN, "lock", username]


def unlock_args(username):
    return [WEBWARDEN, "unlock", username]


def prepare_domain(raw):
    """Normalize + validate a single domain. Returns (normalized, ok)."""
    return validation.normalize_and_validate(raw)


def since_iso(now, days=None, hours=None):
    """ISO8601 'since' for quick filters, computed from a datetime ``now``."""
    delta = datetime.timedelta(days=days or 0, hours=hours or 0)
    return (now - delta).strftime("%Y-%m-%dT%H:%M:%S")
