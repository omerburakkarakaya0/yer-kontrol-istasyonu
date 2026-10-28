$ErrorActionPreference = "Stop"

$gstBin = "C:\Program Files\gstreamer\1.0\msvc_x86_64\bin"

if (-not (Test-Path $gstBin)) {
    throw "GStreamer bin directory not found: $gstBin"
}

$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = @()
if ($currentPath) {
    $parts = $currentPath.Split(";") | Where-Object { $_ }
}

if ($parts -contains $gstBin) {
    Write-Host "GStreamer is already in the user PATH."
    return
}

$newPath = (($parts + $gstBin) -join ";")
[Environment]::SetEnvironmentVariable("Path", $newPath, "User")
Write-Host "Added GStreamer to user PATH: $gstBin"
Write-Host "Close this PowerShell window and open a new one, then run: gst-launch-1.0 --version"
