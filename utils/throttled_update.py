"""
Throttled Update Utility
UI güncellemelerini throttle eden yardımcı sınıf

NEDEN THROTTLING?
- Telemetri çok sık gelirse (örn: 100Hz) UI donabilir
- Her güncellemede UI render maliyeti var
- Throttling ile belirli aralıklarla güncelleme yaparak:
  * UI akıcı kalır
  * CPU kullanımı azalır
  * Kullanıcı deneyimi iyileşir
"""
from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from typing import Callable, Optional


class ThrottledUpdater(QObject):
    """
    UI güncellemelerini throttle eden sınıf.
    
    Kullanım:
        updater = ThrottledUpdater(update_interval_ms=100)  # 100ms'de bir güncelle
        updater.update_requested.connect(self.update_ui)
        
        # Çok sık çağrılabilir
        updater.request_update()  # İlk çağrı hemen çalışır
        updater.request_update()  # Bu çağrı throttle edilir
        updater.request_update()  # Bu da throttle edilir
    """
    update_requested = pyqtSignal()  # Güncelleme sinyali
    
    def __init__(self, update_interval_ms: int = 100, parent: Optional[QObject] = None):
        """
        Args:
            update_interval_ms: Minimum güncelleme aralığı (milisaniye)
            parent: Parent QObject
        """
        super().__init__(parent)
        self.update_interval_ms = update_interval_ms
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)  # Tek seferlik timer
        self.timer.timeout.connect(self._emit_update)
        self.pending_update = False
    
    def request_update(self):
        """
        Güncelleme isteği gönder.
        Eğer timer çalışmıyorsa hemen güncelle, 
        çalışıyorsa beklet.
        """
        if not self.timer.isActive():
            # Timer çalışmıyor, hemen güncelle
            self._emit_update()
        else:
            # Timer çalışıyor, beklet
            self.pending_update = True
    
    def _emit_update(self):
        """Güncelleme sinyalini gönder"""
        self.update_requested.emit()
        
        if self.pending_update:
            # Bekleyen güncelleme var, timer'ı yeniden başlat
            self.pending_update = False
            self.timer.start(self.update_interval_ms)
        else:
            # Bekleyen yok, timer'ı durdur
            self.timer.stop()
    
    def force_update(self):
        """Zorla güncelleme yap (throttle'ı bypass et)"""
        self.timer.stop()
        self.pending_update = False
        self._emit_update()
