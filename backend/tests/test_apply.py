"""apply() reconcile-logic tests with a fully faked services layer."""
import pytest

from webwarden_cli import apply, dnsmasq_config, nftables_ruleset, services, state, users


def test_apply_reconciles_start_restart_stop(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))
    state.set_locked("alice", True); state.alloc_index("alice")
    state.set_locked("bob", True); state.alloc_index("bob")
    monkeypatch.setattr(users, "uid_of", lambda n: {"alice": 1000, "bob": 1001}.get(n))

    written = []
    monkeypatch.setattr(dnsmasq_config, "write_user_dnsmasq", lambda u: written.append(u))
    monkeypatch.setattr(dnsmasq_config, "validate_conf", lambda p: (True, "ok"))
    monkeypatch.setattr(nftables_ruleset, "write_ruleset", lambda specs=None: "RULESET")
    monkeypatch.setattr(nftables_ruleset, "validate_ruleset", lambda p: (True, "ok"))

    events = []
    monkeypatch.setattr(services, "load_ruleset", lambda p: events.append(("load", p)))
    monkeypatch.setattr(services, "list_active_instances", lambda: {"bob", "carol"})
    monkeypatch.setattr(services, "enable_start_instance", lambda u: events.append(("start", u)))
    monkeypatch.setattr(services, "restart_instance", lambda u: events.append(("restart", u)))
    monkeypatch.setattr(services, "stop_disable_instance", lambda u: events.append(("stop", u)))

    apply.apply("test")

    assert set(written) == {"alice", "bob"}
    assert events[0][0] == "load"                  # ruleset loaded before reconcile
    assert ("start", "alice") in events           # newly locked
    assert ("restart", "bob") in events           # already active -> repopulate
    assert ("stop", "carol") in events            # newly unlocked


def test_apply_aborts_fail_closed_on_invalid_ruleset(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))
    monkeypatch.setattr(nftables_ruleset, "build_specs", lambda: [])
    monkeypatch.setattr(nftables_ruleset, "write_ruleset", lambda specs=None: "X")
    monkeypatch.setattr(nftables_ruleset, "validate_ruleset", lambda p: (False, "bad rule"))
    loaded = []
    monkeypatch.setattr(services, "load_ruleset", lambda p: loaded.append(p))

    with pytest.raises(RuntimeError):
        apply.apply()
    assert loaded == []        # never loaded a failing ruleset


def test_apply_aborts_on_invalid_dnsmasq_conf(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))
    state.set_locked("alice", True); state.alloc_index("alice")
    monkeypatch.setattr(users, "uid_of", lambda n: 1000)
    monkeypatch.setattr(dnsmasq_config, "write_user_dnsmasq", lambda u: None)
    monkeypatch.setattr(dnsmasq_config, "validate_conf", lambda p: (False, "bad conf"))
    loaded = []
    monkeypatch.setattr(services, "load_ruleset", lambda p: loaded.append(p))

    with pytest.raises(RuntimeError):
        apply.apply()
    assert loaded == []        # dnsmasq config validated before anything is loaded


def test_apply_aggregates_instance_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))
    state.set_locked("alice", True); state.alloc_index("alice")
    state.set_locked("bob", True); state.alloc_index("bob")
    monkeypatch.setattr(users, "uid_of", lambda n: {"alice": 1000, "bob": 1001}.get(n))
    monkeypatch.setattr(dnsmasq_config, "write_user_dnsmasq", lambda u: None)
    monkeypatch.setattr(dnsmasq_config, "validate_conf", lambda p: (True, "ok"))
    monkeypatch.setattr(nftables_ruleset, "write_ruleset", lambda specs=None: "X")
    monkeypatch.setattr(nftables_ruleset, "validate_ruleset", lambda p: (True, "ok"))
    monkeypatch.setattr(services, "load_ruleset", lambda p: None)
    monkeypatch.setattr(services, "list_active_instances", lambda: set())

    started = []

    def flaky_start(u):
        started.append(u)
        if u == "alice":
            raise services.CommandError("alice boom")

    monkeypatch.setattr(services, "enable_start_instance", flaky_start)

    with pytest.raises(RuntimeError) as exc:
        apply.apply()
    assert set(started) == {"alice", "bob"}     # bob still attempted after alice failed
    assert "alice boom" in str(exc.value)
