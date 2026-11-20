$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\apps\web"
npm run dev
