"""Parse per-user dnsmasq logs into blocked-attempt records.

A *blocked attempt* is a query the allowlist refused: dnsmasq answers it from
the catch-all ``address=`` directive, logged as ``config <domain> is 0.0.0.0``
(or ``is ::``). Allowed visits appear as ``forwarded``/``reply`` lines and are
NOT blocks.

LINUX-VERIFY (plan Phase 06 / Phase 10): confirm the exact line format against
the target's dnsmasq; ``_BLOCK_RE`` is isolated so the pattern can be swapped
after capturing real log samples. ``year`` is supplied by the caller because
dnsmasq log timestamps omit the year.
"""
import datetime
import os
import re

from . import paths

# The blocked-answer message. ``config`` is dnsmasq's keyword for an answer that
# came from an address= directive (our catch-all).
_BLOCK_RE = re.compile(
    r"\bconfig\s+(?P<domain>[A-Za-z0-9.\-]+)\s+is\s+(?:0\.0\.0\.0|::|\[::\])(?=\s|$)")

# Optional leading syslog-style timestamp "Mon DD HH:MM:SS".
_TS_RE = re.compile(r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})")
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    start=1)}


def _extract_iso(line, year):
    m = _TS_RE.match(line)
    if not m or year is None:
        return None
    mon = _MONTHS.get(m.group("mon"))
    if not mon:
        return None
    return "{:04d}-{:02d}-{:02d}T{}".format(year, mon, int(m.group("day")), m.group("time"))


def parse_line(line, user, year=None):
    m = _BLOCK_RE.search(line)
    if not m:
        return None
    return {
        "time": _extract_iso(line, year),
        "user": user,
        "domain": m.group("domain").rstrip(".").lower(),
    }


def parse_blocked(path, user, since=None, year=None):
    """Blocked rows from one user's log file, newest first."""
    rows = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                row = parse_line(line, user, year)
                if row is None:
                    continue
                if since and row["time"] and row["time"] < since:
                    continue
                rows.append(row)
    except FileNotFoundError:
        return []
    rows.reverse()
    return rows


def _log_users(directory):
    try:
        return sorted(fn[:-4] for fn in os.listdir(directory) if fn.endswith(".log"))
    except FileNotFoundError:
        return []


def collect_blocked(user=None, since=None, year=None):
    """Blocked rows across users (or a single user), newest first overall."""
    names = [user] if user else _log_users(paths.log_dir())
    rows = []
    for name in names:
        rows.extend(parse_blocked(paths.user_log_path(name), name, since, year))
    rows.sort(key=lambda r: r["time"] or "", reverse=True)
    return rows


# Retention / deletion -------------------------------------------------------
def prune_log_file(path, cutoff_iso, year=None):
    """Drop lines older than ``cutoff_iso`` from one log file, in place.

    Lines without a parseable timestamp are kept (we can't date them). The
    rewrite reuses the same open handle (seek+truncate) so the file's inode,
    owner and mode are preserved and the writing dnsmasq instance keeps its fd
    valid -- same rationale as logrotate ``copytruncate``. Returns lines removed.
    """
    try:
        f = open(path, "r+", encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return 0
    with f:
        lines = f.readlines()
        kept = [ln for ln in lines
                if not (_extract_iso(ln, year) and _extract_iso(ln, year) < cutoff_iso)]
        removed = len(lines) - len(kept)
        if removed:
            f.seek(0)
            f.writelines(kept)
            f.truncate()
    return removed


def prune_all(retention_days, year=None, now=None):
    """Prune every user log to ``retention_days``; no-op when it is 0/None.

    Returns total lines removed across all user logs.
    """
    if not retention_days or retention_days <= 0:
        return 0
    now = now or datetime.datetime.now()
    cutoff = (now - datetime.timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%S")
    total = 0
    for name in _log_users(paths.log_dir()):
        total += prune_log_file(paths.user_log_path(name), cutoff, year)
    return total


def clear_all():
    """Truncate every user log to zero in place. Returns files cleared."""
    count = 0
    for name in _log_users(paths.log_dir()):
        try:
            with open(paths.user_log_path(name), "r+", encoding="utf-8") as f:
                f.truncate(0)
            count += 1
        except FileNotFoundError:
            continue
    return count


def summarize(rows):
    """Dedup to [{user, domain, count, last_seen}], most-recent first."""
    agg = {}
    for r in rows:
        key = (r["user"], r["domain"])
        a = agg.setdefault(key, {"user": r["user"], "domain": r["domain"],
                                 "count": 0, "last_seen": None})
        a["count"] += 1
        if r["time"] and (a["last_seen"] is None or r["time"] > a["last_seen"]):
            a["last_seen"] = r["time"]
    out = list(agg.values())
    out.sort(key=lambda a: (a["last_seen"] or "", a["count"]), reverse=True)
    return out
