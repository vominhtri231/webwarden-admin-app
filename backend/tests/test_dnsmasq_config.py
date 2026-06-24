"""dnsmasq per-user config generation tests (rendered text only)."""
import pytest

from webwarden_cli import dnsmasq_config as dc
from webwarden_cli import state


def test_render_golden_two_domains():
    conf = dc.render_dnsmasq_conf("alice", 5354, ["b.com", "a.com"], upstreams=("1.1.1.1",))
    expected = (
        "# Managed by webwarden for user alice. Do not edit by hand.\n"
        "port=5354\n"
        "listen-address=127.0.0.1\n"
        "bind-interfaces\n"
        "no-resolv\n"
        "log-queries\n"
        "log-facility=/var/log/webwarden/alice.log\n"
        "min-cache-ttl=60\n"
        "\n"
        "# Default-deny: anything not explicitly allowed resolves to 0.0.0.0 / ::\n"
        "address=/#/0.0.0.0\n"
        "address=/#/::\n"
        "\n"
        "# Allowed domains (forward upstream + populate nft sets)\n"
        "server=/a.com/1.1.1.1\n"
        "nftset=/a.com/inet#kidfilter#allow_v4_alice,inet#kidfilter#allow_v6_alice\n"
        "server=/b.com/1.1.1.1\n"
        "nftset=/b.com/inet#kidfilter#allow_v4_alice,inet#kidfilter#allow_v6_alice\n"
    )
    assert conf == expected


def test_render_empty_allowlist_is_block_only():
    conf = dc.render_dnsmasq_conf("bob", 5355, [])
    assert "address=/#/0.0.0.0" in conf
    assert "address=/#/::" in conf
    assert "server=/" not in conf
    assert "nftset=" not in conf
    assert "port=5355" in conf


def test_render_emits_both_upstreams_per_domain():
    conf = dc.render_dnsmasq_conf("alice", 5354, ["x.com"], upstreams=("1.1.1.1", "8.8.8.8"))
    assert "server=/x.com/1.1.1.1" in conf
    assert "server=/x.com/8.8.8.8" in conf


def test_write_user_dnsmasq_requires_port(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))
    with pytest.raises(ValueError):
        dc.write_user_dnsmasq("nobody")


def test_write_user_dnsmasq_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))
    state.alloc_index("alice")                 # -> port 5354
    state.add_domains("alice", ["example.com"])
    conf = dc.write_user_dnsmasq("alice")
    assert "port=5354" in conf
    assert "server=/example.com/" in conf
    # file written under the redirected etc root
    from webwarden_cli import paths
    with open(paths.dnsmasq_conf_path("alice"), encoding="utf-8") as f:
        assert f.read() == conf


def test_validate_conf_skips_on_non_linux(monkeypatch):
    monkeypatch.setattr(dc.sys, "platform", "win32")
    ok, msg = dc.validate_conf("whatever.conf")
    assert ok is True
    assert "skipped" in msg
