"""CLI dispatch tests: validation, idempotency, state effects, apply wiring."""
import json

import pytest

from webwarden_cli import apply as apply_module
from webwarden_cli import cli, state, users


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))
    monkeypatch.setattr(users, "user_exists", lambda u: True)
    monkeypatch.setattr(users, "has_sudo", lambda u: False)
    calls = []
    monkeypatch.setattr(apply_module, "apply", lambda reason="": calls.append(reason))
    return calls


def test_allow_normalizes_persists_and_applies(_env):
    rc = cli.main(["allow", "alice", "Example.com", "https://test.org/x"])
    assert rc == 0
    assert state.read_allowlist("alice") == ["example.com", "test.org"]
    assert _env == ["allow"]


def test_allow_rejects_invalid_domain_without_applying(_env):
    rc = cli.main(["allow", "alice", "not a domain"])
    assert rc != 0
    assert state.read_allowlist("alice") == []
    assert _env == []          # apply not called on validation failure


def test_allow_unknown_user(_env, monkeypatch):
    monkeypatch.setattr(users, "user_exists", lambda u: False)
    assert cli.main(["allow", "ghost", "example.com"]) != 0


def test_allow_users_adds_to_all_with_single_apply(_env):
    rc = cli.main(["allow-users", "Example.com", "alice", "bob"])
    assert rc == 0
    assert state.read_allowlist("alice") == ["example.com"]
    assert state.read_allowlist("bob") == ["example.com"]
    assert _env == ["allow-users"]          # one reconcile, not one per user


def test_allow_users_rejects_invalid_domain(_env):
    assert cli.main(["allow-users", "not a domain", "alice"]) != 0
    assert _env == []


def test_allow_users_unknown_user_no_partial(_env, monkeypatch):
    monkeypatch.setattr(users, "user_exists", lambda u: u == "alice")
    assert cli.main(["allow-users", "example.com", "alice", "ghost"]) != 0
    assert state.read_allowlist("alice") == []   # validated before any mutation
    assert _env == []


def test_lock_unlock_frees_port(_env):
    assert cli.main(["lock", "alice"]) == 0
    assert state.is_locked("alice")
    assert state.get_index("alice") == 0
    assert cli.main(["unlock", "alice"]) == 0
    assert not state.is_locked("alice")
    assert state.get_index("alice") is None
    assert _env == ["lock", "unlock"]


def test_lock_warns_on_sudo(_env, monkeypatch, capsys):
    monkeypatch.setattr(users, "has_sudo", lambda u: True)
    assert cli.main(["lock", "alice"]) == 0
    assert "deluser alice sudo" in capsys.readouterr().err


def test_list_json(_env):
    state.add_domains("alice", ["b.com", "a.com"])
    rc = cli.main(["list", "alice", "--json"])
    assert rc == 0


def test_list_json_output(_env, capsys):
    state.add_domains("alice", ["b.com", "a.com"])
    cli.main(["list", "alice", "--json"])
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == {"username": "alice", "domains": ["a.com", "b.com"]}


def test_settings_default_json(_env, capsys):
    cli.main(["settings", "--json"])
    data = json.loads(capsys.readouterr().out.strip())
    assert data["log_retention_days"] == 30


def test_settings_set_retention_persists(_env):
    from webwarden_cli import settings
    assert cli.main(["settings", "--set-retention-days", "7"]) == 0
    assert settings.get_retention_days() == 7


def test_log_clear_dispatches(_env, monkeypatch):
    from webwarden_cli import logparse
    calls = []
    monkeypatch.setattr(logparse, "clear_all", lambda: calls.append("clear") or 3)
    assert cli.main(["log", "--clear"]) == 0
    assert calls == ["clear"]


def test_log_prune_uses_days_override(_env, monkeypatch):
    from webwarden_cli import logparse
    seen = []
    monkeypatch.setattr(logparse, "prune_all",
                        lambda days, year=None, now=None: seen.append(days) or 0)
    assert cli.main(["log", "--prune", "--days", "5"]) == 0
    assert seen == [5]


def test_users_json_output(_env, monkeypatch, capsys):
    monkeypatch.setattr(users, "list_human_users", lambda: [("alice", 1000), ("bob", 1001)])
    state.set_locked("alice", True)
    cli.main(["users", "--json"])
    data = json.loads(capsys.readouterr().out.strip())
    assert data == [
        {"username": "alice", "uid": 1000, "locked": True},
        {"username": "bob", "uid": 1001, "locked": False},
    ]
