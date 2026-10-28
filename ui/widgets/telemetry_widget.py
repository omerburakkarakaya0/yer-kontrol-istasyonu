"""
Telemetry Widget
Telemetri verilerini ikonlu kartlar halinde gösteren widget.
"""

import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame,
    QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from models.telemetry import TelemetryData
from utils.throttled_update import ThrottledUpdater


class TelemetryCard(QFrame):
    """
    Tek bir telemetri bilgisini gösteren kart.
    İkon + başlık + değer yapısı kullanır.
    """

    def __init__(self, title: str, icon_text: str, unit: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.icon_text = icon_text
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("telemetryCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self.icon_label = QLabel(self.icon_text)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 24px;")
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(self.title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 12px; color: #BBBBBB;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel("--")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(self.value_label)

        self.set_status("normal")

    def set_value(self, value_text: str):
        self.value_label.setText(value_text)

    def set_icon(self, icon_text: str):
        self.icon_label.setText(icon_text)

    def set_status(self, status: str):
        """
        status:
        - normal
        - good
        - warning
        - danger
        - info
        """
        styles = {
            "normal": """
                QFrame#telemetryCard {
                    background-color: #1f1f1f;
                    border: 1px solid #3a3a3a;
                    border-radius: 10px;
                }
            """,
            "good": """
                QFrame#telemetryCard {
                    background-color: #1f2b1f;
                    border: 2px solid #2e9d44;
                    border-radius: 10px;
                }
            """,
            "warning": """
                QFrame#telemetryCard {
                    background-color: #2f2a1a;
                    border: 2px solid #d4a017;
                    border-radius: 10px;
                }
            """,
            "danger": """
                QFrame#telemetryCard {
                    background-color: #2d1d1d;
                    border: 2px solid #c93c3c;
                    border-radius: 10px;
                }
            """,
            "info": """
                QFrame#telemetryCard {
                    background-color: #1c2430;
                    border: 2px solid #4b89dc;
                    border-radius: 10px;
                }
            """,
        }
        self.setStyleSheet(styles.get(status, styles["normal"]))


class TelemetryWidget(QWidget):
    """
    Telemetri gösterim widget'ı.
    Kart bazlı, ikonlu görünüm kullanır.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_telemetry: TelemetryData = None
        self.last_packet_timestamp = None
        self.init_ui()

        self.updater = ThrottledUpdater(update_interval_ms=100, parent=self)
        self.updater.update_requested.connect(self._update_display)

        self.signal_timer = QTimer(self)
        self.signal_timer.timeout.connect(self._refresh_signal_only)
        self.signal_timer.start(250)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Telemetry")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.connection_label = QLabel("● Disconnected")
        self.connection_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.connection_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self.altitude_card = TelemetryCard("Altitude", "⬆", "m")
        self.speed_card = TelemetryCard("Speed", "⏱", "m/s")
        self.battery_card = TelemetryCard("Battery", "🔋", "%")
        self.pitch_card = TelemetryCard("Pitch", "↕", "°")
        self.roll_card = TelemetryCard("Roll", "↔", "°")
        self.yaw_card = TelemetryCard("Yaw", "🧭", "°")
        self.lat_card = TelemetryCard("GPS Lat", "📍", "")
        self.lon_card = TelemetryCard("GPS Lon", "🌍", "")
        self.signal_card = TelemetryCard("Signal", "📶", "")

        grid.addWidget(self.altitude_card, 0, 0)
        grid.addWidget(self.speed_card, 0, 1)
        grid.addWidget(self.battery_card, 0, 2)
        grid.addWidget(self.pitch_card, 1, 0)
        grid.addWidget(self.roll_card, 1, 1)
        grid.addWidget(self.yaw_card, 1, 2)
        grid.addWidget(self.lat_card, 2, 0)
        grid.addWidget(self.lon_card, 2, 1)
        grid.addWidget(self.signal_card, 2, 2)

        layout.addLayout(grid)

        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: orange; font-weight: bold;")
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)

        layout.addStretch()

    def update_telemetry(self, telemetry: TelemetryData):
        self.last_telemetry = telemetry
        self.last_packet_timestamp = time.time()
        self.updater.request_update()

    def _update_display(self):
        if self.last_telemetry is None:
            self._update_signal_card()
            return

        telemetry = self.last_telemetry

        # Değerler
        self.altitude_card.set_value(f"{telemetry.altitude:.1f} m")
        self.speed_card.set_value(f"{telemetry.speed:.1f} m/s")
        self.battery_card.set_value(f"{telemetry.battery:.1f} %")
        self.pitch_card.set_value(f"{telemetry.pitch:.1f}°")
        self.roll_card.set_value(f"{telemetry.roll:.1f}°")
        self.yaw_card.set_value(f"{telemetry.yaw:.1f}°")
        self.lat_card.set_value(f"{telemetry.latitude:.6f}")
        self.lon_card.set_value(f"{telemetry.longitude:.6f}")

        # Bağlantı
        if telemetry.connected:
            self.connection_label.setText("● Connected")
            self.connection_label.setStyleSheet("color: #2e9d44; font-weight: bold;")
        else:
            self.connection_label.setText("● Disconnected")
            self.connection_label.setStyleSheet("color: #c93c3c; font-weight: bold;")

        # Battery durumu
        self._update_battery_card(telemetry.battery)

        # Speed durumu
        self._update_speed_card(telemetry.speed)

        # Altitude durumu
        self._update_altitude_card(telemetry.altitude)

        # Pitch / Roll / Yaw
        self._update_attitude_cards(telemetry.pitch, telemetry.roll, telemetry.yaw)

        # GPS kartları
        self.lat_card.set_status("info")
        self.lon_card.set_status("info")

        # Signal kartı
        self._update_signal_card()

        # Uyarılar
        warnings = []
        if telemetry.battery < 20:
            warnings.append("LOW BATTERY!")
        if telemetry.altitude < 5 and telemetry.speed > 10:
            warnings.append("LOW ALTITUDE!")
        if abs(telemetry.roll) > 45:
            warnings.append("HIGH ROLL ANGLE!")
        if abs(telemetry.pitch) > 35:
            warnings.append("HIGH PITCH ANGLE!")

        # Signal uyarıları
        signal_state = self._get_signal_state()
        if signal_state == "warning":
            warnings.append("LINK WEAK!")
        elif signal_state == "danger":
            warnings.append("LINK LOST!")

        self.warning_label.setText(" | ".join(warnings) if warnings else "")

    def _refresh_signal_only(self):
        self._update_signal_card()

        if self.last_telemetry is not None:
            warnings = []
            telemetry = self.last_telemetry

            if telemetry.battery < 20:
                warnings.append("LOW BATTERY!")
            if telemetry.altitude < 5 and telemetry.speed > 10:
                warnings.append("LOW ALTITUDE!")
            if abs(telemetry.roll) > 45:
                warnings.append("HIGH ROLL ANGLE!")
            if abs(telemetry.pitch) > 35:
                warnings.append("HIGH PITCH ANGLE!")

            signal_state = self._get_signal_state()
            if signal_state == "warning":
                warnings.append("LINK WEAK!")
            elif signal_state == "danger":
                warnings.append("LINK LOST!")

            self.warning_label.setText(" | ".join(warnings) if warnings else "")

    def _get_signal_state(self):
        if self.last_packet_timestamp is None:
            return "danger"

        delta = time.time() - self.last_packet_timestamp

        if self.last_telemetry is not None and not self.last_telemetry.connected:
            return "danger"

        if delta < 0.3:
            return "good"
        elif delta < 0.8:
            return "info"
        elif delta < 1.5:
            return "warning"
        else:
            return "danger"

    def _update_signal_card(self):
        state = self._get_signal_state()

        if state == "good":
            self.signal_card.set_value("▂▄▆█ Excellent")
            self.signal_card.set_status("good")
            self.signal_card.set_icon("📶")
        elif state == "info":
            self.signal_card.set_value("▂▄▆ Good")
            self.signal_card.set_status("info")
            self.signal_card.set_icon("📶")
        elif state == "warning":
            self.signal_card.set_value("▂▄ Weak")
            self.signal_card.set_status("warning")
            self.signal_card.set_icon("📶")
        else:
            self.signal_card.set_value("▂ Lost")
            self.signal_card.set_status("danger")
            self.signal_card.set_icon("📶")

    def _update_battery_card(self, battery: float):
        if battery <= 30:
            self.battery_card.set_status("danger")
            self.battery_card.set_icon("🪫")
        elif battery <= 60:
            self.battery_card.set_status("warning")
            self.battery_card.set_icon("🔋")
        else:
            self.battery_card.set_status("good")
            self.battery_card.set_icon("🔋")

    def _update_speed_card(self, speed: float):
        if speed < 5:
            self.speed_card.set_status("info")
        elif speed < 15:
            self.speed_card.set_status("good")
        elif speed < 25:
            self.speed_card.set_status("warning")
        else:
            self.speed_card.set_status("danger")

    def _update_altitude_card(self, altitude: float):
        if altitude < 5:
            self.altitude_card.set_status("warning")
        elif altitude < 120:
            self.altitude_card.set_status("good")
        else:
            self.altitude_card.set_status("warning")

    def _update_attitude_cards(self, pitch: float, roll: float, yaw: float):
        if abs(pitch) > 35:
            self.pitch_card.set_status("danger")
        elif abs(pitch) > 20:
            self.pitch_card.set_status("warning")
        else:
            self.pitch_card.set_status("normal")

        if abs(roll) > 45:
            self.roll_card.set_status("danger")
        elif abs(roll) > 25:
            self.roll_card.set_status("warning")
        else:
            self.roll_card.set_status("normal")

        self.yaw_card.set_status("info")