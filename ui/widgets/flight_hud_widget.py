"""Flight HUD Widget

Daha modern ve hÄ±zlÄ± okunabilen HUD gÃ¶rÃ¼nÃ¼mÃ¼:
- Ortada attitude indicator (pitch / roll)
- Ãœstte heading
- SaÄŸda altitude / speed / battery kartlarÄ±
- Altta connection ve warning alanÄ±
"""

import math

from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QGroupBox
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont

from models.telemetry import TelemetryData


class InfoCard(QFrame):
    def __init__(self, title: str, value: str = "--", parent=None, compact=False):
        super().__init__(parent)
        self.compact = compact
        self._title = title
        self._build_ui()
        self.set_value(value)
        self.set_status("normal")

    def _build_ui(self):
        self.setObjectName("infoCard")
        self.setMinimumHeight(38 if self.compact else 54)
        self.setMaximumHeight(42 if self.compact else 64)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2) if self.compact else layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(2)

        self.title_label = QLabel(self._title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #a1af9c; font-size: 10px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel("--")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("color: #f0f3eb; font-size: 18px; font-weight: 700;")
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        if self.value_label.text() == value:
            return
        self.value_label.setText(value)
        font_size = 15 if len(str(value)) > 8 else 18
        if self.compact:
            font_size = 11 if len(str(value)) > 8 else 13
        self.value_label.setStyleSheet(
            f"color: #f0f3eb; font-size: {font_size}px; font-weight: 700;"
        )

    def set_status(self, status: str):
        if getattr(self, "_status", None) == status:
            return
        self._status = status
        styles = {
            "normal": """
                QFrame#infoCard {
                    background-color: #111712;
                    border: 1px solid #2c3b2e;
                    border-radius: 7px;
                }
            """,
            "good": """
                QFrame#infoCard {
                    background-color: #092016;
                    border: 2px solid #1cc55d;
                    border-radius: 7px;
                }
            """,
            "warning": """
                QFrame#infoCard {
                    background-color: #241d08;
                    border: 2px solid #fbbc05;
                    border-radius: 7px;
                }
            """,
            "danger": """
                QFrame#infoCard {
                    background-color: #2a1015;
                    border: 2px solid #ff6570;
                    border-radius: 7px;
                }
            """,
            "info": """
                QFrame#infoCard {
                    background-color: #213b28;
                    border: 2px solid #577b59;
                    border-radius: 7px;
                }
            """,
        }
        self.setStyleSheet(styles.get(status, styles["normal"]))


class AttitudeIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pitch = 0.0
        self.roll = 0.0
        self.speed = 0.0
        self.altitude = 0.0
        self.setMinimumSize(260, 230)

    def set_attitude(self, pitch: float, roll: float):
        self.pitch = pitch
        self.roll = roll
        self.update()

    def set_flight_data(self, pitch: float, roll: float, speed: float, altitude: float):
        self.pitch = pitch
        self.roll = roll
        self.speed = speed
        self.altitude = altitude
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        scale = min(1.0, self.width() / 300, self.height() / 230)
        painter.scale(scale, scale)
        w = self.width() / scale
        h = self.height() / scale
        cx = w / 2
        cy = h / 2
        tape_w = 56
        radius = min(w - tape_w * 2 - 12, h) / 2 - 8

        # Arka plan
        painter.fillRect(QRectF(0, 0, w, h), QColor("#090c0a"))

        # Dairesel alan
        circle_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        painter.save()
        painter.setClipPath(self._circle_path(circle_rect))

        # Pitch / roll dÃ¶nÃ¼ÅŸÃ¼mÃ¼
        try:
            import config
            visual_pitch = self.pitch * float(getattr(config, "HUD_ATTITUDE_PITCH_SIGN", 1.0))
            visual_roll = self.roll * float(getattr(config, "HUD_ATTITUDE_ROLL_SIGN", 1.0))
        except Exception:
            visual_pitch = self.pitch
            visual_roll = self.roll

        painter.translate(cx, cy)
        painter.rotate(visual_roll)

        pitch_offset = visual_pitch * 3.0  # pitch arttÄ±kÃ§a ufuk aÅŸaÄŸÄ±/yukarÄ± kayar

        # GÃ¶kyÃ¼zÃ¼
        painter.fillRect(
            QRectF(-radius * 2, -radius * 2 + pitch_offset, radius * 4, radius * 2),
            QColor("#13ACE8")
        )
        # Yer
        painter.fillRect(
            QRectF(-radius * 2, pitch_offset, radius * 4, radius * 2),
            QColor("#743206")
        )

        # Ufuk Ã§izgisi
        painter.setPen(QPen(QColor("white"), 3))
        painter.drawLine(QPointF(-radius * 1.5, pitch_offset), QPointF(radius * 1.5, pitch_offset))

        # Pitch Ã§izgileri
        painter.setPen(QPen(QColor("#e8eaed"), 2))
        for deg in range(-30, 31, 10):
            if deg == 0:
                continue
            y = pitch_offset - deg * 3.0
            line_half = 28 if deg % 20 == 0 else 18
            painter.drawLine(QPointF(-line_half, y), QPointF(line_half, y))
            painter.setFont(QFont("Arial", 8))
            painter.drawText(int(-line_half - 24), int(y + 4), f"{abs(deg)}")
            painter.drawText(int(line_half + 8), int(y + 4), f"{abs(deg)}")

        painter.restore()

        # DÄ±ÅŸ Ã§ember
        painter.setPen(QPen(QColor("#d0d4d9"), 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(circle_rect)

        # Roll scale Ã¼st yay
        self._draw_roll_scale(painter, cx, cy, radius, visual_roll)

        # Orta sabit niÅŸangah
        self._draw_center_reticle(painter, cx, cy)
        self._draw_side_tapes(painter, cx, cy, radius)

    def _circle_path(self, rect: QRectF):
        from PyQt5.QtGui import QPainterPath
        path = QPainterPath()
        path.addEllipse(rect)
        return path

    def _draw_roll_scale(self, painter: QPainter, cx: float, cy: float, radius: float, visual_roll: float):
        painter.save()
        painter.translate(cx, cy)

        painter.setPen(QPen(QColor("#d0d4d9"), 2))

        # Sabit Ã¼st merkez iÅŸareti
        painter.drawLine(QPointF(0, -radius - 2), QPointF(-8, -radius + 12))
        painter.drawLine(QPointF(0, -radius - 2), QPointF(8, -radius + 12))

        # Roll tickleri
        for angle in [-60, -45, -30, -20, -10, 10, 20, 30, 45, 60]:
            rad = math.radians(angle - 90)
            outer = QPointF(math.cos(rad) * (radius - 2), math.sin(rad) * (radius - 2))
            inner_len = 16 if angle in [-60, -30, 30, 60] else 10
            inner = QPointF(math.cos(rad) * (radius - inner_len), math.sin(rad) * (radius - inner_len))
            painter.drawLine(inner, outer)

        # Mevcut roll gÃ¶stergesi
        painter.rotate(visual_roll)
        painter.setBrush(QBrush(QColor("#34a853")))
        painter.setPen(Qt.NoPen)

        rad = math.radians(-90)
        p1 = QPointF(math.cos(rad) * (radius - 6), math.sin(rad) * (radius - 6))
        p2 = QPointF(-8, -radius + 18)
        p3 = QPointF(8, -radius + 18)

        from PyQt5.QtGui import QPolygonF
        painter.drawPolygon(QPolygonF([p1, p2, p3]))
        painter.restore()

    def _draw_center_reticle(self, painter: QPainter, cx: float, cy: float):
        painter.save()
        painter.setPen(QPen(QColor("#f0f3eb"), 3))

        # Ortadaki HUD niÅŸangahÄ±
        painter.drawLine(int(cx - 38), int(cy), int(cx - 12), int(cy))
        painter.drawLine(int(cx + 12), int(cy), int(cx + 38), int(cy))
        painter.drawLine(int(cx), int(cy - 10), int(cx), int(cy + 10))

        painter.setPen(QPen(QColor("#34a853"), 2))
        painter.drawEllipse(QPointF(cx, cy), 4, 4)
        painter.restore()

    def _draw_side_tapes(self, painter: QPainter, cx: float, cy: float, radius: float):
        painter.save()
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QPen(QColor("#a1af9c"), 1))

        left_x = int(cx - radius - 38)
        right_x = int(cx + radius + 8)
        top = int(cy - radius + 30)
        bottom = int(cy + radius - 30)

        painter.drawLine(left_x + 20, top, left_x + 20, bottom)
        painter.drawLine(right_x + 20, top, right_x + 20, bottom)

        for i, label in enumerate([40, 30, 20, 10]):
            y = top + i * 28
            painter.drawLine(left_x + 10, y, left_x + 28, y)
            painter.drawText(left_x, y + 4, str(label))
        for i, label in enumerate([800, 700, 600, 500]):
            y = top + i * 28
            painter.drawLine(right_x + 10, y, right_x + 28, y)
            painter.drawText(right_x + 30, y + 4, str(label))

        painter.setBrush(QBrush(QColor("#0a361f")))
        painter.setPen(QPen(QColor("#1cc55d"), 2))
        painter.drawRoundedRect(left_x - 4, int(cy - 14), 42, 26, 4, 4)
        painter.drawRoundedRect(right_x - 2, int(cy - 14), 50, 26, 4, 4)
        painter.setPen(QPen(QColor("#8dff99"), 1))
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(left_x - 1, int(cy + 4), f"{self.speed:.1f}")
        painter.drawText(right_x + 3, int(cy + 4), f"{self.altitude:.0f}")
        painter.restore()


class FlightHUDWidget(QGroupBox):
    def __init__(self, parent=None, compact=False):
        super().__init__(parent)
        self.setTitle("UÇUŞ VERİ HUD")
        self.compact = compact
        self._last: TelemetryData | None = None
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            FlightHUDWidget {
                background-color: #090c0a;
                border: 1px solid #2c3b2e;
                border-radius: 8px;
                margin-top: 0px;
                padding-top: 24px;
                color: #f0f3eb;
                font-size: 12px;
                font-weight: 800;
            }
            FlightHUDWidget::title {
                subcontrol-origin: border;
                subcontrol-position: top left;
                top: 8px;
                left: 12px;
                padding: 0px;
            }
            QLabel {
                background-color: transparent;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(5)

        # Orta alan
        center = QHBoxLayout()
        center.setSpacing(8)

        attitude_column = QVBoxLayout()
        attitude_column.setSpacing(3)

        self.attitude = AttitudeIndicator()
        if self.compact:
            self.attitude.setMinimumSize(170, 160)
        attitude_column.addWidget(self.attitude, 1)

        readout_row = QHBoxLayout()
        readout_row.setSpacing(8)
        self.gs_label = QLabel("GS\n--")
        self.heading_label = QLabel("000.0°\nHDG")
        self.alt_bottom_label = QLabel("irtifa (AMSL)\n--")
        for label in (self.gs_label, self.heading_label, self.alt_bottom_label):
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("""
                color: #e0e7dc;
                background-color: transparent;
                font-size: 11px;
                font-weight: 600;
            """)
        self.heading_label.setStyleSheet("""
            color: #f0f3eb;
            background-color: #213b28;
            border: 1px solid #577b59;
            border-radius: 7px;
            padding: 4px 18px;
            font-size: 17px;
            font-weight: 900;
        """)
        if self.compact:
            self.heading_label.setStyleSheet("color: #f0f3eb; background: #213b28; border: 1px solid #577b59; border-radius: 5px; padding: 3px; font-size: 12px; font-weight: 700;")
            for label in (self.gs_label, self.alt_bottom_label):
                label.setStyleSheet("color: #b9c7b1; font-size: 9px;")
            readout_row.setSpacing(3)
        readout_row.addWidget(self.gs_label)
        readout_row.addStretch()
        readout_row.addWidget(self.heading_label)
        readout_row.addStretch()
        readout_row.addWidget(self.alt_bottom_label)
        attitude_column.addLayout(readout_row)

        center.addLayout(attitude_column, 3)

        side_panel = QVBoxLayout()
        side_panel.setSpacing(4)

        self.pitch_card = InfoCard("Pitch", parent=self, compact=self.compact)
        self.roll_card = InfoCard("Roll", parent=self, compact=self.compact)
        self.yaw_card = InfoCard("Yaw", parent=self, compact=self.compact)
        self.alt_card = InfoCard("Altitude", parent=self, compact=self.compact)
        self.gps_lat_card = InfoCard("GPS Lat", parent=self, compact=self.compact)
        self.gps_lon_card = InfoCard("GPS Lon", parent=self, compact=self.compact)
        self.spd_card = InfoCard("Speed", parent=self, compact=self.compact)
        self.bat_card = InfoCard("Battery", parent=self, compact=self.compact)
        self.spd_card.hide()
        self.bat_card.hide()

        side_panel.addWidget(self.pitch_card)
        side_panel.addWidget(self.roll_card)
        side_panel.addWidget(self.yaw_card)
        side_panel.addWidget(self.alt_card)
        side_panel.addWidget(self.gps_lat_card)
        side_panel.addWidget(self.gps_lon_card)
        side_panel.addStretch()

        center.addLayout(side_panel, 1)
        root.addLayout(center)

    def update_telemetry(self, t: TelemetryData):
        self._last = t
        t.pitch = getattr(t, "safe_pitch", 0.0)
        t.roll = getattr(t, "safe_roll", 0.0)
        t.yaw = getattr(t, "safe_yaw", 0.0)

        # GÃ¶rsel attitude
        self.attitude.set_flight_data(t.pitch, t.roll, t.speed, t.altitude)

        # Heading
        heading = t.yaw % 360
        self.heading_label.setText(f"{heading:05.1f}°\nHDG")
        self.gs_label.setText(f"GS\n{t.speed:.1f} m/s")
        self.alt_bottom_label.setText(f"irtifa (AMSL)\n{t.altitude:.0f} m")

        # Kart deÄŸerleri
        self.pitch_card.set_value(f"{t.pitch:.1f}°")
        self.roll_card.set_value(f"{t.roll:.1f}°")
        self.yaw_card.set_value(f"{heading:.1f} deg")
        self.alt_card.set_value(f"{t.altitude:.1f} m")
        self.gps_lat_card.set_value(self._format_gps(t.latitude))
        self.gps_lon_card.set_value(self._format_gps(t.longitude))
        self.spd_card.set_value(f"{t.speed:.1f} m/s")
        self.bat_card.set_value(f"{t.battery:.1f} %")

        # Kart durumlarÄ±
        self._update_pitch_roll_status(t.pitch, t.roll)
        self.yaw_card.set_status("info")
        self._update_altitude_status(t.altitude)
        gps_status = "good" if t.latitude not in (None, 0) and t.longitude not in (None, 0) else "warning"
        self.gps_lat_card.set_status(gps_status)
        self.gps_lon_card.set_status(gps_status)
        self._update_speed_status(t.speed)
        self._update_battery_status(t.battery)

    @staticmethod
    def _format_gps(value):
        if value in (None, 0):
            return "--"
        return f"{float(value):.6f}"

    def _update_pitch_roll_status(self, pitch: float, roll: float):
        if abs(pitch) > 35:
            self.pitch_card.set_status("danger")
        elif abs(pitch) > 20:
            self.pitch_card.set_status("warning")
        else:
            self.pitch_card.set_status("info")

        if abs(roll) > 45:
            self.roll_card.set_status("danger")
        elif abs(roll) > 25:
            self.roll_card.set_status("warning")
        else:
            self.roll_card.set_status("info")

    def _update_altitude_status(self, altitude: float):
        if altitude < 5:
            self.alt_card.set_status("warning")
        elif altitude < 120:
            self.alt_card.set_status("good")
        else:
            self.alt_card.set_status("warning")

    def _update_speed_status(self, speed: float):
        if speed < 5:
            self.spd_card.set_status("info")
        elif speed < 15:
            self.spd_card.set_status("good")
        elif speed < 25:
            self.spd_card.set_status("warning")
        else:
            self.spd_card.set_status("danger")

    def _update_battery_status(self, battery: float):
        if battery <= 30:
            self.bat_card.set_status("danger")
        elif battery <= 60:
            self.bat_card.set_status("warning")
        else:
            self.bat_card.set_status("good")
