"""nftables ruleset generation tests (rendered text only)."""
from webwarden_cli import nftables_ruleset as nft


def test_render_golden_single_user():
    text = nft.render_ruleset([{"username": "alice", "uid": 1000, "port": 5354}])
    expected = (
        "#!/usr/sbin/nft -f\n"
        "# Managed by webwarden. Do not edit by hand.\n"
        "\n"
        "# Idempotent reload: ensure-exists, delete, recreate.\n"
        "table inet kidfilter\n"
        "delete table inet kidfilter\n"
        "\n"
        "table inet kidfilter {\n"
        "    set allow_v4_alice { type ipv4_addr; }\n"
        "    set allow_v6_alice { type ipv6_addr; }\n"
        "\n"
        "    chain dnsredirect {\n"
        "        type nat hook output priority -100; policy accept;\n"
        "        meta skuid 1000 udp dport { 53, 853 } redirect to :5354\n"
        "        meta skuid 1000 tcp dport { 53, 853 } redirect to :5354\n"
        "    }\n"
        "\n"
        "    chain egress {\n"
        "        type filter hook output priority 0; policy accept;\n"
        "        # alice (uid 1000)\n"
        "        meta skuid 1000 ip daddr 127.0.0.0/8 accept\n"
        "        meta skuid 1000 ip6 daddr ::1 accept\n"
        "        meta skuid 1000 tcp dport { 80, 443 } ip daddr @allow_v4_alice accept\n"
        "        meta skuid 1000 tcp dport { 80, 443 } ip6 daddr @allow_v6_alice accept\n"
        "        meta skuid 1000 reject with icmpx type admin-prohibited\n"
        "    }\n"
        "}\n"
    )
    assert text == expected


def test_users_sorted_by_uid_and_isolated():
    text = nft.render_ruleset([
        {"username": "bob", "uid": 1001, "port": 5355},
        {"username": "alice", "uid": 1000, "port": 5354},
    ])
    # alice's set block appears before bob's
    assert text.index("allow_v4_alice") < text.index("allow_v4_bob")
    # each user gets its own redirect port
    assert "meta skuid 1000 udp dport { 53, 853 } redirect to :5354" in text
    assert "meta skuid 1001 udp dport { 53, 853 } redirect to :5355" in text


def test_empty_specs_minimal_table():
    text = nft.render_ruleset([])
    assert "table inet kidfilter {" in text
    assert "chain dnsredirect {" in text
    assert "chain egress {" in text
    assert "meta skuid" not in text       # no per-user rules
    assert "set allow_" not in text       # no sets


def test_admin_uid_never_matched():
    text = nft.render_ruleset([{"username": "kid", "uid": 1000, "port": 5354}])
    assert "skuid 0" not in text          # root/admin not referenced


def test_flush_set_commands():
    cmds = nft.flush_set_commands("alice")
    assert cmds == [
        ["/usr/sbin/nft", "flush", "set", "inet", "kidfilter", "allow_v4_alice"],
        ["/usr/sbin/nft", "flush", "set", "inet", "kidfilter", "allow_v6_alice"],
    ]


def test_build_specs_skips_unresolvable(tmp_path, monkeypatch):
    from webwarden_cli import state, users
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))
    state.set_locked("alice", True)
    state.alloc_index("alice")
    state.set_locked("ghost", True)        # no uid -> skipped
    monkeypatch.setattr(users, "uid_of", lambda n: 1000 if n == "alice" else None)
    specs = nft.build_specs()
    assert specs == [{"username": "alice", "uid": 1000, "port": 5354}]


def test_validate_ruleset_skips_on_non_linux(monkeypatch):
    monkeypatch.setattr(nft.sys, "platform", "win32")
    ok, msg = nft.validate_ruleset("whatever.nft")
    assert ok is True and "skipped" in msg
