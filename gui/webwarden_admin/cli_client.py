"""Async webwarden/pkexec client. Runs the CLI off the UI thread.

Read commands run ``webwarden`` directly; mutations are wrapped in ``pkexec`` so
Polkit authenticates the admin (its password dialog blocks inside polkit, not the
UI loop). Results are JSON-parsed; non-zero exits surface stderr. A per-key busy
guard prevents overlapping calls (e.g. stacked polls).
"""
import json
import shutil

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib  # noqa: E402

from . import cli_args  # noqa: E402

PKEXEC = "pkexec"


def backend_available():
    return shutil.which(cli_args.WEBWARDEN) is not None


class CliClient:
    def __init__(self):
        self._busy = set()

    def run_json(self, argv, on_done, on_error, key=None):
        """Run a read command; on_done receives parsed JSON."""
        self._spawn(argv, on_done, on_error, parse_json=True, key=key)

    def run_mutation(self, argv, on_done, on_error, key=None):
        """Run a mutation through pkexec; on_done receives stdout text."""
        self._spawn([PKEXEC, *argv], on_done, on_error, parse_json=False, key=key)

    # internals --------------------------------------------------------------
    def _spawn(self, argv, on_done, on_error, parse_json, key):
        if key is not None:
            if key in self._busy:
                return
            self._busy.add(key)
        try:
            proc = Gio.Subprocess.new(
                argv,
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as e:
            self._release(key)
            on_error(str(e))
            return
        proc.communicate_utf8_async(
            None, None, self._on_finish, (on_done, on_error, parse_json, key))

    def _on_finish(self, proc, result, data):
        on_done, on_error, parse_json, key = data
        self._release(key)
        try:
            _ok, stdout, stderr = proc.communicate_utf8_finish(result)
        except GLib.Error as e:
            on_error(str(e))
            return
        if proc.get_exit_status() != 0:
            on_error((stderr or "command failed").strip())
            return
        if not parse_json:
            on_done((stdout or "").strip())
            return
        try:
            on_done(json.loads(stdout or "null"))
        except ValueError as e:
            on_error("invalid JSON from backend: " + str(e))

    def _release(self, key):
        if key is not None:
            self._busy.discard(key)
