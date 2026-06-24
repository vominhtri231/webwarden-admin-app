"""Guard: the backend and GUI copies of validation.py must stay byte-identical."""
import os


def test_validation_copies_identical():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    backend = os.path.join(root, "backend", "webwarden_cli", "validation.py")
    gui = os.path.join(root, "gui", "webwarden_admin", "validation.py")
    with open(backend, "rb") as f:
        b = f.read()
    with open(gui, "rb") as f:
        g = f.read()
    assert b == g, "backend/webwarden_cli/validation.py and gui/webwarden_admin/validation.py have drifted"
