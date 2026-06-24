"""Blocked-attempts log: ColumnView with search, quick ranges, summary, and a
one-click 'allow this domain for this user'. Auto-refreshes by polling."""
import datetime

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from ..cli_args import allow_args, log_args, since_iso
from ..models.log_filter import filter_rows
from ..models.row_items import LogItem
from ..widgets.confirm import confirm

POLL_SECONDS = 5


class LogView(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.window = window
        self.client = window.client
        self._summary = False
        self._since = None
        self._text = ""

        self._build_toolbar()
        self.store = Gio.ListStore(item_type=LogItem)
        self.selection = Gtk.SingleSelection(model=self.store)
        self.column_view = Gtk.ColumnView(model=self.selection)
        self._add_column("Time", "time", expand=False)
        self._add_column("User", "user", expand=False)
        self._add_column("Domain", "domain", expand=True)
        self._count_col = self._add_column("Count", "count", expand=False)
        self._count_col.set_visible(False)

        scr = Gtk.ScrolledWindow()
        scr.set_vexpand(True)
        scr.set_child(self.column_view)
        self.append(scr)

        self._poll_id = GLib.timeout_add_seconds(POLL_SECONDS, self._poll)
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
        self.append(bar)

    def _add_column(self, title, prop, expand=False):
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda f, li: li.set_child(Gtk.Label(xalign=0)))

        def bind(f, li, prop=prop):
            val = li.get_item().get_property(prop)
            li.get_child().set_text("" if val is None else str(val))

        factory.connect("bind", bind)
        col = Gtk.ColumnViewColumn(title=title, factory=factory)
        col.set_expand(expand)
        self.column_view.append_column(col)
        return col

    def reload(self):
        self.client.run_json(log_args(since=self._since, summary=self._summary),
                             self._populate, self._err, key="log")

    def _populate(self, data):
        self._count_col.set_visible(self._summary)
        self.store.remove_all()
        for r in filter_rows(data, self._text):
            self.store.append(LogItem(
                time=r.get("last_seen") if self._summary else r.get("time"),
                user=r.get("user"), domain=r.get("domain"), count=r.get("count", 0)))

    def _on_search(self, entry):
        self._text = entry.get_text()
        self.reload()

    def _on_range(self, btn, kw):
        self._since = None if kw is None else since_iso(datetime.datetime.now(), **kw)
        self.reload()

    def _on_summary(self, toggle):
        self._summary = toggle.get_active()
        self.reload()

    def _allow_selected(self):
        item = self.selection.get_selected_item()
        if item is None:
            self.window.notify("Select a blocked row first", error=True)
            return
        user, domain = item.user, item.domain

        def do():
            self.client.run_mutation(allow_args(user, [domain]),
                                     lambda out: self._after("Allowed {} for {}".format(domain, user)),
                                     self._err, key="allow")
        confirm(self.window, "Allow {} for {}?".format(domain, user), do)

    def _after(self, msg):
        self.window.notify(msg)
        self.reload()

    def _err(self, msg):
        self.window.notify(msg, error=True)

    def _poll(self):
        if self.get_root() is None:
            return False        # window closed: stop the timer
        self.reload()
        return True
