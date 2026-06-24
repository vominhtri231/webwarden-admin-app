"""GTK4 application entry: loads CSS and presents the main window."""
import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from .cli_client import CliClient, backend_available
from .window import MainWindow

APP_ID = "org.webwarden.admin"

_CSS_PATHS = (
    "/usr/share/webwarden-admin/webwarden-admin.css",
    os.path.join(os.path.dirname(__file__), "..", "data", "webwarden-admin.css"),
)


class WebwardenApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        self._load_css()
        MainWindow(self, CliClient(), backend_available()).present()

    def _load_css(self):
        for path in _CSS_PATHS:
            if os.path.exists(path):
                provider = Gtk.CssProvider()
                provider.load_from_path(path)
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(), provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                break


def main():
    return WebwardenApp().run(None)
