"""Domain validation and normalization for webwarden.

CRITICAL: this file is duplicated verbatim in gui/webwarden_admin/validation.py.
The two copies MUST stay byte-identical (test_validation_sync enforces this).
Edit both, or neither.

This is the single trust boundary for domain input before it is handed to the
webwarden CLI as argv. Anything that does not match DOMAIN_RE is rejected.
"""
import re

# Spec section 6 domain pattern. Lowercase only; callers normalize first.
DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*\.)+[a-z]{2,}$")

# RFC 1035 hard limit on a fully-qualified domain name.
MAX_DOMAIN_LEN = 253


def normalize_domain(raw):
    """Normalize admin input to a bare lowercase hostname.

    Accepts a plain domain ("Example.com") or a pasted URL
    ("https://user@example.com:8443/path?q=1") and returns "example.com".
    Returns "" if nothing usable remains.
    """
    if raw is None:
        return ""
    s = raw.strip()
    if not s:
        return ""
    # strip scheme (http://, https://, ...)
    if "://" in s:
        s = s.split("://", 1)[1]
    # strip path / query / fragment
    for sep in ("/", "?", "#"):
        if sep in s:
            s = s.split(sep, 1)[0]
    # strip userinfo (user:pass@host)
    if "@" in s:
        s = s.split("@", 1)[1]
    # strip port (a hostname never contains ':')
    if ":" in s:
        s = s.split(":", 1)[0]
    return s.strip().lower().rstrip(".")


def is_valid_domain(domain):
    """True if `domain` is a valid, already-normalized hostname."""
    if not domain or len(domain) > MAX_DOMAIN_LEN:
        return False
    return DOMAIN_RE.match(domain) is not None


def normalize_and_validate(raw):
    """Normalize then validate. Returns (normalized_domain, is_ok)."""
    d = normalize_domain(raw)
    return d, is_valid_domain(d)
