"""Main application window: a stack of the four views + a toast overlay.

The four views are mounted by build_views() (Phase 08). Until then the stack
shows placeholders so the shell is runnable on its own.
"""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from .widgets.toast import Toast


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app, client, backend_ok):
        super().__init__(application=app, title="webwarden admin")
        self.set_default_size(960, 640)
        self.client = client

        if not backend_ok:
            self.set_child(_backend_missing())
            return

        self.toast = Toast()
        self.stack = Gtk.Stack()
        switcher = Gtk.StackSwitcher(stack=self.stack)
        header = Gtk.HeaderBar()
        header.set_title_widget(switcher)
        self.set_titlebar(header)

        self.build_views()

        overlay = Gtk.Overlay()
        overlay.set_child(self.stack)
        overlay.add_overlay(self.toast)
        self.set_child(overlay)

    def build_views(self):
        """Mount the four views into the stack."""
        from .views.allowlist_view import AllowlistView
        from .views.log_view import LogView
        from .views.settings_view import SettingsView
        from .views.status_view import StatusView
        from .views.users_view import UsersView
        self.stack.add_titled(UsersView(self), "users", "Users")
        self.stack.add_titled(AllowlistView(self), "allowlist", "Allowlist")
        self.stack.add_titled(LogView(self), "log", "Blocked Log")
        self.stack.add_titled(StatusView(self), "status", "Status")
        self.stack.add_titled(SettingsView(self), "settings", "Settings")

    def notify(self, text, error=False):
        self.toast.show(text, error=error)


def _backend_missing():
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_valign(Gtk.Align.CENTER)
    box.set_halign(Gtk.Align.CENTER)
    title = Gtk.Label(label="webwarden backend not installed")
    title.add_css_class("title-2")
    box.append(title)
    box.append(Gtk.Label(label="Run install.sh to set it up, then reopen this app."))
    return box
