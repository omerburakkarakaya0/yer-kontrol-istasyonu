# Mimari Açıklama - Yer İstasyonu

Bu doküman, yer istasyonu uygulamasının mimarisini ve tasarım kararlarını açıklar.

## Genel Mimari

### Modüler Yapı

Uygulama 4 ana modüle ayrılmıştır:

1. **models/**: Veri yapıları
2. **core/**: İş mantığı ve worker thread'ler
3. **ui/**: Kullanıcı arayüzü bileşenleri
4. **utils/**: Yardımcı fonksiyonlar

**Neden bu yapı?**
- Kod tekrarını önler
- Bakımı kolaylaştırır
- Test edilebilirliği artırır
- Takım çalışmasına uygundur

## Thread Mimarisi

### Problem

Telemetri ve video sürekli veri üretir. Bu verileri UI thread'inde işlersek:
- UI donar
- Kullanıcı deneyimi kötüleşir
- Uygulama çökebilir

### Çözüm: Worker Thread'ler

**TelemetryWorker** ve **VideoWorker** ayrı thread'lerde çalışır:

```
┌─────────────────┐
│   UI Thread     │  ← Kullanıcı etkileşimi
│  (Main Thread)  │  ← UI güncellemeleri
└────────┬────────┘
         │ Signal/Slot
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│Telemetry│ │Video │  ← Ayrı thread'ler
│ Worker │ │Worker│  ← Veri üretimi
└────────┘ └──────┘
```

### Thread Güvenliği

**PyQt5 Signal/Slot Mekanizması:**
- Signal göndermek thread-safe'dir
- Worker thread'ler signal gönderir
- UI thread signal'leri alır ve güncelleme yapar
- **ASLA** worker thread'den direkt UI güncellemesi yapılmaz!

**Örnek:**
```python
# ✅ DOĞRU
class TelemetryWorker(QThread):
    telemetry_received = pyqtSignal(object)  # Signal tanımla
    
    def run(self):
        data = self.get_telemetry()
        self.telemetry_received.emit(data)  # Signal gönder

# UI Thread'de
worker.telemetry_received.connect(self.update_ui)  # Slot bağla

# ❌ YANLIŞ
class TelemetryWorker(QThread):
    def run(self):
        data = self.get_telemetry()
        self.label.setText(str(data))  # Direkt UI güncellemesi - ÇÖKER!
```

## Throttled Updates

### Problem

Telemetri çok sık gelirse (örn: 100Hz = saniyede 100 güncelleme):
- Her güncellemede UI render edilir
- CPU kullanımı artar
- UI donabilir

### Çözüm: Throttling

`ThrottledUpdater` sınıfı kullanılır:

```python
updater = ThrottledUpdater(update_interval_ms=100)  # 100ms'de bir güncelle
updater.update_requested.connect(self.update_ui)

# Çok sık çağrılabilir
updater.request_update()  # İlk çağrı hemen çalışır
updater.request_update()  # Bu çağrı throttle edilir
updater.request_update()  # Bu da throttle edilir
```

**Nasıl Çalışır?**
1. İlk `request_update()` çağrısı hemen güncelleme yapar
2. Sonraki çağrılar timer başlatır
3. Timer bitince bir güncelleme daha yapılır
4. Bekleyen çağrılar birleştirilir

**Sonuç:**
- UI akıcı kalır
- CPU kullanımı azalır
- Kullanıcı deneyimi iyileşir

## Veri Modelleri

### TelemetryData

Telemetri verilerini tutan dataclass:

```python
@dataclass
class TelemetryData:
    altitude: float
    speed: float
    battery: float
    # ...
```

**Neden dataclass?**
- Otomatik `__init__`, `__repr__`, `__eq__` metodları
- Type hints ile kod okunabilirliği
- Immutable yapılabilir (`frozen=True`)

### MissionItem

Mission item'larını tutan sınıf:

```python
@dataclass
class MissionItem:
    item_type: MissionItemType  # Enum
    sequence: int
    latitude: Optional[float]
    # ...
```

**Enum Kullanımı:**
- Tip güvenliği sağlar
- Hatalı değer girilmesini önler
- IDE autocomplete desteği

## UI Mimarisi

### Widget Hiyerarşisi

```
MainWindow
└── QTabWidget
    ├── FlightTab
    │   ├── TelemetryWidget
    │   ├── MapWidget
    │   └── VideoWidget
    ├── MissionTab
    │   ├── MapWidget
    │   ├── MissionTable
    │   └── ParameterEditor
    ├── CameraTab
    │   └── VideoWidget
    └── LogsTab
        └── LogViewer
```

### Widget vs Tab

**Widget:**
- Yeniden kullanılabilir bileşenler
- Bağımsız çalışabilir
- Örnek: `TelemetryWidget`, `VideoWidget`

**Tab:**
- Sekme sayfaları
- Widget'ları birleştirir
- Örnek: `FlightTab`, `MissionTab`

## Signal/Slot Pattern

PyQt5'in event-driven mimarisi:

**Signal:** Bir olay olduğunda gönderilen mesaj
**Slot:** Signal'i alan ve işleyen fonksiyon

**Örnek:**
```python
# Signal tanımla
class Worker(QThread):
    data_ready = pyqtSignal(object)

# Slot bağla
worker.data_ready.connect(self.handle_data)

# Signal gönder
self.data_ready.emit(data)
```

**Avantajları:**
- Loose coupling (gevşek bağlantı)
- Thread-safe iletişim
- Event-driven mimari

## Mission Manager

Mission item'larını yöneten singleton benzeri sınıf:

**Sorumlulukları:**
- Mission item'larını tutar
- Sequence numaralarını yönetir
- Mission değişikliklerini bildirir (signal)

**Neden ayrı sınıf?**
- Tek sorumluluk prensibi
- Test edilebilirlik
- Gelecekte dosyaya kaydetme/yükleme kolaylığı

## Stil Dosyası (QSS)

Qt Style Sheet kullanarak modern, koyu tema:

**Avantajları:**
- CSS benzeri syntax
- Kolay özelleştirme
- Merkezi stil yönetimi

**Kullanım:**
```python
app.setStyleSheet(open("styles.qss").read())
```

## Hata Yönetimi

**Şu anki durum:**
- Temel hata yönetimi var
- Log sistemi mevcut
- Worker thread hataları loglanır

**İyileştirme önerileri:**
- Try-except blokları eklenebilir
- Hata dialog'ları gösterilebilir
- Hata recovery mekanizmaları eklenebilir

## Performans Optimizasyonları

1. **Throttled Updates**: UI güncellemeleri throttle edilir
2. **Thread Separation**: Ağır işlemler ayrı thread'lerde
3. **Lazy Loading**: Sadece görünen widget'lar render edilir
4. **Efficient Rendering**: QPixmap caching kullanılabilir

## Gelecek Geliştirmeler

### Kısa Vadeli
- Gerçek harita entegrasyonu
- Gerçek telemetri kaynağı
- Gerçek video akışı

### Uzun Vadeli
- Çoklu İHA desteği
- 3D görselleştirme
- Web arayüzü

## Öğrenme Noktaları

### Thread Kullanımı
- Worker thread'ler veri üretir
- UI thread veri gösterir
- Signal/Slot ile iletişim

### Throttling
- Çok sık güncelleme yapma
- Timer kullanarak throttle et
- UI akıcılığını koru

### Modüler Yapı
- Her modül tek sorumluluğa sahip
- Modüller arası gevşek bağlantı
- Test edilebilir kod

### Signal/Slot
- Event-driven mimari
- Thread-safe iletişim
- Loose coupling

## Sonuç

Bu mimari:
- ✅ Thread-safe
- ✅ Modüler
- ✅ Genişletilebilir
- ✅ Bakımı kolay
- ✅ Öğrenmeye uygun

Production için ek güvenlik ve hata yönetimi gerekir, ancak demo için yeterlidir.
