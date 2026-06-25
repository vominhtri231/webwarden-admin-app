"""Blocked-log parsing tests against captured-style dnsmasq log samples."""
import datetime

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


TWODAY = (
    "Jun 20 10:00:00 dnsmasq[1]: config old.example.com is 0.0.0.0\n"
    "Jun 24 22:11:00 dnsmasq[1]: config new.example.com is 0.0.0.0\n"
)


def test_prune_all_drops_old_keeps_recent(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_LOG_DIR", str(tmp_path))
    _write(tmp_path, "alice.log", TWODAY)
    removed = logparse.prune_all(2, year=2026, now=datetime.datetime(2026, 6, 24, 22, 30, 0))
    assert removed == 1                       # cutoff Jun 22: Jun 20 dropped, Jun 24 kept
    rows = logparse.collect_blocked(year=2026)
    assert [r["domain"] for r in rows] == ["new.example.com"]


def test_prune_zero_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_LOG_DIR", str(tmp_path))
    _write(tmp_path, "alice.log", SAMPLE)
    assert logparse.prune_all(0, year=2026) == 0


def test_prune_keeps_undatable_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_LOG_DIR", str(tmp_path))
    _write(tmp_path, "alice.log",
           "no timestamp config x.com is 0.0.0.0\n"
           "Jun 20 10:00:00 dnsmasq[1]: config old.com is 0.0.0.0\n")
    removed = logparse.prune_all(2, year=2026, now=datetime.datetime(2026, 6, 24, 0, 0, 0))
    assert removed == 1                       # only the dated-old line
    assert "no timestamp" in (tmp_path / "alice.log").read_text(encoding="utf-8")


def test_clear_all_truncates_every_file(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_LOG_DIR", str(tmp_path))
    _write(tmp_path, "alice.log", SAMPLE)
    _write(tmp_path, "bob.log", "Jun 24 23:00:00 dnsmasq[9]: config bad.org is 0.0.0.0\n")
    assert logparse.clear_all() == 2
    assert (tmp_path / "alice.log").read_text(encoding="utf-8") == ""
    assert logparse.collect_blocked(year=2026) == []


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


def test_summarize_ungrouped_has_no_broad_key():
    rows = [{"time": "2026-06-24T22:11:00", "user": "a", "domain": "x.googlevideo.com"}]
    out = logparse.summarize(rows)
    assert out[0]["domain"] == "x.googlevideo.com"   # unchanged
    assert "broad" not in out[0]


def test_summarize_group_collapses_subdomains_and_sums_counts():
    rows = [
        {"time": "2026-06-24T22:11:00", "user": "alice", "domain": "r3---sn-a.googlevideo.com"},
        {"time": "2026-06-24T22:10:00", "user": "alice", "domain": "r5---sn-b.googlevideo.com"},
        {"time": "2026-06-24T22:09:00", "user": "alice", "domain": "fonts.googleapis.com"},
    ]
    by = {(r["user"], r["domain"]): r for r in logparse.summarize(rows, group=True)}
    assert by[("alice", "googlevideo.com")]["count"] == 2
    assert by[("alice", "googlevideo.com")]["last_seen"] == "2026-06-24T22:11:00"
    assert by[("alice", "googlevideo.com")]["broad"] is False
    assert by[("alice", "googleapis.com")]["broad"] is True   # shared CDN flagged
