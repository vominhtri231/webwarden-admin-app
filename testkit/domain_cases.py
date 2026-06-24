"""Shared domain test cases for both validation suites.

Imported by backend/tests and gui/tests so the two copies of validation.py are
exercised against the exact same expectations. These follow the spec regex
``^[a-z0-9]([a-z0-9-]*\\.)+[a-z]{2,}$`` literally (which intentionally tolerates
empty/hyphen-led inner labels; we do not add stricter rules than the contract).
"""

# (raw_input, expected_normalized)
NORMALIZE_CASES = [
    ("example.com", "example.com"),
    ("  Example.COM  ", "example.com"),
    ("https://example.com/path?q=1", "example.com"),
    ("http://user:pass@sub.example.com:8443/x", "sub.example.com"),
    ("example.com.", "example.com"),
    ("HTTP://WWW.Example.COM", "www.example.com"),
    ("ftp://files.example.org/pub", "files.example.org"),
    ("", ""),
    ("   ", ""),
    (None, ""),
]

VALID_DOMAINS = [
    "example.com",
    "sub.example.com",
    "a.co",
    "www.wikipedia.org",
    "xn--80ak6aa92e.com",
    "my-site.example.co.uk",
    "1.example.com",
]

INVALID_DOMAINS = [
    "",
    "example",              # no TLD
    "example.c",            # TLD too short
    "-bad.com",             # leading hyphen on first label
    "exa mple.com",         # space
    "example.com; rm -rf /",  # shell-injection shaped
    "exam$ple.com",         # illegal char
    "EXAMPLE.COM",          # uppercase (must be normalized first)
    "http://example.com",   # scheme present (must be normalized first)
    ".com",                 # no leading label
]
