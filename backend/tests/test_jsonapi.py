"""JSON contract tests (spec 4.4 shapes)."""
from webwarden_cli import jsonapi, services, state, users


def test_status_json_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))
    monkeypatch.setattr(users, "list_human_users", lambda: [("alice", 1000), ("bob", 1001)])
    monkeypatch.setattr(users, "has_sudo", lambda u: u == "bob")
    monkeypatch.setattr(services, "is_instance_active", lambda u: True)
    monkeypatch.setattr(services, "firewall_loaded", lambda: True)
    state.set_locked("alice", True)
    state.add_domains("alice", ["a.com", "b.com"])

    data = jsonapi.status_json()
    assert data["firewall_loaded"] is True
    alice = next(u for u in data["users"] if u["username"] == "alice")
    assert alice == {"username": "alice", "uid": 1000, "locked": True,
                     "has_sudo": False, "allow_count": 2, "dns_service_active": True}
    bob = next(u for u in data["users"] if u["username"] == "bob")
    assert bob["locked"] is False
    assert bob["has_sudo"] is True
    assert bob["dns_service_active"] is False        # not locked -> not checked


def test_log_json_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_LOG_DIR", str(tmp_path))
    (tmp_path / "alice.log").write_text(
        "Jun 24 22:10:01 dnsmasq[1]: config a.com is 0.0.0.0\n"
        "Jun 24 22:10:02 dnsmasq[1]: config b.com is 0.0.0.0\n"
        "Jun 24 22:10:03 dnsmasq[1]: config c.com is 0.0.0.0\n", encoding="utf-8")
    rows = jsonapi.log_json(year=2026, limit=2)
    assert [r["domain"] for r in rows] == ["c.com", "b.com"]   # newest first, limited
