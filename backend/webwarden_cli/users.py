"""Human user account enumeration and admin-rights detection.

Uses the Linux-only ``pwd`` / ``grp`` modules, imported lazily so the module can
be imported (and the rest unit-tested) on non-Linux dev machines. Tests inject
fakes by setting ``users._pwd`` / ``users._grp``.
"""
from . import paths

# Groups that grant admin power on Ubuntu/Mint; membership defeats a lock.
ADMIN_GROUPS = ("sudo", "admin")

_pwd = None
_grp = None


def _pwd_mod():
    global _pwd
    if _pwd is None:
        import pwd
        _pwd = pwd
    return _pwd


def _grp_mod():
    global _grp
    if _grp is None:
        import grp
        _grp = grp
    return _grp


def list_human_users():
    """Return [(username, uid)] for real accounts, sorted by uid."""
    pwd = _pwd_mod()
    out = [(e.pw_name, e.pw_uid) for e in pwd.getpwall()
           if paths.MIN_UID <= e.pw_uid <= paths.MAX_UID]
    return sorted(out, key=lambda t: t[1])


def uid_of(username):
    pwd = _pwd_mod()
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        return None


def user_exists(username):
    return uid_of(username) is not None


def has_sudo(username):
    """True if the user belongs to an admin group (secondary or primary)."""
    grp = _grp_mod()
    for gname in ADMIN_GROUPS:
        try:
            if username in grp.getgrnam(gname).gr_mem:
                return True
        except KeyError:
            continue
    # Primary group could itself be an admin group.
    pwd = _pwd_mod()
    try:
        gid = pwd.getpwnam(username).pw_gid
    except KeyError:
        return False
    for gname in ADMIN_GROUPS:
        try:
            if grp.getgrnam(gname).gr_gid == gid:
                return True
        except KeyError:
            continue
    return False
