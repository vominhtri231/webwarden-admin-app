# Syntax-check every Python source (py_compile never imports gi, so GTK modules
# are safe to check on Windows) and then run the test suite.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Get-ChildItem -Path $root -Recurse -Filter *.py |
    Where-Object { $_.FullName -notmatch '[\\/](\.git|\.claude|__pycache__)[\\/]' } |
    ForEach-Object { python -m py_compile $_.FullName }
Write-Host "py_compile OK"
python -m pytest
