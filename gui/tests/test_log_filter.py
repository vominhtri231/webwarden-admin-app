"""Pure log-filter tests (no GTK)."""
from webwarden_admin.models import log_filter


ROWS = [
    {"time": "2026-06-24T22:11:00", "user": "alice", "domain": "ads.example.net"},
    {"time": "2026-06-24T22:10:00", "user": "bob", "domain": "example.com"},
]


def test_no_filter_passes_all():
    assert log_filter.filter_rows(ROWS) == ROWS


def test_text_matches_domain():
    out = log_filter.filter_rows(ROWS, "example.com")
    assert [r["user"] for r in out] == ["bob"]


def test_text_matches_user_case_insensitive():
    out = log_filter.filter_rows(ROWS, "ALICE")
    assert [r["domain"] for r in out] == ["ads.example.net"]


def test_text_no_match():
    assert log_filter.filter_rows(ROWS, "nonsense") == []
