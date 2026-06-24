"""Settings view: blocked-log retention (days). 0 = keep forever.

Saving writes the setting through pkexec and the backend prunes existing logs
immediately, so the change takes effect at once.
"""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ..cli_args import set_retention_args, settings_args


class SettingsView(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window = window
        self.client = window.client
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(self, m)(16)

        title = Gtk.Label(label="Blocked-log retention", xalign=0)
        title.add_css_class("title-4")
        self.append(title)

        row = Gtk.Box(spacing=8)
        row.append(Gtk.Label(label="Keep logs for"))
        self.spin = Gtk.SpinButton.new_with_range(0, 365, 1)
        self.spin.set_value(30)
        row.append(self.spin)
        row.append(Gtk.Label(label="days  (0 = keep forever)"))
        self.append(row)

        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")
        save.set_halign(Gtk.Align.START)
        save.connect("clicked", lambda b: self._save())
        self.append(save)

        note = Gtk.Label(
            label="Older blocked-log entries are deleted automatically. "
                  "Saving also prunes existing logs now.", xalign=0)
        note.add_css_class("dim-label")
        note.set_wrap(True)
        self.append(note)

        self._load()

    def _load(self):
        self.client.run_json(settings_args(), self._populate, self._err, key="settings")

    def _populate(self, data):
        try:
            self.spin.set_value(int(data.get("log_retention_days", 30)))
        except (TypeError, ValueError):
            self.spin.set_value(30)

    def _save(self):
        days = int(self.spin.get_value())
        self.client.run_mutation(
            set_retention_args(days),
            lambda out: self.window.notify("Retention saved: {} day(s)".format(days)),
            self._err, key="set-retention")

    def _err(self, msg):
        self.window.notify(msg, error=True)
