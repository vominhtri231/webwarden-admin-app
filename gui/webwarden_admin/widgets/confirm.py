"""Confirmation dialog helper (GTK4 Gtk.AlertDialog)."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402


def confirm(parent, message, on_confirm, detail=None):
    """Show a confirm dialog; invoke on_confirm() if the user accepts."""
    dialog = Gtk.AlertDialog()
    dialog.set_message(message)
    if detail:
        dialog.set_detail(detail)
    dialog.set_buttons(["Cancel", "Confirm"])
    dialog.set_cancel_button(0)
    dialog.set_default_button(1)

    def _cb(d, result):
        try:
            choice = d.choose_finish(result)
        except GLib.Error:
            return
        if choice == 1:
            on_confirm()

    dialog.choose(parent, None, _cb)
