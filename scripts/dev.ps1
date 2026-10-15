# Windows quick start (no Docker needed):   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
# Creates a virtual environment OUTSIDE the OneDrive-synced folder, installs dependencies once,
# then starts the backend (direct mode: simulator built in) and the React dev server.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $env:USERPROFILE ".venvs\oee"
$py = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Creating virtual environment in $venv ..."
    python -m venv $venv
    & $py -m pip install --quiet -r (Join-Path $root "backend\requirements-dev.txt")
}
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "Installing frontend packages ..."
    Push-Location (Join-Path $root "frontend"); npm install; Pop-Location
}
if (-not (Test-Path (Join-Path $root ".env"))) { Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env") }

Write-Host "Backend  -> http://localhost:8000/docs"
Write-Host "Frontend -> http://localhost:5173"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; & '$py' -m uvicorn app.main:app --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev"
Start-Sleep 6
Start-Process "http://localhost:5173"
