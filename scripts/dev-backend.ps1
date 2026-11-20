$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = $root
& "$root\.venv\Scripts\uvicorn.exe" app.main:app --app-dir "$root\backend" --reload --host 127.0.0.1 --port 8000
