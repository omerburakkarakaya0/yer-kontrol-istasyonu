param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$MockDir = Join-Path $Root "communication_core\mock_server"
$LogDir = Join-Path $Root "communication_core\logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

Start-Process `
    -FilePath "python" `
    -ArgumentList @("-m", "uvicorn", "main:app", "--host", $HostAddress, "--port", "$Port") `
    -WorkingDirectory $MockDir `
    -RedirectStandardOutput (Join-Path $LogDir "mock_server.out.log") `
    -RedirectStandardError (Join-Path $LogDir "mock_server.err.log") `
    -WindowStyle Hidden

Write-Host "Mock competition server started at http://$HostAddress`:$Port"
