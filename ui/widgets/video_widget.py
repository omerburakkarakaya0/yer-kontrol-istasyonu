from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy


class VideoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_pixmap = None

        self.image_label = QLabel("Opening camera...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: black;
                border: 1px solid #444;
                color: white;
                font-size: 16px;
            }
        """)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(640, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        layout.addWidget(self.image_label)

    def update_frame(self, image):
        if image is None:
            return

        if hasattr(image, "isNull") and image.isNull():
            return

        self.current_pixmap = QPixmap.fromImage(image)
        self.update_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image()

    def update_image(self):
        if self.current_pixmap is None:
            return

        scaled_pixmap = self.current_pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setText("")
