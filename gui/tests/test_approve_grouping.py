"""Pure batch-approve grouping tests (no GTK)."""
from webwarden_admin.models.approve_grouping import group_domains_by_user


def test_groups_unique_domains_per_user_in_order():
    rows = [
        {"user": "alice", "domain": "youtube.com"},
        {"user": "alice", "domain": "googlevideo.com"},
        {"user": "alice", "domain": "youtube.com"},   # dup -> dropped
    ]
    assert group_domains_by_user(rows) == {"alice": ["youtube.com", "googlevideo.com"]}


def test_splits_across_users():
    rows = [
        {"user": "alice", "domain": "a.com"},
        {"user": "bob", "domain": "b.com"},
    ]
    assert group_domains_by_user(rows) == {"alice": ["a.com"], "bob": ["b.com"]}


def test_skips_blank_user_or_domain():
    rows = [
        {"user": "", "domain": "a.com"},
        {"user": "alice", "domain": ""},
        {"user": "alice", "domain": "ok.com"},
    ]
    assert group_domains_by_user(rows) == {"alice": ["ok.com"]}


def test_empty_selection_is_empty():
    assert group_domains_by_user([]) == {}
