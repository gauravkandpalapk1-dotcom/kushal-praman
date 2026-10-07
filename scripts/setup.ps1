# Kaushal Pramaan backend setup (Windows PowerShell).
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 [-Dev]
# Creates .venv (Python 3.13), installs requirements, writes .env if missing,
# applies Alembic migrations and seeds demo data (idempotent).
param([switch]$Dev)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment (.venv, Python 3.13)..."
    py -3.13 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.13 not found. Install it or edit this script." }
}
$Py = Join-Path $Root ".venv\Scripts\python.exe"

& $Py -m pip install --upgrade pip
$req = if ($Dev) { "backend\requirements-dev.txt" } else { "backend\requirements.txt" }
& $Py -m pip install -r $req
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

if (-not (Test-Path ".env")) {
    $secret = & $Py -c "import secrets; print(secrets.token_urlsafe(48))"
    (Get-Content -Encoding utf8 ".env.example") -replace "^JWT_SECRET=.*", "JWT_SECRET=$secret" | Set-Content -Encoding utf8 ".env"
    Write-Host "Wrote .env with a random JWT_SECRET."
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "ffmpeg not found on PATH: segmentation and media probing will be unavailable."
}

& $Py -m alembic -c backend\alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw "alembic upgrade failed" }
& $Py -m backend.app.services.seed
if ($LASTEXITCODE -ne 0) { throw "seed failed" }

Write-Host ""
Write-Host "Setup complete. Start the server with: powershell -ExecutionPolicy Bypass -File scripts\run.ps1"
Write-Host "Demo logins: admin@kp.demo / Admin@2026, raj@kp.demo / Candidate@2026, a07@kp.demo, a12@kp.demo / Assessor@2026"
