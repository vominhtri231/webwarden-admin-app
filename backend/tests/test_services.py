"""Service-wrapper parsing tests (subprocess faked)."""
from webwarden_cli import services


class _Result:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def test_list_active_instances_parses_unit_names(monkeypatch):
    out = (
        "webwarden-dns@alice.service loaded active running webwarden ...\n"
        "webwarden-dns@bob.service   loaded active running webwarden ...\n"
    )
    monkeypatch.setattr(services.subprocess, "run", lambda *a, **k: _Result(stdout=out))
    assert services.list_active_instances() == {"alice", "bob"}


def test_list_active_instances_empty(monkeypatch):
    monkeypatch.setattr(services.subprocess, "run", lambda *a, **k: _Result(stdout=""))
    assert services.list_active_instances() == set()


def test_firewall_loaded(monkeypatch):
    monkeypatch.setattr(services.subprocess, "run", lambda *a, **k: _Result(returncode=0))
    assert services.firewall_loaded() is True
    monkeypatch.setattr(services.subprocess, "run", lambda *a, **k: _Result(returncode=1))
    assert services.firewall_loaded() is False


def test_run_raises_on_nonzero(monkeypatch):
    monkeypatch.setattr(services.subprocess, "run",
                        lambda *a, **k: _Result(stdout="boom", returncode=1))
    import pytest
    with pytest.raises(services.CommandError):
        services.systemctl("restart", "x")
