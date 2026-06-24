"""JSON accessors that form the stable CLI contract (spec section 4.4).

All five accessors live here so the GUI never parses raw files or human text.
"""
import json

from . import logparse, services, state, users


def list_json(username):
    return {"username": username, "domains": state.read_allowlist(username)}


def users_json():
    """All human users (uid >= 1000) with a locked flag."""
    locked = state.read_locked()
    return [
        {"username": name, "uid": uid, "locked": name in locked}
        for name, uid in users.list_human_users()
    ]


def status_json():
    """Firewall + per-user service state."""
    locked = state.read_locked()
    out = []
    for name, uid in users.list_human_users():
        is_locked = name in locked
        out.append({
            "username": name,
            "uid": uid,
            "locked": is_locked,
            "has_sudo": users.has_sudo(name),
            "allow_count": len(state.read_allowlist(name)),
            "dns_service_active": services.is_instance_active(name) if is_locked else False,
        })
    return {"users": out, "firewall_loaded": services.firewall_loaded()}


def log_json(user=None, since=None, limit=None, year=None):
    rows = logparse.collect_blocked(user=user, since=since, year=year)
    return rows[:limit] if limit is not None else rows


def log_summary_json(user=None, since=None, year=None):
    return logparse.summarize(logparse.collect_blocked(user=user, since=since, year=year))


def dumps(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
