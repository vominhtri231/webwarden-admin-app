"""Minimal bottom toast (no libadwaita) for success/error feedback."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402


class Toast(Gtk.Revealer):
    def __init__(self):
        super().__init__(transition_type=Gtk.RevealerTransitionType.SLIDE_UP)
        self._label = Gtk.Label()
        self._label.add_css_class("toast")
        self._label.set_margin_bottom(16)
        self.set_child(self._label)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.END)
        self._timeout = 0

    def show(self, text, error=False):
        self._label.set_text(text)
        if error:
            self._label.add_css_class("toast-error")
        else:
            self._label.remove_css_class("toast-error")
        self.set_reveal_child(True)
        if self._timeout:
            GLib.source_remove(self._timeout)
        self._timeout = GLib.timeout_add_seconds(4, self._hide)

    def _hide(self):
        self.set_reveal_child(False)
        self._timeout = 0
        return False
