"""Backend domain validation tests."""
import pytest

from webwarden_cli import validation as v
from testkit.domain_cases import NORMALIZE_CASES, VALID_DOMAINS, INVALID_DOMAINS


@pytest.mark.parametrize("raw,expected", NORMALIZE_CASES)
def test_normalize(raw, expected):
    assert v.normalize_domain(raw) == expected


@pytest.mark.parametrize("d", VALID_DOMAINS)
def test_valid(d):
    assert v.is_valid_domain(d) is True


@pytest.mark.parametrize("d", INVALID_DOMAINS)
def test_invalid(d):
    assert v.is_valid_domain(d) is False


def test_normalize_and_validate_url():
    d, ok = v.normalize_and_validate("https://Example.com/login")
    assert d == "example.com"
    assert ok is True


def test_injection_is_rejected_after_normalize():
    d, ok = v.normalize_and_validate("example.com; rm -rf /")
    # path stripping leaves "example.com;" which fails the regex
    assert ok is False
