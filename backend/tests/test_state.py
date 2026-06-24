"""State layer tests: allowlists, locked set, stable port index."""
import pytest

from webwarden_cli import state


@pytest.fixture(autouse=True)
def _etc(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))


def test_allowlist_roundtrip_and_idempotency():
    assert state.read_allowlist("alice") == []
    assert state.add_domains("alice", ["b.com", "a.com", "a.com"]) == ["b.com", "a.com"]
    assert state.read_allowlist("alice") == ["a.com", "b.com"]
    assert state.add_domains("alice", ["a.com"]) == []          # idempotent
    assert state.remove_domains("alice", ["a.com", "a.com"]) == ["a.com"]
    assert state.read_allowlist("alice") == ["b.com"]
    assert state.remove_domains("alice", ["missing.com"]) == []  # idempotent


def test_locked_set_idempotent():
    assert state.read_locked() == set()
    state.set_locked("alice", True)
    state.set_locked("alice", True)
    assert state.is_locked("alice")
    assert state.read_locked() == {"alice"}
    state.set_locked("alice", False)
    assert not state.is_locked("alice")


def test_port_index_stable_across_unlock_relock():
    assert state.alloc_index("alice") == 0
    assert state.alloc_index("bob") == 1
    assert state.alloc_index("alice") == 0      # idempotent
    assert state.get_port("alice") == 5354
    state.free_index("alice")                    # alice unlocked
    assert state.get_index("bob") == 1           # bob unaffected
    assert state.get_index("alice") is None
    assert state.alloc_index("alice") == 0       # lowest free reused on relock
