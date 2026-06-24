"""Allowlist editor: pick a user, add/remove approved domains."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ..cli_args import (allow_args, disallow_args, list_args, prepare_domain, users_args)
from ..widgets.confirm import confirm


class AllowlistView(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.window = window
        self.client = window.client
        self._user = None
        self._usernames = []
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(self, m)(12)

        top = Gtk.Box(spacing=6)
        top.append(Gtk.Label(label="User:"))
        self.user_dd = Gtk.DropDown()
        self.user_dd.connect("notify::selected", self._on_user_changed)
        top.append(self.user_dd)
        self.append(top)

        add = Gtk.Box(spacing=6)
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("example.com or a pasted URL")
        self.entry.set_hexpand(True)
        self.entry.connect("activate", lambda e: self._add())
        add_btn = Gtk.Button(label="Add")
        add_btn.connect("clicked", lambda b: self._add())
        add.append(self.entry)
        add.append(add_btn)
        self.append(add)

        note = Gtk.Label(label="Approving a domain also covers its subdomains.", xalign=0)
        note.add_css_class("dim-label")
        self.append(note)

        self.listbox = Gtk.ListBox()
        scr = Gtk.ScrolledWindow()
        scr.set_vexpand(True)
        scr.set_child(self.listbox)
        self.append(scr)
        self.reload_users()

    # users dropdown ---------------------------------------------------------
    def reload_users(self):
        self.client.run_json(users_args(), self._populate_users, self._err, key="users")

    def _populate_users(self, data):
        self._usernames = [u["username"] for u in data]
        self.user_dd.set_model(Gtk.StringList.new(self._usernames))
        if self._usernames:
            self.user_dd.set_selected(0)
            self._user = self._usernames[0]
            self._load_domains()

    def _on_user_changed(self, dd, _pspec):
        idx = dd.get_selected()
        if 0 <= idx < len(self._usernames):
            self._user = self._usernames[idx]
            self._load_domains()

    # domains ----------------------------------------------------------------
    def _load_domains(self):
        if not self._user:
            return
        self.client.run_json(list_args(self._user), self._populate_domains,
                             self._err, key="list:" + self._user)

    def _populate_domains(self, data):
        child = self.listbox.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt
        for d in data.get("domains", []):
            self.listbox.append(self._domain_row(d))

    def _domain_row(self, domain):
        row = Gtk.Box(spacing=12)
        for m in ("set_margin_top", "set_margin_bottom"):
            getattr(row, m)(4)
        row.set_margin_start(8)
        lbl = Gtk.Label(label=domain, xalign=0)
        lbl.set_hexpand(True)
        rm = Gtk.Button(label="Remove")
        rm.add_css_class("destructive-action")
        rm.connect("clicked", lambda b: self._remove(domain))
        row.append(lbl)
        row.append(rm)
        return row

    def _add(self):
        raw = self.entry.get_text()
        domain, ok = prepare_domain(raw)
        if not ok:
            self.window.notify("Invalid domain: " + (raw or "(empty)"), error=True)
            return
        if not self._user:
            return
        self.client.run_mutation(allow_args(self._user, [domain]),
                                 lambda out: self._after("Added " + domain),
                                 self._err, key="allow")
        self.entry.set_text("")

    def _remove(self, domain):
        def do():
            self.client.run_mutation(disallow_args(self._user, [domain]),
                                     lambda out: self._after("Removed " + domain),
                                     self._err, key="disallow")
        confirm(self.window, "Remove {} for {}?".format(domain, self._user), do)

    def _after(self, msg):
        self.window.notify(msg)
        self._load_domains()

    def _err(self, msg):
        self.window.notify(msg, error=True)
