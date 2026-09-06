[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

$StudioRoot = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $StudioRoot 'backend'
$Frontend = Join-Path $StudioRoot 'frontend'
$BackendVenv = Join-Path $Backend '.venv'
$FrontendModules = Join-Path $Frontend 'node_modules'
$UiUrl = 'http://127.0.0.1:5173'
$ApiUrl = 'http://127.0.0.1:8765'

function Require-Command {
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [string]$InstallHint
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required command '$Name' was not found. $InstallHint"
    }
    return $command
}

$Pwsh = Require-Command -Name 'pwsh' -InstallHint 'Install PowerShell 7 or later.'
$PythonCommand = Require-Command -Name 'python' -InstallHint 'Install Python and make sure python.exe is on PATH.'
$null = Require-Command -Name 'node' -InstallHint 'Install a current Node.js release.'
$null = Require-Command -Name 'npm' -InstallHint 'Install npm with Node.js.'

if (-not (Test-Path $Backend)) {
    throw "Backend directory was not found: $Backend"
}
if (-not (Test-Path (Join-Path $Frontend 'package.json'))) {
    throw "Frontend package.json was not found: $Frontend"
}

if (-not (Test-Path $BackendVenv)) {
    Write-Host 'Creating backend virtual environment...'
    & $PythonCommand.Source -m venv $BackendVenv
}

$Python = Join-Path $BackendVenv 'Scripts\python.exe'
if (-not (Test-Path $Python)) {
    throw "Backend virtual-environment Python was not found: $Python"
}

if (-not $SkipInstall) {
    Write-Host 'Installing/updating Fabric Ops Studio backend...'
    & $Python -m pip install -e $Backend

    if (-not (Test-Path $FrontendModules)) {
        Write-Host 'Installing frontend dependencies...'
        Push-Location $Frontend
        try {
            npm install
        }
        finally {
            Pop-Location
        }
    }
}
elseif (-not (Test-Path $FrontendModules)) {
    throw "-SkipInstall was used but frontend dependencies are missing: $FrontendModules"
}

$escapedBackend = $Backend.Replace("'", "''")
$escapedFrontend = $Frontend.Replace("'", "''")
$escapedPython = $Python.Replace("'", "''")

Write-Host "Starting Fabric Ops Studio API on $ApiUrl"
$backendCommand = "Set-Location '$escapedBackend'; &'$escapedPython' -m uvicorn app.main:app --host 127.0.0.1 --port 8765"
Start-Process $Pwsh.Source -ArgumentList '-NoExit', '-Command', $backendCommand | Out-Null

Write-Host "Starting Fabric Ops Studio UI on $UiUrl"
$frontendCommand = "Set-Location '$escapedFrontend'; npm run dev"
Start-Process $Pwsh.Source -ArgumentList '-NoExit', '-Command', $frontendCommand | Out-Null

if (-not $NoBrowser) {
    Start-Sleep -Seconds 2
    Start-Process $UiUrl | Out-Null
}

Write-Host ''
Write-Host 'Fabric Ops Studio processes were launched in separate PowerShell 7 windows.'
Write-Host "UI:  $UiUrl"
Write-Host "API: $ApiUrl"
Write-Host 'Use the Diagnostics page after launch to verify upstream module and optional-tool readiness.'
