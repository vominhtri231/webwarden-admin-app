# GTK4 + PyGObject Desktop Admin GUI: Implementation Reference

**Context:** Linux Mint (Ubuntu 24.04, Cinnamon), Python 3 + PyGObject, unprivileged GTK4 app invoking `webwarden` CLI via `pkexec`. Four panels: Users list, Allowlist editor, Blocked-attempts log, Status bar.

---

## 1. App Skeleton & Structure

### Architecture Choice
- **Use `Gtk.Application` + `Gtk.ApplicationWindow`**, not `Adw.Application` (libadwaita).
  - **Why:** Cinnamon is not GNOME. Adwaita assumes GNOME theming/integration (automatic stylesheet loading, GNOME-specific widgets). Mint uses its own theme engine. Plain GTK4 gives you portability; Adwaita adds desktop-specific glue that won't integrate cleanly on Cinnamon.
  - **Trade-off:** No automatic dark mode switching or GNOME polish; you must handle theme alignment manually. Acceptable for a utility app.
  - **Source:** [Adwaita targets GNOME](https://pygobject.gnome.org/tutorials/libadwaita/application.html); doesn't guarantee Cinnamon integration.

### Module Split (Per YAGNI/DRY + <200 lines/file rule)
```
src/
├── app.py              # Gtk.Application subclass, activate signal, window creation
├── window.py           # Gtk.ApplicationWindow, main UI layout, view switching
├── views/
│   ├── users.py        # Users panel: ColumnView + ToggleSwitch + badges
│   ├── allowlist.py    # Allowlist editor: domain list, add/remove, validation feedback
│   ├── log.py          # Blocked-attempts log: ColumnView + sorting/filtering + polling
│   └── status.py       # Status bar: health indicators, error display
├── models/
│   ├── cli_client.py   # Wrapper around Gio.Subprocess + pkexec, async call pattern
│   └── log_model.py    # Gio.ListStore for log data, sortable/filterable schema
├── utils/
│   ├── domain_validation.py  # Regex + validation rules, pure logic (testable)
│   ├── json_parser.py        # Parse CLI stdout, handle errors
│   └── formatting.py         # Time/domain/count display helpers
└── main.py             # Entry point: gi.require_version, app instantiation & run()
```

### Basic Skeleton
```python
# main.py
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from app import WebwardenAdminApp

if __name__ == '__main__':
    app = WebwardenAdminApp(application_id='com.example.webwarden-admin')
    exit_status = app.run(None)
    exit(exit_status)

# app.py
from gi.repository import Gtk, Gio

class WebwardenAdminApp(Gtk.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        window = Gtk.ApplicationWindow(application=self)
        window.set_default_size(1200, 700)
        window.set_title('Webwarden Admin')
        # Delegate UI build to window.py
        from window import MainWindow
        content = MainWindow()
        window.set_child(content)
        window.present()
```

**Source:** [GTK4 Application structure](https://pygobject.gnome.org/tutorials/gtk4/application.html).

---

## 2. Async Subprocess (CRITICAL: pkexec + Gio)

### Recommended Pattern: `Gio.Subprocess` + Async Callback (GTK-native)
**Why not threads or asyncio:** Callbacks integrate directly with GTK's GLib main loop (no marshal back to UI thread needed). asyncio is experimental with PyGObject; threads add complexity.

### Imperative Pattern (Callback-based, stable)
```python
# cli_client.py
from gi.repository import Gio, GLib, Gtk
import json

class WebwardenCLIClient:
    def run_command_async(self, args, on_complete):
        """
        args: list like ['log', '--json'] or ['toggle-block', '--user', 'alice', '--domain', 'evil.com']
        on_complete: callback(success: bool, stdout: str, stderr: str)
        """
        cmd = ['pkexec', 'webwarden'] + args
        try:
            proc = Gio.Subprocess.new(cmd, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as e:
            on_complete(False, "", f"Failed to spawn: {e}")
            return

        proc.communicate_utf8_async(
            stdin=None,
            cancellable=None,
            callback=self._on_subprocess_complete,
            user_data=(on_complete, cmd)
        )

    def _on_subprocess_complete(self, proc, res, user_data):
        on_complete, cmd = user_data
        try:
            success, stdout, stderr = proc.communicate_utf8_finish(res)
            exit_status = proc.get_exit_status()
            if exit_status == 0:
                on_complete(True, stdout, stderr)
            else:
                on_complete(False, stdout, f"Exit {exit_status}: {stderr}")
        except GLib.Error as e:
            on_complete(False, "", str(e))
```

### Async/Await Pattern (PyGObject 3.50+, experimental)
```python
async def run_command_async(self, args):
    """Awaitable version; requires GLibEventLoopPolicy."""
    cmd = ['pkexec', 'webwarden'] + args
    proc = Gio.Subprocess.new(cmd, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
    try:
        success, stdout, stderr = await proc.communicate_utf8_async()
        return (True, stdout, stderr)
    except GLib.Error as e:
        return (False, "", str(e))

# In main.py, start the app via Gtk.Application, not asyncio.run():
from gi.repository import Gio
GLib.set_event_loop_policy(GLib.GLibEventLoopPolicy())
# Then create app and call app.run()
```

**Tradeoff:** Async/await is cleaner but experimental; callback is verbose but rock-solid. **Recommendation: Use callback pattern for shipping code; async/await for exploration.**

### pkexec Integration Notes
- **Password dialog:** pkexec spawns its own password dialog asynchronously (via polkit agent). The subprocess call **blocks in the polkit agent**, not your app. The `communicate_utf8_async` callback fires **after** the user enters the password and polkit completes auth.
- **Caching:** After first auth, polkit caches credentials for ~15 min by default; subsequent `pkexec webwarden` calls won't re-prompt.
- **Failure handling:** If the user cancels the password dialog, `communicate_utf8_finish()` raises `GLib.Error` with code `Gio.IOErrorEnum.CANCELLED`. Catch and surface to UI gracefully.

**Source:** [Gio.Subprocess async API](https://docs.gtk.org/gio/method.Subprocess.communicate_utf8_async.html), [PyGObject async guide](https://pygobject.gnome.org/guide/asynchronous.html), [pkexec behavior](https://forums.linuxmint.com/viewtopic.php?t=298965).

---

## 3. Widget Stack: ColumnView + Models

### Modern GTK4 List Architecture
**ColumnView + Gio.ListStore + SortListModel + FilterListModel**

Instead of deprecated `Gtk.TreeView`, use the declarative model/factory/sorter/filter stack:
1. **Gio.ListStore** — in-memory list of objects (each row is a Python object).
2. **Gtk.SignalListItemFactory** — creates/binds cell widgets on demand.
3. **Gtk.SortListModel** — wraps ListStore, applies sorting via `Gtk.CustomSorter`.
4. **Gtk.FilterListModel** — wraps SortListModel, applies filtering via `Gtk.CustomFilter`.
5. **Gtk.ColumnView** — renders columns using factories and handles selection.

### Log Table Example (ColumnView + polling)
```python
# log.py
from gi.repository import Gtk, Gio, GLib
import json
from datetime import datetime

class LogRow:
    """Plain Python object to hold a row."""
    def __init__(self, timestamp, user, domain, count):
        self.timestamp = timestamp
        self.user = user
        self.domain = domain
        self.count = count

class LogPanel(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Create model
        self.store = Gio.ListStore.new(LogRow)

        # Create sorter (click column headers to sort)
        self.sorter = Gtk.CustomSorter()
        self.sorter.set_sort_func(self._sort_func)
        sort_model = Gtk.SortListModel.new(self.store, self.sorter)

        # Create filter
        self.filter = Gtk.CustomFilter()
        self.filter.set_filter_func(self._filter_func)
        filter_model = Gtk.FilterListModel.new(sort_model, self.filter)

        # Create column view
        self.view = Gtk.ColumnView.new(Gtk.SingleSelection.new(filter_model))
        
        # Add columns with factories
        self._add_column('Timestamp', 80, lambda obj: obj.timestamp)
        self._add_column('User', 100, lambda obj: obj.user)
        self._add_column('Domain', 200, lambda obj: obj.domain)
        self._add_column('Count', 60, lambda obj: str(obj.count))

        # Scrollable wrapper
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.view)
        self.append(scroll)

        # Search entry (connected to filter)
        search = Gtk.SearchEntry()
        search.connect('search-changed', self._on_search_changed)
        self.prepend(search)

        # Start polling
        self.poll_source = None
        self._start_polling()

    def _add_column(self, title, width, get_value):
        """Add a text column with a factory."""
        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', self._on_setup_cell)
        factory.connect('bind', self._on_bind_cell, get_value)

        col = Gtk.ColumnViewColumn.new(title, factory)
        col.set_fixed_width(width)
        self.view.append_column(col)

    def _on_setup_cell(self, factory, item):
        """Create the cell widget (once per cell type)."""
        label = Gtk.Label()
        item.set_child(label)

    def _on_bind_cell(self, factory, item, get_value):
        """Bind model data to cell widget (called when row scrolls into view)."""
        obj = item.get_item()
        label = item.get_child()
        label.set_text(get_value(obj))

    def _sort_func(self, a, b, user_data=None):
        """Return -1, 0, or 1 for sort order."""
        # Sort by timestamp descending
        if a.timestamp < b.timestamp:
            return 1
        elif a.timestamp > b.timestamp:
            return -1
        return 0

    def _filter_func(self, item, user_data=None):
        """Return True to show row, False to hide."""
        search_text = self.search_entry.get_text().lower()
        return (search_text in item.user.lower() or
                search_text in item.domain.lower())

    def _on_search_changed(self, entry):
        self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def _start_polling(self):
        """Poll webwarden log every 3 seconds."""
        self.poll_source = GLib.timeout_add_seconds(3, self._poll_log)

    def _poll_log(self):
        """Fetch log, update store. Return True to continue polling."""
        from cli_client import WebwardenCLIClient
        client = WebwardenCLIClient()
        client.run_command_async(['log', '--json'], self._on_log_fetched)
        return True  # Keep polling

    def _on_log_fetched(self, success, stdout, stderr):
        """Callback from async subprocess."""
        if not success:
            print(f"Log fetch failed: {stderr}")
            return
        
        try:
            data = json.loads(stdout)
            self.store.remove_all()
            for entry in data:  # Assume entry: {timestamp, user, domain, count}
                row = LogRow(
                    datetime.fromisoformat(entry['timestamp']),
                    entry['user'],
                    entry['domain'],
                    entry['count']
                )
                self.store.append(row)
        except json.JSONDecodeError:
            print("Failed to parse log JSON")

    def cleanup(self):
        """Stop polling on view destroy."""
        if self.poll_source:
            GLib.source_remove(self.poll_source)
```

### Users Panel (with toggle + badge)
```python
# users.py
from gi.repository import Gtk, Gio

class UserRow:
    def __init__(self, username, uid, locked):
        self.username = username
        self.uid = uid
        self.locked = locked  # bool

class UsersPanel(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        self.store = Gio.ListStore.new(UserRow)

        # Simple selection model (no sorting/filtering for users)
        selection = Gtk.SingleSelection.new(self.store)
        self.view = Gtk.ColumnView.new(selection)

        # Username column
        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', lambda f, item: item.set_child(Gtk.Label()))
        factory.connect('bind', lambda f, item: item.get_child().set_text(item.get_item().username))
        col = Gtk.ColumnViewColumn.new('User', factory)
        self.view.append_column(col)

        # Locked toggle column (custom widget)
        toggle_factory = Gtk.SignalListItemFactory()
        toggle_factory.connect('setup', self._setup_toggle_cell)
        toggle_factory.connect('bind', self._bind_toggle_cell)
        toggle_col = Gtk.ColumnViewColumn.new('Status', toggle_factory)
        self.view.append_column(toggle_col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.view)
        self.append(scroll)

        # Populate (in real app, fetch via CLI)
        self.store.append(UserRow('alice', 1000, False))
        self.store.append(UserRow('bob', 1001, True))

    def _setup_toggle_cell(self, factory, item):
        """Create a toggle switch + badge box."""
        box = Gtk.Box(spacing=6, orientation=Gtk.Orientation.HORIZONTAL)
        toggle = Gtk.Switch()
        toggle.set_active(item.get_item().locked)
        toggle.connect('notify::active', self._on_toggle_changed, item)
        box.append(toggle)

        # Sudo warning badge (if user.locked and not sudo-capable)
        badge = Gtk.Label()
        badge.set_css_classes(['badge', 'warning'])
        badge.set_text('⚠ sudo')
        box.append(badge)

        item.set_child(box)

    def _bind_toggle_cell(self, factory, item):
        """Update toggle state when row rebinds."""
        obj = item.get_item()
        box = item.get_child()
        toggle = box.get_first_child()
        toggle.set_active(obj.locked)

    def _on_toggle_changed(self, toggle, pspec, item):
        """User clicked toggle; invoke pkexec webwarden to change lock status."""
        obj = item.get_item()
        new_state = toggle.get_active()
        
        from cli_client import WebwardenCLIClient
        client = WebwardenCLIClient()
        args = ['lock' if new_state else 'unlock', '--user', obj.username]
        client.run_command_async(args, lambda s, o, e: self._on_toggle_complete(s, o, e, obj))

    def _on_toggle_complete(self, success, stdout, stderr, user):
        if not success:
            # Show error dialog
            dialog = Gtk.AlertDialog.new()
            dialog.set_message(f"Failed to toggle {user.username}")
            dialog.set_detail(stderr)
            dialog.choose(None, None, None)
            # Revert toggle in UI
            user.locked = not user.locked
            self.view.get_model().items_changed(0, 1, 1)
```

**Source:** [ColumnView, SortListModel, FilterListModel](https://docs.gtk.org/gtk4/class.ColumnView.html).

---

## 4. Polling & Auto-Refresh Pattern

### GLib.timeout_add_seconds (GTK-native, non-blocking)
```python
# In polling handler:
def _start_polling(self):
    # Schedule callback every 3 seconds
    self.poll_id = GLib.timeout_add_seconds(3, self._poll_callback)

def _poll_callback(self):
    """Invoked by main loop every 3 sec. Must return True to keep polling."""
    # Launch async subprocess; don't block here
    self.cli.run_command_async(['log', '--json'], self._on_result)
    return True  # Keep polling

def _on_result(self, success, stdout, stderr):
    # Update UI from callback (runs on main thread)
    self.update_view_from_log(stdout)

def cleanup(self):
    if self.poll_id:
        GLib.source_remove(self.poll_id)  # Stop polling
```

### Avoiding Overlapping Calls
```python
def _start_polling(self):
    self.poll_id = GLib.timeout_add_seconds(3, self._poll_callback)
    self.polling_in_flight = False

def _poll_callback(self):
    if self.polling_in_flight:
        return True  # Waiting for previous call to finish
    self.polling_in_flight = True
    self.cli.run_command_async(['log', '--json'], self._on_result)
    return True

def _on_result(self, success, stdout, stderr):
    self.polling_in_flight = False
    self.update_view(stdout)
```

### Pause on Window Unfocused (Optional)
```python
def __init__(self):
    # ... setup ...
    self.connect('focus-in-event', lambda w, e: self._resume_polling())
    self.connect('focus-out-event', lambda w, e: self._pause_polling())

def _pause_polling(self):
    if self.poll_id:
        GLib.source_remove(self.poll_id)
        self.poll_id = None

def _resume_polling(self):
    if not self.poll_id:
        self._start_polling()
```

**Source:** [GLib.timeout_add_seconds](https://docs.gtk.org/glib/func.timeout_add_seconds.html).

---

## 5. Packaging & Deployment on Linux Mint

### Required apt Packages
```bash
# On Mint/Ubuntu target system:
sudo apt install python3 python3-gi gir1.2-gtk-4.0
# Optional: if using adwaita (not recommended here)
# sudo apt install gir1.2-adw-1
```

### Venv vs System Site-Packages
**Avoid venvs for PyGObject apps.** PyGObject requires GObject introspection libraries (`.so` files, type stubs). Venvs isolate packages but GTK4 introspection won't find system libraries. **Solution:** Install PyGObject and deps system-wide, or document "run from system Python without venv."

### Directory Structure & Installation
```bash
# Source layout (git):
src/
  webwarden_admin/
    __init__.py
    main.py
    app.py
    window.py
    views/
    models/
    utils/

# Installation target (system):
/opt/webwarden-admin/
  ├── webwarden_admin/       # Copy src/webwarden_admin here
  └── __main__.py            # Or entry point script

# Entry script (/usr/local/bin/webwarden-admin):
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/webwarden-admin')
from webwarden_admin import main
main.main()
```

### Desktop Entry (.desktop file)
```ini
# /usr/share/applications/com.example.webwarden-admin.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=Webwarden Admin
Exec=/usr/local/bin/webwarden-admin
Icon=com.example.webwarden-admin
Categories=System;Administration;
Terminal=false
```

### Icon Installation
```bash
# Scalable icon (preferred)
mkdir -p /usr/share/icons/hicolor/scalable/apps/
cp webwarden-admin.svg /usr/share/icons/hicolor/scalable/apps/com.example.webwarden-admin.svg

# Raster fallbacks (128x128, 256x256)
mkdir -p /usr/share/icons/hicolor/{128x128,256x256}/apps/
cp webwarden-admin-128.png /usr/share/icons/hicolor/128x128/apps/com.example.webwarden-admin.png
```

### Setup.py / Pyproject.toml
```python
# setup.py (minimal)
from setuptools import setup, find_packages

setup(
    name='webwarden-admin',
    version='1.0.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    python_requires='>=3.9',
    entry_points={
        'console_scripts': [
            'webwarden-admin=webwarden_admin.main:main',
        ],
    },
)
```

**Note:** On Mint, PyGObject may not be in PyPI or may not build correctly. Recommend shipping the `.py` files directly in `/opt` and wrapping with a bash launcher, or providing a `.deb` package with GTK deps declared.

**Source:** [GTK4 Linux packaging](https://www.gtk.org/docs/installations/linux), [Desktop entry spec](https://toshiocp.github.io/Gtk4-tutorial/sec2.html).

---

## 6. Syntax Checking & Testing (Windows CI, No Display)

### Separating Logic from Widgets
**Critical:** Domain validation, CLI-arg building, JSON parsing, and log sorting are **pure logic**, testable without GTK/display.

```python
# utils/domain_validation.py — testable on Windows
import re

def validate_domain(domain: str) -> tuple[bool, str]:
    """
    Returns (is_valid, error_message).
    Pure logic, no GTK dependency.
    """
    if not domain.strip():
        return False, "Domain cannot be empty"
    if not re.match(r'^[a-z0-9.-]+\.[a-z]{2,}$', domain.lower()):
        return False, "Invalid domain format"
    if domain.count('.') < 1:
        return False, "Domain must have at least one dot"
    return True, ""

# tests/test_domain_validation.py — pytest on Windows
import pytest
from utils.domain_validation import validate_domain

@pytest.mark.parametrize("domain,expected_valid", [
    ("google.com", True),
    ("evil.co.uk", True),
    ("localhost", False),
    ("invalid", False),
    ("", False),
    ("invalid..com", False),
])
def test_domain_validation(domain, expected_valid):
    valid, _ = validate_domain(domain)
    assert valid == expected_valid

def test_domain_error_message():
    valid, msg = validate_domain("")
    assert not valid
    assert "empty" in msg.lower()
```

### Syntax Check (Windows CI, no GTK import)
```bash
# In CI (Windows):
python -m py_compile src/webwarden_admin/**/*.py  # Compile check
python -m pyflakes src/                           # Static analysis

# If GTK import fails on Windows, gate imports:
# In source files: only import Gtk/Gio inside functions that won't run on Windows,
# OR use conditional imports:
try:
    from gi.repository import Gtk
except ImportError:
    Gtk = None  # For CI on Windows
```

### Unit Tests (pytest, no display)
```bash
# tests/conftest.py — setup pytest
import os
os.environ['GDK_SCALE'] = '1'  # Avoid display issues

# tests/test_cli_client.py — test CLI logic without subprocess
from unittest.mock import patch, MagicMock
from models.cli_client import WebwardenCLIClient
import json

def test_cli_parse_log_output():
    """Test JSON parsing without invoking pkexec."""
    output = json.dumps([
        {"timestamp": "2024-06-24T10:00:00", "user": "alice", "domain": "evil.com", "count": 3}
    ])
    # Test that your log parsing handles this correctly
    # (move parsing logic into a separate, testable function)
    result = parse_log_json(output)
    assert len(result) == 1
    assert result[0]['user'] == 'alice'
```

### CI/CD Strategy
```yaml
# .github/workflows/lint-test.yml
name: Lint & Test
on: [push, pull_request]
jobs:
  lint:
    runs-on: windows-latest  # or ubuntu-latest for pure Python
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install pyflakes
      - run: python -m pyflakes src/
  test:
    runs-on: ubuntu-latest  # PyGObject CI must run on Linux
    steps:
      - uses: actions/checkout@v3
      - run: sudo apt install python3-gi gir1.2-gtk-4.0
      - run: pip install pytest
      - run: pytest tests/
```

**Source:** [pyflakes](https://pypi.org/project/pyflakes/), [pytest](https://docs.pytest.org/), [pytest parametrize](https://betterstack.com/community/guides/testing/pytest-guide/).

---

## 7. Domain Validation & Error Handling

### Input Validation (Text Entry)
```python
# views/allowlist.py
from utils.domain_validation import validate_domain

class AllowlistPanel(Gtk.Box):
    def __init__(self):
        # ...
        self.domain_entry = Gtk.Entry()
        self.domain_entry.connect('changed', self._on_domain_entry_changed)
        self.add_button = Gtk.Button(label='Add Domain')
        self.add_button.set_sensitive(False)
        self.add_button.connect('clicked', self._on_add_clicked)
        
        self.error_label = Gtk.Label()
        self.error_label.add_css_class('error')
        # ...

    def _on_domain_entry_changed(self, entry):
        domain = entry.get_text()
        valid, msg = validate_domain(domain)
        
        if not domain:
            self.error_label.set_text('')
            self.add_button.set_sensitive(False)
        elif valid:
            self.error_label.set_text('')
            self.add_button.set_sensitive(True)
        else:
            self.error_label.set_text(f"✗ {msg}")
            self.add_button.set_sensitive(False)

    def _on_add_clicked(self, button):
        domain = self.domain_entry.get_text()
        user = self.selected_user.username  # From parent context
        
        from cli_client import WebwardenCLIClient
        client = WebwardenCLIClient()
        args = ['add-domain', '--user', user, '--domain', domain]
        client.run_command_async(args, self._on_add_complete)

    def _on_add_complete(self, success, stdout, stderr):
        if success:
            self.domain_entry.set_text('')
            # Refresh list
            self._fetch_allowlist()
        else:
            self._show_error_dialog(stderr)

    def _show_error_dialog(self, message):
        dialog = Gtk.AlertDialog.new()
        dialog.set_message('Failed to add domain')
        dialog.set_detail(message)
        dialog.choose(None, None, None)
```

### Graceful CLI Degradation
```python
# In app initialization:
from cli_client import WebwardenCLIClient

client = WebwardenCLIClient()
client.run_command_async(['--version'], self._on_cli_check)

def _on_cli_check(self, success, stdout, stderr):
    if not success:
        # Show warning banner in main window
        banner = Gtk.InfoBar()
        banner.set_message_type(Gtk.MessageType.WARNING)
        banner.get_content_area().append(
            Gtk.Label(label='⚠ webwarden CLI not found. Features will be read-only.')
        )
        self.main_box.prepend(banner)
        # Disable mutation actions (toggle, add domain, etc.)
        self._disable_mutations()
```

---

## 8. Gotchas & Architectural Notes

| Issue | Solution |
|-------|----------|
| **Subprocess blocks on pkexec password dialog** | Expected behavior. The `communicate_utf8_async` callback fires *after* auth completes. Use a spinner/loading state in UI while waiting. |
| **PyGObject import fails on Windows** | Expected; GTK4 libs don't exist there. Separate pure logic tests (run on Windows) from widget tests (run on Linux CI). |
| **ColumnView is verbose; TreeView is deprecated** | Bite the bullet. ColumnView is the GTK4 way. Model/factory/sorter/filter wiring is complex but flexible. |
| **Adwaita themes don't match Cinnamon** | Skip libadwaita. Use plain GTK4 + manual CSS for badges/errors. |
| **Polling overlaps (2 log fetches running)** | Guard with `self.polling_in_flight` flag. Or use `Gio.Cancellable` to cancel prior call before launching new one. |
| **No display on Windows CI** | Use `pytest` on logic; GTK widget tests need `xvfb` (Linux CI only) or skip them for Windows. |
| **venv breaks PyGObject introspection** | Use system Python + system packages. Document "do not use venv" in README. |

---

## 9. Code Snippet Checklist

- [x] `Gtk.Application` + `activate` signal
- [x] `Gio.Subprocess.communicate_utf8_async()` with callback
- [x] `Gio.ListStore` + `Gtk.SignalListItemFactory` (ColumnView setup)
- [x] `Gtk.SortListModel` + `Gtk.CustomSorter`
- [x] `Gtk.FilterListModel` + `Gtk.CustomFilter`
- [x] `GLib.timeout_add_seconds()` + polling guard
- [x] Domain validation (pure logic, testable)
- [x] Error dialog (`Gtk.AlertDialog`)
- [x] Toggle switch + badge combo
- [x] .desktop entry + icon install
- [x] pytest on logic; integration tests on Linux CI

---

## Unresolved Questions

1. **Adwaita on Cinnamon:** Exact theme/integration behavior untested; documentation suggests GNOME-primary but doesn't explicitly forbid Cinnamon. Recommend proof-of-concept on target system.
2. **pkexec credential caching with rapid calls:** Does polkit cache credentials across multiple `pkexec` invocations in the same session? Behavior may vary by system policy. Test on target Mint install.
3. **ColumnView keyboard navigation:** How to enable standard tree nav (arrow keys, Home/End)? Not covered in docs; may require custom event handlers or selection model config.
4. **JSON parse performance:** For large log tables (10k+ rows), is Gio.ListStore performant? Or use pagination/virtual scrolling? No benchmarks found.
5. **CSS class names for badges/errors:** GTK4 doesn't ship default `.badge` or `.error` classes. Must define in app CSS. Where to load app.css in PyGObject? Via `Gtk.CssProvider` + `Gtk.StyleContext.add_provider_for_display()` or resource bundles?
6. **Desktop file execution from Cinnamon menu:** Will Cinnamon correctly execute `Exec=/usr/local/bin/webwarden-admin`? Behavior untested on real Mint system.

---

## Sources Cited

- [PyGObject Official Docs](https://pygobject.gnome.org/)
- [GTK4 Application Guide](https://pygobject.gnome.org/tutorials/gtk4/application.html)
- [Gio.Subprocess.communicate_utf8_async API](https://docs.gtk.org/gio/method.Subprocess.communicate_utf8_async.html)
- [PyGObject Asynchronous Programming](https://pygobject.gnome.org/guide/asynchronous.html)
- [GTK4 ColumnView Documentation](https://docs.gtk.org/gtk4/class.ColumnView.html)
- [GTK4 SortListModel & FilterListModel](https://docs.gtk.org/gtk4/class.SortListModel.html)
- [Adwaita (libadwaita) for PyGObject](https://pygobject.gnome.org/tutorials/libadwaita/application.html)
- [GLib.timeout_add_seconds Reference](https://docs.gtk.org/glib/func.timeout_add_seconds.html)
- [pytest Documentation](https://docs.pytest.org/)
- [GTK4 Linux Installation & Packaging](https://www.gtk.org/docs/installations/linux)
