"""Pytest bootstrap: make the backend, GUI, and shared-fixture packages importable.

Adds the repo root (for ``testkit``), ``backend`` (for ``webwarden_cli``), and
``gui`` (for ``webwarden_admin``) to sys.path so tests can import them without an
installed package. Loaded automatically by pytest from the rootdir.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (ROOT, os.path.join(ROOT, "backend"), os.path.join(ROOT, "gui")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
