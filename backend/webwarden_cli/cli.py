"""webwarden command-line interface (argparse dispatch).

Implements the stable contract (spec 4.4). Mutating commands validate input,
require root, mutate on-disk state, then re-apply enforcement. All commands exit
0 on success and non-zero with a clear stderr message on error.
"""
import argparse
import datetime
import os
import sys

from . import apply as apply_module
from . import jsonapi, logparse, settings, state, users, validation


def _die(msg, code=2):
    print("webwarden: " + msg, file=sys.stderr)
    return code


def _is_root():
    # geteuid exists only on POSIX; on dev (Windows) treat as root since the
    # privileged side-effects (apply) are Linux-only and mocked in tests.
    return not hasattr(os, "geteuid") or os.geteuid() == 0


def _normalize_domains(raw_domains):
    valid, invalid = [], []
    for raw in raw_domains:
        d, ok = validation.normalize_and_validate(raw)
        if ok:
            valid.append(d)
        else:
            invalid.append(raw)
    return valid, invalid


# Mutating commands ----------------------------------------------------------
def cmd_allow(args):
    if not users.user_exists(args.username):
        return _die("no such user: " + args.username)
    valid, invalid = _normalize_domains(args.domains)
    if invalid:
        return _die("invalid domain(s): " + ", ".join(invalid))
    if not _is_root():
        return _die("must run as root")
    added = state.add_domains(args.username, valid)
    apply_module.apply("allow")
    print("added {} domain(s) for {}".format(len(added), args.username))
    return 0


def cmd_disallow(args):
    if not users.user_exists(args.username):
        return _die("no such user: " + args.username)
    valid, invalid = _normalize_domains(args.domains)
    if invalid:
        return _die("invalid domain(s): " + ", ".join(invalid))
    if not _is_root():
        return _die("must run as root")
    removed = state.remove_domains(args.username, valid)
    apply_module.apply("disallow")
    print("removed {} domain(s) for {}".format(len(removed), args.username))
    return 0


def cmd_lock(args):
    if not users.user_exists(args.username):
        return _die("no such user: " + args.username)
    if not _is_root():
        return _die("must run as root")
    state.set_locked(args.username, True)
    state.alloc_index(args.username)
    apply_module.apply("lock")
    if users.has_sudo(args.username):
        print("warning: {0} has admin (sudo) rights, which defeats the lock; "
              "run 'deluser {0} sudo'".format(args.username), file=sys.stderr)
    print("locked " + args.username)
    return 0


def cmd_unlock(args):
    if not _is_root():
        return _die("must run as root")
    state.set_locked(args.username, False)
    apply_module.apply("unlock")     # stops the instance before we free its port
    state.free_index(args.username)
    print("unlocked " + args.username)
    return 0


def cmd_apply(args):
    if not _is_root():
        return _die("must run as root")
    apply_module.apply("manual")
    print("applied")
    return 0


# Read commands --------------------------------------------------------------
def cmd_list(args):
    if not users.user_exists(args.username):
        return _die("no such user: " + args.username)
    data = jsonapi.list_json(args.username)
    if args.json:
        print(jsonapi.dumps(data))
    else:
        for d in data["domains"]:
            print(d)
    return 0


def cmd_users(args):
    data = jsonapi.users_json()
    if args.json:
        print(jsonapi.dumps(data))
    else:
        for u in data:
            print("{}\t{}\t{}".format(u["uid"], u["username"],
                                      "locked" if u["locked"] else ""))
    return 0


def cmd_status(args):
    data = jsonapi.status_json()
    if args.json:
        print(jsonapi.dumps(data))
    else:
        print("firewall_loaded: {}".format(data["firewall_loaded"]))
        for u in data["users"]:
            flags = []
            if u["locked"]:
                flags.append("locked")
            if u["has_sudo"]:
                flags.append("sudo!")
            if u["locked"] and not u["dns_service_active"]:
                flags.append("service-down")
            print("{}\t{}\t{} domains\t{}".format(
                u["uid"], u["username"], u["allow_count"], " ".join(flags)))
    return 0


def cmd_settings(args):
    if args.set_retention_days is not None:
        if not _is_root():
            return _die("must run as root")
        days = settings.set_retention_days(args.set_retention_days)
        logparse.prune_all(days, year=datetime.date.today().year)   # enforce now
        print("log_retention_days set to {}".format(days))
        return 0
    data = settings.read_settings()
    if args.json:
        print(jsonapi.dumps(data))
    else:
        print("log_retention_days: {}".format(settings.get_retention_days()))
    return 0


def cmd_log(args):
    if args.clear:
        if not _is_root():
            return _die("must run as root")
        n = logparse.clear_all()
        print("cleared {} log file(s)".format(n))
        return 0
    if args.prune:
        if not _is_root():
            return _die("must run as root")
        days = args.days if args.days is not None else settings.get_retention_days()
        removed = logparse.prune_all(days, year=datetime.date.today().year)
        print("pruned {} entr{} older than {} day(s)".format(
            removed, "y" if removed == 1 else "ies", days))
        return 0
    year = datetime.date.today().year
    if args.summary:
        data = jsonapi.log_summary_json(user=args.user, since=args.since, year=year,
                                        group=args.group)
    else:
        data = jsonapi.log_json(user=args.user, since=args.since,
                                limit=args.limit, year=year)
    if args.json:
        print(jsonapi.dumps(data))
    else:
        for r in data:
            if args.summary:
                print("{}\t{}\t{}\tx{}\t{}".format(
                    r["last_seen"], r["user"], r["domain"], r["count"], ""))
            else:
                print("{}\t{}\t{}".format(r["time"], r["user"], r["domain"]))
    return 0


# Parser ---------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="webwarden", description="Per-user website allowlist manager")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("status", help="firewall + per-user service state (JSON)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("users", help="list human users with locked flag")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_users)

    sp = sub.add_parser("list", help="list a user's allowed domains")
    sp.add_argument("username")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("allow", help="allow domain(s) for a user")
    sp.add_argument("username")
    sp.add_argument("domains", nargs="+")
    sp.set_defaults(func=cmd_allow)

    sp = sub.add_parser("disallow", help="remove domain(s) for a user")
    sp.add_argument("username")
    sp.add_argument("domains", nargs="+")
    sp.set_defaults(func=cmd_disallow)

    sp = sub.add_parser("lock", help="restrict a user to their allowlist")
    sp.add_argument("username")
    sp.set_defaults(func=cmd_lock)

    sp = sub.add_parser("unlock", help="remove restrictions from a user")
    sp.add_argument("username")
    sp.set_defaults(func=cmd_unlock)

    sp = sub.add_parser("apply", help="reconcile running state with policy")
    sp.set_defaults(func=cmd_apply)

    sp = sub.add_parser("log", help="blocked-attempt log (JSON); also --prune/--clear")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--summary", action="store_true")
    sp.add_argument("--group", action="store_true",
                    help="with --summary: collapse to registrable domains + flag broad CDNs")
    sp.add_argument("--user")
    sp.add_argument("--since")
    sp.add_argument("--limit", type=int)
    sp.add_argument("--clear", action="store_true", help="truncate all user logs (root)")
    sp.add_argument("--prune", action="store_true",
                    help="drop entries older than retention (root)")
    sp.add_argument("--days", type=int, help="override retention days for --prune")
    sp.set_defaults(func=cmd_log)

    sp = sub.add_parser("settings", help="read/update app settings (JSON)")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--set-retention-days", type=int,
                    help="set blocked-log retention in days (0 = keep forever; root)")
    sp.set_defaults(func=cmd_settings)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except NotImplementedError as e:
        return _die(str(e), 3)
    except Exception as e:  # top-level guard: never traceback at the user
        return _die(str(e), 1)
