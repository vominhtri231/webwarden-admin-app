"""Registrable-domain heuristic + broad-CDN flagging tests."""
from webwarden_cli import domain_groups


def test_registrable_two_labels_unchanged():
    assert domain_groups.registrable("example.com") == "example.com"


def test_registrable_collapses_subdomains():
    assert domain_groups.registrable("r3---sn-x.googlevideo.com") == "googlevideo.com"
    assert domain_groups.registrable("i.ytimg.com") == "ytimg.com"
    assert domain_groups.registrable("a.b.c.example.com") == "example.com"


def test_registrable_multi_label_suffix_keeps_three():
    assert domain_groups.registrable("www.bbc.co.uk") == "bbc.co.uk"
    assert domain_groups.registrable("shop.example.com.au") == "example.com.au"


def test_registrable_edge_cases():
    assert domain_groups.registrable("localhost") == "localhost"   # single label
    assert domain_groups.registrable("Example.COM.") == "example.com"  # case + trailing dot
    assert domain_groups.registrable("") == ""
    assert domain_groups.registrable(None) == ""


def test_is_broad_flags_shared_cdns():
    assert domain_groups.is_broad("cloudfront.net") is True
    assert domain_groups.is_broad("googleapis.com") is True
    assert domain_groups.is_broad("googlevideo.com") is False   # YouTube-specific
    assert domain_groups.is_broad("example.com") is False
