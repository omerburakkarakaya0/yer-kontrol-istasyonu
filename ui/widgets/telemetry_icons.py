from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF
from PyQt5.QtCore import Qt, QRectF, QPointF
import math


def value_color(value, thresholds):
    if value is None:
        return QColor("#777777")

    for limit, color in thresholds:
        if value <= limit:
            return QColor(color)

    return QColor("#00c853")


class BatteryIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.setMinimumSize(70, 36)

    def set_value(self, value):
        self.value = max(0, min(100, int(value)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        body = QRectF(5, 6, w - 18, h - 12)
        tip = QRectF(w - 12, h / 2 - 6, 7, 12)

        painter.setPen(QPen(QColor("#ffffff"), 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(body, 4, 4)
        painter.drawRoundedRect(tip, 2, 2)

        color = value_color(self.value, [
            (25, "#ff3333"),
            (50, "#ff9800"),
            (75, "#ffeb3b"),
            (100, "#40d000")
        ])

        fill_width = (body.width() - 6) * self.value / 100
        fill_rect = QRectF(body.x() + 3, body.y() + 3, fill_width, body.height() - 6)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(fill_rect, 3, 3)


class SignalIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.setMinimumSize(70, 42)

    def set_value(self, value):
        self.value = max(0, min(100, int(value)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = value_color(self.value, [
            (30, "#ff3333"),
            (70, "#ffeb3b"),
            (100, "#00c853")
        ])

        painter.setPen(Qt.NoPen)

        bars = 5
        gap = 5
        bar_width = 8
        max_height = self.height() - 8
        active_bars = math.ceil(self.value / 20)

        start_x = 8
        bottom = self.height() - 4

        for i in range(bars):
            height = max_height * ((i + 1) / bars)
            x = start_x + i * (bar_width + gap)
            y = bottom - height

            if i < active_bars:
                painter.setBrush(QBrush(color))
            else:
                painter.setBrush(QBrush(QColor("#444444")))

            painter.drawRoundedRect(QRectF(x, y, bar_width, height), 2, 2)


class CompassIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.heading = 0
        self.setMinimumSize(70, 70)

    def set_heading(self, heading):
        self.heading = float(heading) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        size = min(self.width(), self.height()) - 6
        cx = self.width() / 2
        cy = self.height() / 2
        r = size / 2

        painter.setPen(QPen(QColor("#dddddd"), 2))
        painter.setBrush(QBrush(QColor("#15191d")))
        painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        painter.drawText(QRectF(cx - 8, cy - r + 4, 16, 14), Qt.AlignCenter, "N")
        painter.drawText(QRectF(cx - 8, cy + r - 18, 16, 14), Qt.AlignCenter, "S")
        painter.drawText(QRectF(cx + r - 18, cy - 7, 16, 14), Qt.AlignCenter, "E")
        painter.drawText(QRectF(cx - r + 2, cy - 7, 16, 14), Qt.AlignCenter, "W")

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.heading)

        needle = QPolygonF([
            QPointF(0, -r + 16),
            QPointF(-7, 5),
            QPointF(0, 0),
            QPointF(7, 5)
        ])

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#ff3333")))
        painter.drawPolygon(needle)

        painter.restore()


class SpeedGaugeIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.max_value = 100
        self.setMinimumSize(90, 60)

    def set_value(self, value):
        self.value = max(0, min(self.max_value, float(value)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h - 5
        r = min(w / 2 - 8, h - 8)

        painter.setPen(QPen(QColor("#555555"), 8, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), 0 * 16, 180 * 16)

        painter.setPen(QPen(QColor("#8eae7b"), 8, Qt.SolidLine, Qt.RoundCap))
        angle_span = int(180 * (self.value / self.max_value))
        painter.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), 180 * 16, -angle_span * 16)

        angle = math.radians(180 - angle_span)
        needle_len = r - 5
        x = cx + needle_len * math.cos(angle)
        y = cy - needle_len * math.sin(angle)

        painter.setPen(QPen(QColor("#ffffff"), 3))
        painter.drawLine(QPointF(cx, cy), QPointF(x, y))

        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(QPointF(cx, cy), 4, 4)
        
class AltitudeIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(55, 55)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2

        painter.setPen(QPen(QColor("#8eae7b"), 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(cx, cy + 18), QPointF(cx, cy - 15))
        painter.drawLine(QPointF(cx, cy - 15), QPointF(cx - 10, cy - 3))
        painter.drawLine(QPointF(cx, cy - 15), QPointF(cx + 10, cy - 3))

        painter.setPen(QPen(QColor("#777777"), 2))
        painter.drawLine(QPointF(cx - 18, cy + 20), QPointF(cx + 18, cy + 20))


class PitchIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(55, 55)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2

        painter.setPen(QPen(QColor("#00c853"), 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(cx - 18, cy - 18, 36, 36), 30 * 16, 120 * 16)

        painter.drawLine(QPointF(cx, cy - 22), QPointF(cx - 8, cy - 10))
        painter.drawLine(QPointF(cx, cy - 22), QPointF(cx + 8, cy - 10))

        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawLine(QPointF(cx - 16, cy), QPointF(cx + 16, cy))


class RollIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(55, 55)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2

        painter.setPen(QPen(QColor("#ff9800"), 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(cx - 20, cy - 20, 40, 40), 200 * 16, 140 * 16)

        painter.drawLine(QPointF(cx - 21, cy), QPointF(cx - 10, cy - 7))
        painter.drawLine(QPointF(cx - 21, cy), QPointF(cx - 10, cy + 7))

        painter.drawLine(QPointF(cx + 21, cy), QPointF(cx + 10, cy - 7))
        painter.drawLine(QPointF(cx + 21, cy), QPointF(cx + 10, cy + 7))


class GpsIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(55, 55)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2

        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QBrush(QColor("#e53935")))

        painter.drawEllipse(QPointF(cx, cy - 6), 12, 12)

        triangle = QPolygonF([
            QPointF(cx, cy + 22),
            QPointF(cx - 9, cy + 4),
            QPointF(cx + 9, cy + 4)
        ])
        painter.drawPolygon(triangle)

        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(QPointF(cx, cy - 6), 4, 4)
