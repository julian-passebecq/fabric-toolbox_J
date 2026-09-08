[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$SkipInstall,
    [switch]$CheckOnly,
    [switch]$SmokeTest,
    [int]$ApiPort = 8765,
    [int]$UiPort = 5173,
    [string]$PythonPath = 'python'
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne 7) { throw 'Studio requires PowerShell 7' }
$LauncherPath = Join-Path $PSScriptRoot 'launcher.py'
$LauncherArgs = @($LauncherPath, '--api-port', "$ApiPort", '--ui-port', "$UiPort")
if ($NoBrowser) { $LauncherArgs += '--no-browser' }
if ($SkipInstall) { $LauncherArgs += '--skip-install' }
if ($CheckOnly) { $LauncherArgs += '--check-only' }
if ($SmokeTest) { $LauncherArgs += '--smoke-test' }
& $PythonPath @LauncherArgs
if ($LASTEXITCODE -ne 0) { throw "Studio launcher failed with exit code $LASTEXITCODE" }
