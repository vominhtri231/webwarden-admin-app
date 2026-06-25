"""Blocked-attempts log + discovery view.

ColumnView with a per-user filter, registrable-domain grouping (Summary mode),
broad-CDN flags, multi-select, and one-click batch 'allow this set for a user'.
Auto-refreshes by polling -- paused while rows are selected so a tick can't wipe
an in-progress multi-selection."""
import datetime

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from ..cli_args import allow_args, log_args, log_clear_args, since_iso, users_args
from ..models.approve_grouping import group_domains_by_user
from ..models.log_filter import filter_rows
from ..models.row_items import LogItem
from ..widgets.confirm import confirm

POLL_SECONDS = 5
ALL_USERS = "All users"


class LogView(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.window = window
        self.client = window.client
        self._summary = False
        self._since = None
        self._text = ""
        self._user = None
        self._usernames = []

        self._build_toolbar()
        self.store = Gio.ListStore(item_type=LogItem)
        self.selection = Gtk.MultiSelection(model=self.store)
        self.column_view = Gtk.ColumnView(model=self.selection)
        self._add_column("Time", "time", expand=False)
        self._add_column("User", "user", expand=False)
        self._add_column("Domain", "domain", expand=True)
        self._count_col = self._add_column("Count", "count", expand=False)
        self._count_col.set_visible(False)
        self._broad_col = self._add_column(
            "Broad?", "broad", expand=False,
            fmt=lambda v: "⚠ broad" if v else "")
        self._broad_col.set_visible(False)

        scr = Gtk.ScrolledWindow()
        scr.set_vexpand(True)
        scr.set_child(self.column_view)
        self.append(scr)

        self._poll_id = GLib.timeout_add_seconds(POLL_SECONDS, self._poll)
        self.reload_users()
        self.reload()

    def _build_toolbar(self):
        bar = Gtk.Box(spacing=6)
        for m in ("set_margin_top", "set_margin_start", "set_margin_end"):
            getattr(bar, m)(8)
        self.search = Gtk.SearchEntry()
        self.search.set_hexpand(True)
        self.search.set_placeholder_text("filter by domain or user")
        self.search.connect("search-changed", self._on_search)
        bar.append(self.search)
        self.user_dd = Gtk.DropDown(
            expression=Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        self.user_dd.set_model(Gtk.StringList.new([ALL_USERS]))
        self.user_dd.connect("notify::selected", self._on_user_changed)
        bar.append(self.user_dd)
        for label, kw in (("24h", {"hours": 24}), ("7d", {"days": 7}), ("All", None)):
            b = Gtk.Button(label=label)
            b.connect("clicked", self._on_range, kw)
            bar.append(b)
        self.summary_toggle = Gtk.ToggleButton(label="Summary")
        self.summary_toggle.connect("toggled", self._on_summary)
        bar.append(self.summary_toggle)
        allow_btn = Gtk.Button(label="Allow selected")
        allow_btn.connect("clicked", lambda b: self._allow_selected())
        bar.append(allow_btn)
        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", lambda b: self.reload())
        bar.append(refresh)
        clear = Gtk.Button(label="Clear all logs")
        clear.add_css_class("destructive-action")
        clear.connect("clicked", lambda b: self._clear_logs())
        bar.append(clear)
        self.append(bar)

    def _add_column(self, title, prop, expand=False, fmt=None):
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda f, li: li.set_child(Gtk.Label(xalign=0)))
        fmt = fmt or (lambda v: "" if v is None else str(v))

        def bind(f, li, prop=prop, fmt=fmt):
            li.get_child().set_text(fmt(li.get_item().get_property(prop)))

        factory.connect("bind", bind)
        col = Gtk.ColumnViewColumn(title=title, factory=factory)
        col.set_expand(expand)
        self.column_view.append_column(col)
        return col

    # users filter -----------------------------------------------------------
    def reload_users(self):
        # Distinct key: UsersView ("users") and AllowlistView ("allowlist-users")
        # also load users; sharing a key lets the client busy-guard drop whichever
        # fires second -> empty dropdown (issue #2). Keep "log-users" unique.
        self.client.run_json(users_args(), self._populate_users, self._err, key="log-users")

    def _populate_users(self, data):
        self._usernames = [u["username"] for u in data]
        self.user_dd.set_model(Gtk.StringList.new([ALL_USERS] + self._usernames))

    def _on_user_changed(self, dd, _pspec):
        idx = dd.get_selected()
        user = self._usernames[idx - 1] if 1 <= idx <= len(self._usernames) else None
        if user == self._user:
            return                  # set_model resets selection to 0; skip the no-op reload
        self._user = user
        self.reload()

    # log rows ---------------------------------------------------------------
    def reload(self):
        # Summary mode also groups to registrable domains (the discovery view).
        self.client.run_json(
            log_args(user=self._user, since=self._since,
                     summary=self._summary, group=self._summary),
            self._populate, self._err, key="log")

    def _populate(self, data):
        self._count_col.set_visible(self._summary)
        self._broad_col.set_visible(self._summary)
        self.store.remove_all()
        for r in filter_rows(data, self._text):
            self.store.append(LogItem(
                time=r.get("last_seen") if self._summary else r.get("time"),
                user=r.get("user"), domain=r.get("domain"),
                count=r.get("count", 0), broad=r.get("broad", False)))

    def _on_search(self, entry):
        self._text = entry.get_text()
        self.reload()

    def _on_range(self, btn, kw):
        self._since = None if kw is None else since_iso(datetime.datetime.now(), **kw)
        self.reload()

    def _on_summary(self, toggle):
        self._summary = toggle.get_active()
        self.reload()

    # batch approve ----------------------------------------------------------
    def _selected_items(self):
        return [self.store.get_item(i) for i in range(self.store.get_n_items())
                if self.selection.is_selected(i)]

    def _allow_selected(self):
        items = self._selected_items()
        if not items:
            self.window.notify("Select one or more blocked rows first", error=True)
            return
        by_user = group_domains_by_user(
            [{"user": it.user, "domain": it.domain} for it in items])
        total = sum(len(v) for v in by_user.values())
        if len(by_user) == 1:
            user = next(iter(by_user))
            msg = "Allow {} domain(s) for {}?".format(total, user)
        else:
            msg = "Allow {} domain(s) across {} users?".format(total, len(by_user))

        def do():
            for user, domains in by_user.items():
                self.client.run_mutation(
                    allow_args(user, domains),
                    lambda out, u=user, n=len(domains):
                        self._after("Allowed {} domain(s) for {}".format(n, u)),
                    self._err, key="allow:" + user)
        confirm(self.window, msg, do)

    def _clear_logs(self):
        def do():
            self.client.run_mutation(log_clear_args(),
                                     lambda out: self._after("Cleared all blocked logs"),
                                     self._err, key="log-clear")
        confirm(self.window, "Delete ALL blocked-log entries for every user?", do)

    def _after(self, msg):
        self.window.notify(msg)
        self.reload()

    def _err(self, msg):
        self.window.notify(msg, error=True)

    def _poll(self):
        if self.get_root() is None:
            return False        # window closed: stop the timer
        if any(self.selection.is_selected(i) for i in range(self.store.get_n_items())):
            return True         # don't wipe an in-progress multi-selection
        self.reload()
        return True
