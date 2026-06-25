"""Registrable-domain (eTLD+1) grouping + advisory broad-CDN flagging.

Modern sites pull from many registrable domains AND many dynamic subdomains
(``r3---sn-x.googlevideo.com``). dnsmasq already suffix-matches, so allowing the
registrable domain (``googlevideo.com``) covers every subdomain -- this module
just collapses the *display* of blocked attempts so an admin approves one entry,
not hundreds.

``registrable`` is a deliberate heuristic, NOT the full Public Suffix List: a
human approves every result downstream, so a rare misgroup is corrected at
approval time. KISS/YAGNI -- no data file to ship or refresh.
"""

# Multi-label public suffixes where eTLD+1 is the last THREE labels (e.g.
# ``bbc.co.uk``). Small curated set; extend if a real-world miss bites.
_MULTI_LABEL_SUFFIXES = frozenset({
    "co.uk", "org.uk", "gov.uk", "ac.uk", "co.jp", "com.au", "net.au", "org.au",
    "com.br", "com.cn", "com.hk", "co.in", "co.kr", "co.nz", "co.za", "com.sg",
    "com.tw",
})

# Multi-tenant CDNs/clouds: allowing one of these effectively permits many
# unrelated sites that ride the same infrastructure. Advisory only -- surfaced
# to the admin as a "broad" warning; never used to block or auto-skip.
_BROAD_DOMAINS = frozenset({
    "cloudfront.net", "amazonaws.com", "akamai.net", "akamaihd.net",
    "akamaiedge.net", "fastly.net", "googleusercontent.com", "googleapis.com",
    "gstatic.com", "azureedge.net", "cloudflare.net", "windows.net",
})


def registrable(domain):
    """Best-effort registrable domain (eTLD+1) for ``domain``.

    Heuristic: the last two labels, or the last three when the final two are a
    known multi-label suffix. Inputs are already-normalized hostnames; anything
    with <=2 labels is returned as-is.
    """
    d = (domain or "").strip().strip(".").lower()
    labels = [x for x in d.split(".") if x]
    if len(labels) <= 2:
        return ".".join(labels)
    if ".".join(labels[-2:]) in _MULTI_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def is_broad(registrable_domain):
    """True if a registrable domain is a known shared/multi-tenant CDN."""
    return registrable_domain in _BROAD_DOMAINS
