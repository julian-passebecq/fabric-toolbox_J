$ErrorActionPreference = 'Stop'

$StudioRoot = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $StudioRoot 'backend'
$Frontend = Join-Path $StudioRoot 'frontend'

if (-not (Test-Path (Join-Path $Backend '.venv'))) {
    Write-Host 'Creating backend virtual environment...'
    python -m venv (Join-Path $Backend '.venv')
}

$Python = Join-Path $Backend '.venv\Scripts\python.exe'
& $Python -m pip install -e $Backend

Write-Host 'Starting Fabric Ops Studio API on http://127.0.0.1:8765'
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$Backend'; &'$Python' -m uvicorn app.main:app --host 127.0.0.1 --port 8765"

if (-not (Test-Path (Join-Path $StudioRoot 'node_modules'))) {
    Write-Host 'Installing frontend dependencies...'
    Push-Location $StudioRoot
    npm install
    Pop-Location
}

Write-Host 'Starting Fabric Ops Studio UI on http://127.0.0.1:5173'
Set-Location $Frontend
npm run dev
