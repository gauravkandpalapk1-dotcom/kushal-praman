# Start the Kaushal Pramaan backend (serves the API, and the static UI if frontend/out exists).
#   powershell -ExecutionPolicy Bypass -File scripts\run.ps1 [-Port 8000] [-Reload]
param([int]$Port = 8000, [switch]$Reload)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "Run scripts\setup.ps1 first." }

Write-Host "Kaushal Pramaan on http://localhost:$Port  (API docs: http://localhost:$Port/api/docs)"
$uvArgs = @("-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "$Port")
if ($Reload) { $uvArgs += @("--reload", "--reload-dir", "backend", "--reload-dir", "ai") }
& $Py @uvArgs
