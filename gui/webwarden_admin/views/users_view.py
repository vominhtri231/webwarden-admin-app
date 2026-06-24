"""Users panel: lock/unlock toggle per human user + sudo warning badge."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ..cli_args import lock_args, unlock_args, users_args
from ..widgets.confirm import confirm


class UsersView(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.window = window
        self.client = window.client
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(self, m)(12)

        bar = Gtk.Box(spacing=6)
        note = Gtk.Label(label="Locked users may only visit their allowlist.", xalign=0)
        note.set_hexpand(True)
        bar.append(note)
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
        self.client.run_json(users_args(), self._populate, self._err, key="users")

    def _populate(self, data):
        child = self.listbox.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt
        for u in data:
            self.listbox.append(self._row(u))

    def _row(self, u):
        row = Gtk.Box(spacing=12)
        for m in ("set_margin_top", "set_margin_bottom"):
            getattr(row, m)(6)
        row.set_margin_start(8)
        name = Gtk.Label(label="{} (uid {})".format(u["username"], u["uid"]), xalign=0)
        name.set_hexpand(True)
        row.append(name)
        if u.get("has_sudo"):
            badge = Gtk.Label(label="admin — defeats lock")
            badge.add_css_class("warn-badge")
            badge.set_tooltip_text(
                "This user has admin rights. Run 'deluser {} sudo' so the lock holds."
                .format(u["username"]))
            row.append(badge)
        switch = Gtk.Switch()
        switch.set_active(bool(u["locked"]))
        switch.set_valign(Gtk.Align.CENTER)
        switch.connect("state-set", self._on_toggle, u)
        row.append(switch)
        return row

    def _on_toggle(self, switch, state, u):
        username = u["username"]
        action = "lock" if state else "unlock"

        def do():
            args = lock_args(username) if state else unlock_args(username)
            self.client.run_mutation(args,
                                     lambda out: self._after(action, username),
                                     self._err, key="lock:" + username)

        detail = None
        if state and u.get("has_sudo"):
            detail = ("{0} has admin rights; the lock will not hold until you run "
                      "'deluser {0} sudo'.".format(username))
        confirm(self.window, "{} {}?".format(action.capitalize(), username), do, detail)
        return True   # don't flip the switch until reload reflects real state

    def _after(self, action, username):
        self.window.notify("{}ed {}".format(action, username))
        self.reload()

    def _err(self, msg):
        self.window.notify(msg, error=True)
