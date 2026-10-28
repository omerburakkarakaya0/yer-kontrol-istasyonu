# Desktop Build

Bu proje Windows icin PyInstaller ile masaustu uygulamasi olarak paketlenir.

## Build

PowerShell'i proje klasorunde acin ve calistirin:

```powershell
& ".\tools\build_desktop_app.ps1"
```

Masaustu kisayolu da olussun isterseniz:

```powershell
& ".\tools\build_desktop_app.ps1" -CreateShortcut
```

Build tamamlaninca uygulama burada olusur:

```text
dist\BLACK_BOX_Yer_Kontrol_Istasyonu\BLACK_BOX_Yer_Kontrol_Istasyonu.exe
```

Bu klasoru komple tasiyin. Sadece `.exe` dosyasini tek basina tasimayin; harita,
model, log viewer ve haberlesme servis dosyalari ayni paket klasorunde gerekir.

## Notlar

- `third_party\uavlogviewer\dist` yoksa once UAV log viewer build edilmelidir.
- `communication_core\build_nmake\communication_core_service.exe` paket icine alinir.
- `backend_cpp\build_nmake\telemetry_bridge.exe` paket icine alinir.
- Kamera icin GStreamer veya FFmpeg sistemde kurulu olmaya devam etmelidir.
