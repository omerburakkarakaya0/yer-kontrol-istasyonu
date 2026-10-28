# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets'), ('resources', 'resources'), ('third_party\\uavlogviewer\\dist', 'third_party\\uavlogviewer\\dist'), ('communication_core\\config', 'communication_core\\config'), ('communication_core\\build_nmake\\communication_core_service.exe', 'communication_core\\build_nmake'), ('backend_cpp\\build_nmake\\telemetry_bridge.exe', 'backend_cpp\\build_nmake')]
binaries = []
hiddenimports = ['pymavlink.dialects.v20.ardupilotmega', 'pymavlink.dialects.v10.ardupilotmega']
tmp_ret = collect_all('PyQt5')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('PyQtWebEngine')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BLACK_BOX_Yer_Kontrol_Istasyonu',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BLACK_BOX_Yer_Kontrol_Istasyonu',
)
