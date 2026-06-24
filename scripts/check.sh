#!/usr/bin/env bash
# Syntax-check every Python source then run the test suite.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
find "$root" -name '*.py' \
    -not -path '*/.git/*' -not -path '*/.claude/*' -not -path '*/__pycache__/*' -print0 \
    | xargs -0 -n1 python3 -m py_compile
echo "py_compile OK"
python3 -m pytest
