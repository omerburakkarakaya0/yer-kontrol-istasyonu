param(
    [string]$ConfigPath = "communication_core\config\config.yaml"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Exe = Join-Path $Root "communication_core\build_nmake\communication_core_service.exe"
$Config = Join-Path $Root $ConfigPath
$WorkDir = Join-Path $Root "communication_core"
$LogDir = Join-Path $WorkDir "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

if (-not (Test-Path $Exe)) {
    throw "communication_core_service.exe not found. Build communication_core first."
}
if (-not (Test-Path $Config)) {
    throw "Config not found: $Config"
}

Start-Process `
    -FilePath $Exe `
    -ArgumentList @($Config) `
    -WorkingDirectory $WorkDir `
    -RedirectStandardOutput (Join-Path $LogDir "service.stdout.log") `
    -RedirectStandardError (Join-Path $LogDir "service.stderr.log") `
    -WindowStyle Hidden

Write-Host "Communication Core started. Health: http://127.0.0.1:8090/healthz"
Write-Host "Communication Core status: http://127.0.0.1:8090/status"
