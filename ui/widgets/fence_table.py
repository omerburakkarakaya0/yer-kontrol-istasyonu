"""Fence table with Mission Planner-style item columns."""
import math
from typing import List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class FenceTable(QWidget):
    zone_selected = pyqtSignal(int)
    zone_changed = pyqtSignal(int, dict)
    zone_remove_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.zones: List[object] = []
        self._updating = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Fence Items")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget(self)
        self.table.setColumnCount(14)
        self.table.setHorizontalHeaderLabels([
            "Command", "P1", "P2", "P3", "P4", "Lat", "Lon", "Alt",
            "Frame", "Delete", "Grad %", "Angle", "Dist", "AZ",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionsMovable(False)
        self.table.horizontalHeader().setSectionsClickable(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self._apply_column_widths()
        layout.addWidget(self.table, 1)

    def update_zones(self, zones: List[object]):
        self.zones = list(zones or [])
        self._populate()

    def _populate(self):
        self._updating = True
        self.table.setRowCount(len(self.zones))

        for row, zone in enumerate(self.zones):
            self._set_readonly_item(row, 0, "FENCE_CIRCLE")

            radius = QDoubleSpinBox()
            radius.setRange(1.0, 5000.0)
            radius.setDecimals(1)
            radius.setSuffix(" m")
            radius.setValue(float(getattr(zone, "radius_m", 50.0)))
            radius.valueChanged.connect(lambda value, i=row: self._emit_change(i, {"radius_m": value}))
            self.table.setCellWidget(row, 1, radius)

            self._set_readonly_item(row, 2, "0")
            self._set_readonly_item(row, 3, "0")
            self._set_readonly_item(row, 4, "0")

            lat = self._coord_spin(float(getattr(zone, "center_lat", 0.0)))
            lat.valueChanged.connect(lambda value, i=row: self._emit_change(i, {"center_lat": value}))
            self.table.setCellWidget(row, 5, lat)

            lon = self._coord_spin(float(getattr(zone, "center_lon", 0.0)))
            lon.valueChanged.connect(lambda value, i=row: self._emit_change(i, {"center_lon": value}))
            self.table.setCellWidget(row, 6, lon)

            self._set_readonly_item(row, 7, "0")
            self._set_frame_combo(row, 8, str(getattr(zone, "frame", "Relative")), row)

            remove = QPushButton("Sil")
            remove.clicked.connect(lambda _, i=row: self.zone_remove_requested.emit(i))
            self.table.setCellWidget(row, 9, remove)

            grad, angle, dist, azimuth = self._leg_metrics(row)
            for col, value in zip((10, 11, 12, 13), (grad, angle, dist, azimuth)):
                metric_item = self._readonly_item(value)
                metric_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, col, metric_item)

        self._apply_column_widths()
        self._updating = False

    def _apply_column_widths(self):
        widths = [150, 90, 62, 62, 62, 130, 130, 82, 105, 90, 82, 82, 90, 82]
        for column, width in enumerate(widths):
            self.table.setColumnWidth(column, width)

    def _set_frame_combo(self, row: int, column: int, value: str, zone_index: int):
        combo = QComboBox()
        for frame in ("Relative", "Absolute", "Terrain"):
            combo.addItem(frame, frame)
        index = combo.findText(self._normalize_frame(value))
        combo.setCurrentIndex(max(0, index))
        combo.currentTextChanged.connect(
            lambda text, i=zone_index: self._emit_change(i, {"frame": self._normalize_frame(text)})
        )
        self.table.setCellWidget(row, column, combo)

    @staticmethod
    def _normalize_frame(frame: str) -> str:
        text = str(frame or "").strip().casefold()
        if text in {"absolute", "global"}:
            return "Absolute"
        if text in {"terrain", "global_terrain_alt"}:
            return "Terrain"
        return "Relative"

    def _set_readonly_item(self, row: int, column: int, value: str):
        self.table.setItem(row, column, self._readonly_item(value))

    @staticmethod
    def _readonly_item(value: str):
        item = QTableWidgetItem(str(value))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    @staticmethod
    def _coord_spin(value: float):
        spin = QDoubleSpinBox()
        spin.setRange(-180.0, 180.0)
        spin.setDecimals(7)
        spin.setSingleStep(0.0001)
        spin.setValue(value)
        return spin

    def _leg_metrics(self, row: int):
        if row <= 0 or row >= len(self.zones):
            return "--", "--", "--", "--"

        previous = self.zones[row - 1]
        current = self.zones[row]
        dist_m = self._distance_m(previous.center_lat, previous.center_lon, current.center_lat, current.center_lon)
        azimuth = self._bearing_deg(previous.center_lat, previous.center_lon, current.center_lat, current.center_lon)
        return "0.0", "0.0", f"{dist_m:.1f}", f"{azimuth:.0f}"

    @staticmethod
    def _distance_m(lat1, lon1, lat2, lon2) -> float:
        radius_m = 6371000.0
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        d_phi = math.radians(float(lat2) - float(lat1))
        d_lambda = math.radians(float(lon2) - float(lon1))
        a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        return radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _bearing_deg(lat1, lon1, lat2, lon2) -> float:
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        d_lambda = math.radians(float(lon2) - float(lon1))
        y = math.sin(d_lambda) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
        return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

    def _emit_change(self, index: int, updates: dict):
        if self._updating:
            return
        self.zone_changed.emit(index, updates)

    def _on_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.zone_selected.emit(rows[0].row())

    def select_zone(self, index: int):
        if 0 <= index < self.table.rowCount():
            self.table.selectRow(index)
