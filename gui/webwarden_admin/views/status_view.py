"""Status / health view: firewall loaded + per-locked-user resolver state."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ..cli_args import status_args


class StatusView(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.window = window
        self.client = window.client
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(self, m)(12)

        bar = Gtk.Box(spacing=6)
        self.fw_label = Gtk.Label(xalign=0)
        self.fw_label.set_hexpand(True)
        bar.append(self.fw_label)
        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", lambda b: self.reload())
        bar.append(refresh)
        self.append(bar)

        self.listbox = Gtk.ListBox()
        scr = Gtk.ScrolledWindow()
        scr.set_vexpand(True)
        scr.set_child(self.listbox)
        self.append(scr)
        self.reload()

    def reload(self):
        self.client.run_json(status_args(), self._populate,
                             lambda m: self.window.notify(m, error=True), key="status")

    def _populate(self, data):
        loaded = data.get("firewall_loaded")
        self.fw_label.set_text("Firewall loaded: " + ("yes" if loaded else "NO"))
        self.fw_label.remove_css_class("error-text")
        if not loaded:
            self.fw_label.add_css_class("error-text")
        _clear(self.listbox)
        for u in data.get("users", []):
            if not u.get("locked"):
                continue
            self.listbox.append(_service_row(u))


def _service_row(u):
    row = Gtk.Box(spacing=12)
    for m in ("set_margin_top", "set_margin_bottom"):
        getattr(row, m)(4)
    row.set_margin_start(8)
    name = Gtk.Label(label=u["username"], xalign=0)
    name.set_hexpand(True)
    row.append(name)
    active = u.get("dns_service_active")
    badge = Gtk.Label(label="resolver up" if active else "resolver DOWN")
    badge.add_css_class("ok-badge" if active else "warn-badge")
    row.append(badge)
    return row


def _clear(listbox):
    child = listbox.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        listbox.remove(child)
        child = nxt
