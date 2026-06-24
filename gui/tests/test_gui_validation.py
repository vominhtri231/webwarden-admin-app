"""GUI domain validation tests (same expectations as the backend copy)."""
import pytest

from webwarden_admin import validation as v
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
