"""Pure client-side filtering for blocked-log rows (no GTK).

Filtering/sorting is done in Python on the JSON rows (cheap at household scale)
rather than via GTK filter models, which keeps this logic unit-testable.
"""


def matches(row, text_filter=None):
    """True if a row matches the free-text filter (domain or user substring)."""
    if not text_filter:
        return True
    t = text_filter.lower()
    return t in (row.get("domain", "").lower()) or t in (row.get("user", "").lower())


def filter_rows(rows, text_filter=None):
    return [r for r in rows if matches(r, text_filter)]
