param(
    [switch]$CreateShortcut
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$Python = "python"
if (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe") {
    $Python = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
}

Write-Host "Using Python: $Python"

Write-Host "Ensuring PyInstaller is installed..."
& $Python -m pip install --upgrade pyinstaller

if (-not (Test-Path "third_party\uavlogviewer\dist")) {
    throw "third_party\uavlogviewer\dist bulunamadi. Once uavlogviewer icin npm run build calistirin."
}

if (-not (Test-Path "communication_core\build_nmake\communication_core_service.exe")) {
    throw "communication_core\build_nmake\communication_core_service.exe bulunamadi."
}

if (-not (Test-Path "backend_cpp\build_nmake\telemetry_bridge.exe")) {
    throw "backend_cpp\build_nmake\telemetry_bridge.exe bulunamadi."
}

$AddData = @(
    "assets;assets",
    "resources;resources",
    "third_party\uavlogviewer\dist;third_party\uavlogviewer\dist",
    "communication_core\config;communication_core\config",
    "communication_core\build_nmake\communication_core_service.exe;communication_core\build_nmake",
    "backend_cpp\build_nmake\telemetry_bridge.exe;backend_cpp\build_nmake"
)

$Args = @(
    "--noconfirm",
    "--clean",
    "--onedir",
    "--windowed",
    "--name", "BLACK_BOX_Yer_Kontrol_Istasyonu",
    "--collect-all", "PyQt5",
    "--collect-all", "PyQtWebEngine",
    "--hidden-import", "pymavlink.dialects.v20.ardupilotmega",
    "--hidden-import", "pymavlink.dialects.v10.ardupilotmega"
)

foreach ($Item in $AddData) {
    $Args += @("--add-data", $Item)
}

$Args += "main.py"

Write-Host "Building desktop app..."
& $Python -m PyInstaller @Args

$Exe = Join-Path $ProjectRoot "dist\BLACK_BOX_Yer_Kontrol_Istasyonu\BLACK_BOX_Yer_Kontrol_Istasyonu.exe"
if (-not (Test-Path $Exe)) {
    throw "Build bitti ama exe bulunamadi: $Exe"
}

Write-Host ""
Write-Host "Build tamam:"
Write-Host $Exe

if ($CreateShortcut) {
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $ShortcutPath = Join-Path $Desktop "BLACK BOX Yer Kontrol Istasyonu.lnk"
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $Exe
    $Shortcut.WorkingDirectory = Split-Path $Exe
    $Shortcut.IconLocation = $Exe
    $Shortcut.Save()
    Write-Host "Masaustu kisayolu olusturuldu:"
    Write-Host $ShortcutPath
}
