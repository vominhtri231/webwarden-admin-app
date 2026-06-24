"""App settings persistence: defaults, roundtrip, clamping, malformed files."""
import pytest

from webwarden_cli import settings


@pytest.fixture(autouse=True)
def _etc(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBWARDEN_ETC", str(tmp_path))
    return tmp_path


def test_default_retention_when_missing():
    assert settings.get_retention_days() == 30
    assert settings.read_settings()["log_retention_days"] == 30


def test_set_and_read_roundtrip():
    assert settings.set_retention_days(7) == 7
    assert settings.get_retention_days() == 7


def test_retention_clamped_to_range():
    assert settings.set_retention_days(-5) == 0
    assert settings.set_retention_days(99999) == 365


def test_zero_disables_keeps_value():
    assert settings.set_retention_days(0) == 0
    assert settings.get_retention_days() == 0


def test_malformed_file_falls_back_to_default(_etc):
    (_etc / "settings.json").write_text("{ not json", encoding="utf-8")
    assert settings.get_retention_days() == 30


def test_non_int_value_falls_back():
    assert settings.set_retention_days("abc") == 30
