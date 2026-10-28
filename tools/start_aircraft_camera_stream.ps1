param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8092,
    [string]$Source = "0",
    [int]$Width = 640,
    [int]$Height = 480,
    [double]$Fps = 15,
    [int]$Quality = 70
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Streamer = Join-Path $PSScriptRoot "aircraft_camera_stream.py"

python $Streamer `
    --host $HostAddress `
    --port $Port `
    --source $Source `
    --width $Width `
    --height $Height `
    --fps $Fps `
    --quality $Quality
