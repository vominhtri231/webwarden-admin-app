"""Persistent app settings (currently just blocked-log retention).

Stored as JSON at ``/etc/webwarden/settings.json``. Reads tolerate a missing or
malformed file by returning defaults. ``log_retention_days`` is how many days of
blocked log to keep; ``0`` disables auto-pruning (keep forever). Paths derive
from ``paths.etc_root()`` so tests can redirect via ``$WEBWARDEN_ETC``.
"""
import json

from . import paths, state

DEFAULT_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 365


def read_settings():
    try:
        with open(paths.settings_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError):
        data = None
    if not isinstance(data, dict):
        data = {}
    data.setdefault("log_retention_days", DEFAULT_RETENTION_DAYS)
    return data


def _clamp_days(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS
    return max(0, min(MAX_RETENTION_DAYS, n))


def get_retention_days():
    return _clamp_days(read_settings().get("log_retention_days"))


def set_retention_days(value):
    """Persist retention (clamped to 0..365). Returns the stored value."""
    days = _clamp_days(value)
    data = read_settings()
    data["log_retention_days"] = days
    state.atomic_write(paths.settings_file(),
                       json.dumps(data, indent=2, sort_keys=True) + "\n")
    return days
