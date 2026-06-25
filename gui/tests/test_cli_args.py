"""Pure argv-builder and UI-logic tests (no GTK)."""
import datetime

from webwarden_admin import cli_args as a


def test_read_args():
    assert a.status_args() == ["webwarden", "status", "--json"]
    assert a.users_args() == ["webwarden", "users", "--json"]
    assert a.list_args("alice") == ["webwarden", "list", "alice", "--json"]


def test_log_args_combinations():
    assert a.log_args() == ["webwarden", "log", "--json"]
    assert a.log_args(user="alice", since="2026-06-24T00:00:00", limit=50) == [
        "webwarden", "log", "--json", "--user", "alice",
        "--since", "2026-06-24T00:00:00", "--limit", "50"]
    assert a.log_args(summary=True) == ["webwarden", "log", "--json", "--summary"]
    assert a.log_args(summary=True, group=True) == [
        "webwarden", "log", "--json", "--summary", "--group"]
    assert a.log_args(group=True) == ["webwarden", "log", "--json"]   # group needs summary


def test_mutation_args():
    assert a.allow_args("alice", ["a.com", "b.com"]) == \
        ["webwarden", "allow", "alice", "a.com", "b.com"]
    assert a.disallow_args("alice", ["a.com"]) == ["webwarden", "disallow", "alice", "a.com"]
    assert a.lock_args("alice") == ["webwarden", "lock", "alice"]
    assert a.unlock_args("alice") == ["webwarden", "unlock", "alice"]


def test_settings_and_log_admin_args():
    assert a.settings_args() == ["webwarden", "settings", "--json"]
    assert a.set_retention_args(7) == ["webwarden", "settings", "--set-retention-days", "7"]
    assert a.log_clear_args() == ["webwarden", "log", "--clear"]
    assert a.log_prune_args() == ["webwarden", "log", "--prune"]
    assert a.log_prune_args(5) == ["webwarden", "log", "--prune", "--days", "5"]


def test_prepare_domain():
    assert a.prepare_domain("https://Example.com/x") == ("example.com", True)
    assert a.prepare_domain("nope zzz")[1] is False


def test_since_iso():
    now = datetime.datetime(2026, 6, 24, 22, 0, 0)
    assert a.since_iso(now, hours=24) == "2026-06-23T22:00:00"
    assert a.since_iso(now, days=7) == "2026-06-17T22:00:00"
