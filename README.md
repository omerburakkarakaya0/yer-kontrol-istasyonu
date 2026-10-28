# Yer İstasyonu - Teknofest İHA

Modern, thread-safe yer istasyonu uygulaması. PyQt5 ile geliştirilmiştir.

## Özellikler

### 1. Rota Çizme Sistemi
- Takeoff, Waypoint, Do Jump, RTL, Do Land Start, Land item'ları
- Waypoint parametre düzenleme
- Mission item tablosu
- Harita üzerinde rota çizimi (placeholder)

### 2. Sistem Mimarisi
- **Thread-safe**: Telemetri ve video ayrı thread'lerde çalışır
- **Throttled UI Updates**: UI güncellemeleri throttle edilir (çökme önleme)
- **Signal/Slot Pattern**: Thread'ler arası güvenli iletişim

### 3. Telemetri
- Altitude, Speed, Battery
- Pitch, Roll, Yaw
- GPS Lat/Lon
- Bağlantı durumu göstergesi
- Uyarı sistemi (düşük batarya vb.)

### 4. Kamera
- Video akışı gösterimi
- Demo için dosyadan video oynatma desteği
- Gerçek kamera entegrasyonu için hazır mimari

### 5. Arayüz
- Modern, sade, koyu tema
- Sekmeli yapı: Flight, Mission, Camera, Logs
- Responsive layout

## Kurulum

### Gereksinimler
- Python 3.7+
- PyQt5
- OpenCV (cv2)

### Adımlar

1. Bağımlılıkları yükleyin:
```bash
pip install -r requirements.txt
```

2. Uygulamayı çalıştırın:
```bash
python main.py
```

## Proje Yapısı

```
Yer Istasyonu Tasarimi/
├── main.py                 # Ana giriş noktası
├── config.py               # Konfigürasyon
├── requirements.txt         # Python bağımlılıkları
├── ui/                     # UI bileşenleri
│   ├── main_window.py      # Ana pencere
│   ├── tabs/               # Sekme sayfaları
│   │   ├── flight_tab.py
│   │   ├── mission_tab.py
│   │   ├── camera_tab.py
│   │   └── logs_tab.py
│   └── widgets/            # Yeniden kullanılabilir widget'lar
│       ├── telemetry_widget.py
│       ├── map_widget.py
│       ├── mission_table.py
│       └── video_widget.py
├── core/                   # Core mantık
│   ├── telemetry_worker.py # Telemetri worker thread
│   ├── video_worker.py     # Video worker thread
│   └── mission_manager.py  # Mission yönetimi
├── models/                 # Veri modelleri
│   ├── telemetry.py
│   └── mission_item.py
├── utils/                  # Yardımcı fonksiyonlar
│   └── throttled_update.py # UI update throttling
└── resources/              # Kaynaklar
    └── styles.qss          # Stil dosyası
```

## Mimari Açıklama

### Thread Mimarisi

**Neden Thread Kullanıyoruz?**
- Telemetri ve video sürekli veri üretir
- Bu işlemler UI thread'ini bloklayabilir
- Ayrı thread'lerde çalıştırarak UI akıcı kalır

**Thread Güvenliği:**
- PyQt5'in Signal/Slot mekanizması thread-safe
- Worker thread'ler signal gönderir
- UI thread signal'leri alır ve güncelleme yapar
- Doğrudan UI güncellemesi yapılmaz (thread-safe değil!)

### Throttled Updates

**Neden Throttling?**
- Telemetri çok sık gelirse (örn: 100Hz) UI donabilir
- Her güncellemede render maliyeti var
- Throttling ile belirli aralıklarla güncelleme yapılır

**Nasıl Çalışır?**
- `ThrottledUpdater` sınıfı kullanılır
- İlk güncelleme hemen yapılır
- Sonraki güncellemeler belirli aralıklarla yapılır (örn: 100ms)
- UI akıcı kalır, CPU kullanımı azalır

### Modüler Yapı

**Neden Modüler?**
- Kod tekrarını önler
- Bakımı kolaylaştırır
- Test edilebilirliği artırır
- Takım çalışmasına uygundur

**Modüller:**
- `models/`: Veri yapıları (TelemetryData, MissionItem)
- `core/`: İş mantığı (worker thread'ler, mission manager)
- `ui/`: Kullanıcı arayüzü (widget'lar, tab'lar)
- `utils/`: Yardımcı fonksiyonlar

## Kullanım

### Flight Tab
- Canlı telemetri verilerini gösterir
- Harita üzerinde mevcut konumu gösterir
- Video akışını gösterir

### Mission Tab
- Rota planlama yapılır
- Mission item'ları eklenir/düzenlenir/silinir
- Harita üzerinde rota çizilir

### Camera Tab
- Video akışını gösterir
- Kamera kontrolleri (ileride)

### Logs Tab
- Sistem loglarını gösterir
- Bağlantı durumlarını gösterir
- Hata mesajlarını gösterir

## Demo Modu

Şu anda uygulama demo modunda çalışmaktadır:
- Telemetri verileri simüle edilir
- Video varsayılan kameradan okunur (yoksa siyah ekran)
- Mission item'ları eklenebilir ve düzenlenebilir

## Geliştirme Planı

### Kısa Vadeli
- [ ] Gerçek harita entegrasyonu (Leaflet/QWebEngine)
- [ ] Gerçek telemetri kaynağı entegrasyonu (Serial/UDP)
- [ ] Gerçek video akışı entegrasyonu (RTSP/UDP)
- [ ] Mission item'larını kaydetme/yükleme (JSON)

### Orta Vadeli
- [ ] Video kayıt özelliği
- [ ] Telemetri loglama
- [ ] Mission simülasyonu
- [ ] Gelişmiş uyarı sistemi

### Uzun Vadeli
- [ ] Çoklu İHA desteği
- [ ] 3D görselleştirme
- [ ] Gelişmiş analitik
- [ ] Web arayüzü

## Notlar

- Bu uygulama eğitim amaçlı geliştirilmiştir
- Production kullanımı için ek güvenlik ve hata yönetimi gerekir
- Thread yönetimi dikkatli yapılmalıdır
- UI güncellemeleri her zaman UI thread'inde yapılmalıdır

## Lisans

Bu proje Teknofest İHA yarışması için geliştirilmiştir.


## Offline MBTiles Harita

Mission ekranı artık `assets/maps/mission_map.mbtiles` dosyasını okuyacak şekilde hazırlandı.
Harita üzerinde:
- mouse wheel ile smooth zoom
- sürükleyerek pan
- çift tık ile waypoint ekleme
- rota çizgisi
- grid overlay
özellikleri bulunur.

## Telemetry Backend

Bu surumde telemetri okuma katmani UI'dan ayrildi:

- `models/telemetry.py`: Standart `TelemetryData` modeli
- `backend/telemetry/base.py`: Ortak backend arayuzu
- `backend/telemetry/simulation_backend.py`: Test/sunum icin simule veri kaynagi
- `backend/telemetry/mavlink_backend.py`: Serial/UDP/TCP MAVLink okuyucu
- `backend/telemetry/manager.py`: Backend secimi ve yasam dongusu
- `core/telemetry_worker.py`: PyQt QThread icinde manager'i calistiran worker

### Kurulum

```bash
pip install -r requirements.txt
```

MAVLink icin `pymavlink` gereklidir. Gercek baglanti yoksa uygulama Demo/Simulation backend ile calismaya devam eder.

### Simulasyon modunda calistirma

```bash
python main.py
```

Uygulama acildiginda varsayilan olarak Demo telemetri backend'i baslar. Flight ekraninda Type alanini `Demo` secip Connect ile yeniden baslatabilirsiniz.

### UDP MAVLink ile calistirma

Flight ekraninda:

- Type: `UDP`
- Target: `udp:0.0.0.0:14550` veya sadece `14550`
- Baud: bos

Sonra `Connect` butonuna basin. Heartbeat 5 saniye icinde gelmezse UI donmadan hata Logs ekranina yazilir.

### Serial MAVLink ile calistirma

Flight ekraninda:

- Type: `Serial`
- Target: `COM3` gibi port adi
- Baud: `57600` veya autopilot ayarinizdaki baudrate

Sonra `Connect` butonuna basin.

### TCP MAVLink

TCP opsiyonel olarak desteklenir:

- Type: `TCP`
- Target: `127.0.0.1:5760` veya `tcp:127.0.0.1:5760`

### Smoke test

```bash
python -m unittest tests.test_telemetry_backend
```

Bu testler:

- Simulasyon backend veri uretiyor mu?
- `TelemetryManager` Demo backend'e gecebiliyor mu?
- `TelemetryWorker` baslatilip durdurulabiliyor mu?
