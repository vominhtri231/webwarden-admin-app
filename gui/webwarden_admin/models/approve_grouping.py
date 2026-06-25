"""Pure helper for batch-approving selected blocked rows (no GTK).

The discovery flow lets an admin multi-select blocked domains and approve them
in one privileged call per user. Grouping by user keeps domain order stable and
dedups, so each user maps to a single ``allow <user> <d1> <d2>...`` invocation.
Kept GTK-free so it is unit-testable on any platform.
"""


def group_domains_by_user(rows):
    """Map selected rows -> {user: [unique domains, first-seen order]}.

    ``rows`` is any iterable of dicts/objects exposing ``user`` and ``domain``
    (here, dicts built from the selected LogItems). Blank users/domains are
    skipped so a malformed selection never produces an empty argv.
    """
    out = {}
    for r in rows:
        user = r.get("user")
        domain = r.get("domain")
        if not user or not domain:
            continue
        seen = out.setdefault(user, [])
        if domain not in seen:
            seen.append(domain)
    return out
