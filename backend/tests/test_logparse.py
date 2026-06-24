"""Blocked-log parsing tests against captured-style dnsmasq log samples."""
from webwarden_cli import logparse

SAMPLE = (
    "Jun 24 22:10:01 dnsmasq[1234]: query[A] example.com from 127.0.0.1\n"
    "Jun 24 22:10:01 dnsmasq[1234]: config example.com is 0.0.0.0\n"
    "Jun 24 22:10:02 dnsmasq[1234]: query[AAAA] example.com from 127.0.0.1\n"
    "Jun 24 22:10:02 dnsmasq[1234]: config example.com is ::\n"
    "Jun 24 22:10:05 dnsmasq[1234]: query[A] wikipedia.org from 127.0.0.1\n"
    "Jun 24 22:10:05 dnsmasq[1234]: forwarded wikipedia.org to 1.1.1.1\n"
    "Jun 24 22:10:05 dnsmasq[1234]: reply wikipedia.org is 1.2.3.4\n"
    "Jun 24 22:11:00 dnsmasq[1234]: config ads.example.net is 0.0.0.0\n"
)


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_parse_blocked_classifies_and_orders(tmp_path):
    path = _write(tmp_path, "alice.log", SAMPLE)
    rows = logparse.parse_blocked(path, "alice", year=2026)
    assert [r["domain"] for r in rows] == ["ads.example.net", "example.com", "example.com"]
    assert rows[0]["time"] == "2026-06-24T22:11:00"
    assert all(r["user"] == "alice" for r in rows)
    assert "wikipedia.org" not in [r["domain"] for r in rows]   # allowed -> not a block


def test_since_filter(tmp_path):
    path = _write(tmp_path, "alice.log", SAMPLE)
    rows = logparse.parse_blocked(path, "alice", since="2026-06-24T22:10:30", year=2026)
    assert [r["domain"] for r in rows] == ["ads.example.net"]


def test_missing_file_is_empty():
    assert logparse.parse_blocked("/nope/missing.log", "x", year=2026) == []


def test_collect_blocked_across_users(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_LOG_DIR", str(tmp_path))
    _write(tmp_path, "alice.log", SAMPLE)
    _write(tmp_path, "bob.log",
           "Jun 24 23:00:00 dnsmasq[9]: config bad.example.org is 0.0.0.0\n")
    rows = logparse.collect_blocked(year=2026)
    assert rows[0] == {"time": "2026-06-24T23:00:00", "user": "bob", "domain": "bad.example.org"}
    assert {r["user"] for r in rows} == {"alice", "bob"}


def test_summarize_counts_and_last_seen():
    rows = [
        {"time": "2026-06-24T22:11:00", "user": "alice", "domain": "x.com"},
        {"time": "2026-06-24T22:10:00", "user": "alice", "domain": "x.com"},
        {"time": "2026-06-24T22:09:00", "user": "alice", "domain": "y.com"},
    ]
    by = {(r["user"], r["domain"]): r for r in logparse.summarize(rows)}
    assert by[("alice", "x.com")]["count"] == 2
    assert by[("alice", "x.com")]["last_seen"] == "2026-06-24T22:11:00"
    assert by[("alice", "y.com")]["count"] == 1
