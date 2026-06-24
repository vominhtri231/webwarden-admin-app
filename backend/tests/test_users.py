"""User enumeration / admin-detection tests with injected pwd/grp fakes."""
from webwarden_cli import users


class _Pw:
    def __init__(self, name, uid, gid=1000):
        self.pw_name, self.pw_uid, self.pw_gid = name, uid, gid


class _FakePwd:
    def __init__(self, entries):
        self._e = entries

    def getpwall(self):
        return self._e

    def getpwnam(self, name):
        for e in self._e:
            if e.pw_name == name:
                return e
        raise KeyError(name)


class _Gr:
    def __init__(self, name, gid, mem):
        self.gr_name, self.gr_gid, self.gr_mem = name, gid, mem


class _FakeGrp:
    def __init__(self, groups):
        self._g = groups

    def getgrnam(self, name):
        for g in self._g:
            if g.gr_name == name:
                return g
        raise KeyError(name)


def _install(monkeypatch, pw, gr):
    monkeypatch.setattr(users, "_pwd", _FakePwd(pw))
    monkeypatch.setattr(users, "_grp", _FakeGrp(gr))


def test_list_human_users_filters_system_accounts(monkeypatch):
    pw = [_Pw("root", 0), _Pw("bob", 1001), _Pw("alice", 1000), _Pw("nobody", 65534)]
    _install(monkeypatch, pw, [])
    assert users.list_human_users() == [("alice", 1000), ("bob", 1001)]


def test_has_sudo_secondary_group(monkeypatch):
    pw = [_Pw("alice", 1000, gid=1000)]
    gr = [_Gr("sudo", 27, ["alice"]), _Gr("users", 1000, [])]
    _install(monkeypatch, pw, gr)
    assert users.has_sudo("alice") is True
    assert users.has_sudo("bob") is False


def test_has_sudo_primary_group(monkeypatch):
    pw = [_Pw("carol", 1002, gid=27)]
    gr = [_Gr("sudo", 27, [])]
    _install(monkeypatch, pw, gr)
    assert users.has_sudo("carol") is True


def test_uid_and_exists(monkeypatch):
    _install(monkeypatch, [_Pw("alice", 1000)], [])
    assert users.uid_of("alice") == 1000
    assert users.user_exists("alice") is True
    assert users.uid_of("ghost") is None
    assert users.user_exists("ghost") is False
