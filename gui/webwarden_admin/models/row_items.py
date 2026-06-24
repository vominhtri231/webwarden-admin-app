"""GObject row item for the blocked-log Gtk.ColumnView."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GObject  # noqa: E402


class LogItem(GObject.Object):
    __gtype_name__ = "WebwardenLogItem"

    time = GObject.Property(type=str, default="")
    user = GObject.Property(type=str, default="")
    domain = GObject.Property(type=str, default="")
    count = GObject.Property(type=int, default=0)

    def __init__(self, time="", user="", domain="", count=0):
        super().__init__()
        self.time = time or ""
        self.user = user or ""
        self.domain = domain or ""
        self.count = count or 0
