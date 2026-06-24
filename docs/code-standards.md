# Code Standards

## Language & layout
- Python 3 for both backend CLI and GUI. `snake_case` modules/functions (Python convention).
- Keep each source file under ~200 lines; split by concern (one module = one responsibility).
- Backend package: `webwarden_cli`. GUI package: `webwarden_admin`. No runtime import between them.

## Security (non-negotiable)
- All external commands run via **argv arrays**, never string concatenation / shell.
- Domain input is **normalized then validated** (`validation.py`) before reaching argv.
- Hardcode tool paths (`/usr/sbin/nft`, etc.) — `pkexec` scrubs `PATH`.
- The GUI never writes `/etc/webwarden`; all mutations go through the CLI via `pkexec`.

## Reliability
- Atomic file writes (temp file + `os.replace`).
- Mutating CLI commands are idempotent and exit non-zero with a clear stderr message on error.
- `apply` is fail-closed: validate (`nft -c -f`, `dnsmasq --test`) before tearing down protection.

## Testing
- Separate pure logic from GTK/kernel side-effects so logic is unit-testable on Windows.
- GTK is never imported in modules covered by unit tests.
- `scripts/check.ps1` (Windows) / `check.sh` (Linux): `py_compile` all sources + `pytest`.
- No failing test is ignored to make a build pass.
