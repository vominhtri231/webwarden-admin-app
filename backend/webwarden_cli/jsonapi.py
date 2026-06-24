"""JSON accessors that form the stable CLI contract (spec section 4.4).

``list_json`` and ``users_json`` are implemented here. ``status_json`` and the
log accessors are added in Phase 06 (they depend on services + log parsing).
"""
import json

from . import state, users


def list_json(username):
    return {"username": username, "domains": state.read_allowlist(username)}


def users_json():
    """All human users (uid >= 1000) with a locked flag."""
    locked = state.read_locked()
    return [
        {"username": name, "uid": uid, "locked": name in locked}
        for name, uid in users.list_human_users()
    ]


def dumps(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
