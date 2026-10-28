"""
Camera Tab
Kamera görüntüsü sekmesi

MİMARİ:
- Video widget'ı
- Kamera kontrol butonları (ileride)
- Video kayıt butonları (ileride)
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from ui.widgets.video_widget import VideoWidget


class CameraTab(QWidget):
    """
    Camera sekmesi - Kamera görüntüsü.
    
    Bu sekme:
    1. Video akışını gösterir
    2. Kamera kontrolleri sağlar (ileride)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """UI'yi oluştur"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Video widget
        self.video_widget = VideoWidget()
        layout.addWidget(self.video_widget, stretch=1)
        
        # Kontrol paneli (ileride genişletilebilir)
        control_layout = QHBoxLayout()
        control_layout.addStretch()
        
        # Placeholder butonlar
        self.record_btn = QPushButton("Record")
        self.record_btn.setEnabled(False)  # Şimdilik devre dışı
        control_layout.addWidget(self.record_btn)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
    
    def update_video_frame(self, image):
        """Video frame'ini güncelle"""
        self.video_widget.update_frame(image)
