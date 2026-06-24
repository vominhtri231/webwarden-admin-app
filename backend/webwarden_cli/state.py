"""On-disk policy state: locked users, per-user allowlists, stable port index.

All paths derive from ``paths.etc_root()`` so tests can redirect via
``$WEBWARDEN_ETC``. Writes are atomic (temp file + os.replace); reads tolerate
missing files. Directories are created mode 0750.
"""
import json
import os

from . import paths


def _ensure_dir(path, mode=0o750):
    if path:
        os.makedirs(path, mode=mode, exist_ok=True)


def _atomic_write(path, content, mode=0o640):
    _ensure_dir(os.path.dirname(path))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.replace(tmp, path)
    try:
        os.chmod(path, mode)
    except OSError:
        pass  # chmod is a no-op / not permitted on some dev platforms


def _read_lines(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except FileNotFoundError:
        return []


# Locked users ---------------------------------------------------------------
def read_locked():
    return set(_read_lines(paths.locked_file()))


def is_locked(username):
    return username in read_locked()


def set_locked(username, locked):
    users = read_locked()
    if locked:
        users.add(username)
    else:
        users.discard(username)
    _atomic_write(paths.locked_file(), "".join(u + "\n" for u in sorted(users)))


# Allowlists -----------------------------------------------------------------
def read_allowlist(username):
    return sorted(set(_read_lines(paths.allowlist_path(username))))


def _write_allowlist(username, domains):
    _atomic_write(paths.allowlist_path(username),
                  "".join(d + "\n" for d in sorted(set(domains))))


def add_domains(username, domains):
    """Add domains; returns the list actually added (new, order-preserved)."""
    current = set(read_allowlist(username))
    added = []
    for d in domains:
        if d not in current and d not in added:
            added.append(d)
    if added:
        _write_allowlist(username, current.union(added))
    return added


def remove_domains(username, domains):
    """Remove domains; returns the list actually removed."""
    current = set(read_allowlist(username))
    removed = []
    for d in domains:
        if d in current and d not in removed:
            removed.append(d)
    if removed:
        _write_allowlist(username, current.difference(removed))
    return removed


# Stable port index ----------------------------------------------------------
def _read_ports():
    try:
        with open(paths.port_index_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _write_ports(mapping):
    _atomic_write(paths.port_index_file(),
                  json.dumps(mapping, indent=2, sort_keys=True) + "\n")


def get_index(username):
    return _read_ports().get(username)


def alloc_index(username):
    """Assign (and persist) the lowest free index for a user; idempotent."""
    mapping = _read_ports()
    if username in mapping:
        return mapping[username]
    used = set(mapping.values())
    idx = 0
    while idx in used:
        idx += 1
    mapping[username] = idx
    _write_ports(mapping)
    return idx


def free_index(username):
    mapping = _read_ports()
    if username in mapping:
        del mapping[username]
        _write_ports(mapping)


def get_port(username):
    idx = get_index(username)
    return paths.user_port(idx) if idx is not None else None
