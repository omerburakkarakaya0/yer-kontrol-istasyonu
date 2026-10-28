from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt


class TelemetryCard(QWidget):
    def __init__(self, title, icon_widget=None, parent=None, compact=False):
        super().__init__(parent)

        self.title_label = QLabel(title)
        self.value_label = QLabel("--")

        self.title_label.setAlignment(Qt.AlignCenter)
        self.value_label.setAlignment(Qt.AlignCenter)

        self.title_label.setStyleSheet("color: #a1af9c; font-size: 11px; font-weight: 800;")
        self.value_label.setStyleSheet("color: #f0f3eb; font-size: 18px; font-weight: bold;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        if icon_widget:
            layout.addWidget(icon_widget, alignment=Qt.AlignCenter)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

        self.setStyleSheet("""
            QWidget {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #141d16, stop:1 #111712);
                border: 1px solid #2c3b2e;
                border-radius: 9px;
            }
        """)

        if compact:
            self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            layout.setContentsMargins(4, 5, 4, 5)
            layout.setSpacing(3)
            self.title_label.setStyleSheet("color: #a1af9c; font-size: 10px; font-weight: 600; border: none; background: transparent;")
            self.value_label.setStyleSheet("color: #f0f3eb; font-size: 11px; font-weight: 700; border: none; background: transparent;")
            if icon_widget:
                icon_widget.setFixedSize(70, 38)

    def set_value(self, text):
        self.value_label.setText(str(text))
