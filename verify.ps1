# verify.ps1 — syntax check for every Python file in this project.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$fail = 0

Get-ChildItem -Path $root -Filter *.py -File | ForEach-Object {
  python -m py_compile $_.FullName
  if ($LASTEXITCODE -ne 0) { Write-Host "SYNTAX FAIL: $($_.Name)"; $fail = 1 }
  else { Write-Host "ok  $($_.Name)" }
}

if ($fail -ne 0) { Write-Host 'VERIFY: FAILED'; exit 1 }
Write-Host 'VERIFY: PASSED'; exit 0
