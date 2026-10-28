"""Mission item table with Mission Planner-style columns."""
import math
from typing import List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.mission_item import MissionItem, MissionItemType


class MissionTable(QWidget):
    item_selected = pyqtSignal(int)
    item_remove_requested = pyqtSignal(int)
    item_type_changed = pyqtSignal(int, object)
    item_updated = pyqtSignal(int, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mission_items: List[MissionItem] = []
        self._updating_table = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Mission Items")
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
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemChanged.connect(self._on_item_changed)
        self._apply_column_widths()
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self._remove_selected)
        button_layout.addWidget(self.remove_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

    def update_mission(self, items: List[MissionItem]):
        self.mission_items = items
        self._populate_table()

    def _populate_table(self):
        self._updating_table = True
        self.table.setRowCount(len(self.mission_items))

        for row, item in enumerate(self.mission_items):
            combo = QComboBox()
            combo.addItem("WAYPOINT", MissionItemType.WAYPOINT)
            combo.addItem("TAKEOFF", MissionItemType.TAKEOFF)
            combo.addItem("DO_JUMP", MissionItemType.DO_JUMP)
            combo.addItem("DO_LAND_START", MissionItemType.DO_LAND_START)
            combo.addItem("LAND", MissionItemType.LAND)

            current_index = combo.findData(item.item_type)
            if current_index >= 0:
                combo.setCurrentIndex(current_index)

            combo.currentIndexChanged.connect(
                lambda _, seq=item.sequence, c=combo: self._emit_type_change(seq, c)
            )
            self.table.setCellWidget(row, 0, combo)

            for col, value in enumerate(self._mission_planner_params(item), start=1):
                self._set_editable_item(row, col, value)

            self._set_editable_item(row, 5, self._format_coord(item.latitude))
            self._set_editable_item(row, 6, self._format_coord(item.longitude))
            self._set_editable_item(row, 7, self._format_number(item.altitude, 1))
            self._set_frame_combo(row, 8, str((item.parameters or {}).get("frame", "Relative")), item.sequence)

            remove = QPushButton("Sil")
            remove.clicked.connect(lambda _, seq=item.sequence: self.item_remove_requested.emit(seq))
            self.table.setCellWidget(row, 9, remove)

            grad, angle, dist, azimuth = self._leg_metrics(row)
            for col, value in zip((10, 11, 12, 13), (grad, angle, dist, azimuth)):
                metric_item = self._readonly_item(value)
                metric_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, col, metric_item)

        self._apply_column_widths()
        self._updating_table = False

    def _apply_column_widths(self):
        widths = [150, 62, 62, 62, 62, 118, 118, 82, 105, 90, 82, 82, 90, 82]
        for column, width in enumerate(widths):
            self.table.setColumnWidth(column, width)

    def _set_readonly_item(self, row: int, column: int, value: str):
        self.table.setItem(row, column, self._readonly_item(value))

    def _set_editable_item(self, row: int, column: int, value: str):
        self.table.setItem(row, column, QTableWidgetItem(str(value)))

    @staticmethod
    def _readonly_item(value: str):
        item = QTableWidgetItem(str(value))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    @staticmethod
    def _mission_planner_params(item: MissionItem):
        params = item.parameters or {}
        if item.item_type == MissionItemType.DO_JUMP:
            return [
                str(params.get("jump_to", 0)),
                str(params.get("repeat", 1)),
                "--",
                "--",
            ]
        if item.item_type == MissionItemType.RTL:
            return ["--", "--", "--", "--"]

        return [
            str(params.get("delay", params.get("param1", 0))),
            str(params.get("acceptance_radius", params.get("param2", 0))),
            str(params.get("pass_radius", params.get("param3", 0))),
            str(params.get("yaw", params.get("param4", 0))),
        ]

    def _on_item_changed(self, cell: QTableWidgetItem):
        if self._updating_table:
            return
        row = cell.row()
        column = cell.column()
        if row < 0 or row >= len(self.mission_items):
            return
        if column not in {1, 2, 3, 4, 5, 6, 7}:
            return

        item = self.mission_items[row]
        text = cell.text().strip()
        updates = {}
        params = dict(item.parameters or {})

        try:
            if column in {1, 2, 3, 4}:
                value = float(text.replace(",", "."))
                if item.item_type == MissionItemType.DO_JUMP:
                    if column == 1:
                        params["jump_to"] = int(value)
                    elif column == 2:
                        params["repeat"] = int(value)
                    else:
                        params[f"param{column}"] = value
                else:
                    params[f"param{column}"] = value
                updates["parameters"] = params
            elif column == 5:
                updates["latitude"] = float(text.replace(",", "."))
            elif column == 6:
                updates["longitude"] = float(text.replace(",", "."))
            elif column == 7:
                updates["altitude"] = float(text.replace(",", "."))
        except ValueError:
            self._populate_table()
            return

        if updates:
            self.item_updated.emit(item.sequence, updates)

    def _leg_metrics(self, row: int):
        if row <= 0 or row >= len(self.mission_items):
            return "--", "--", "--", "--"

        previous = self._previous_position_item(row)
        current = self.mission_items[row]
        if previous is None or not self._has_position(current):
            return "--", "--", "--", "--"

        distance_m = self._distance_m(previous.latitude, previous.longitude, current.latitude, current.longitude)
        azimuth = self._bearing_deg(previous.latitude, previous.longitude, current.latitude, current.longitude)
        alt_delta = float(current.altitude or 0.0) - float(previous.altitude or 0.0)
        if distance_m <= 0.001:
            grad = "--"
            angle = "--"
        else:
            grad = f"{(alt_delta / distance_m) * 100.0:.1f}"
            angle = f"{math.degrees(math.atan2(alt_delta, distance_m)):.1f}"
        return grad, angle, f"{distance_m:.1f}", f"{azimuth:.0f}"

    def _previous_position_item(self, row: int):
        for index in range(row - 1, -1, -1):
            candidate = self.mission_items[index]
            if self._has_position(candidate):
                return candidate
        return None

    @staticmethod
    def _has_position(item: MissionItem) -> bool:
        return item.latitude is not None and item.longitude is not None

    @staticmethod
    def _format_coord(value):
        return "--" if value is None else f"{float(value):.6f}"

    @staticmethod
    def _format_number(value, decimals: int):
        return "--" if value is None else f"{float(value):.{decimals}f}"

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

    def _emit_type_change(self, sequence: int, combo: QComboBox):
        if self._updating_table:
            return
        self.item_type_changed.emit(sequence, combo.currentData())

    def _set_frame_combo(self, row: int, column: int, value: str, sequence: int):
        combo = QComboBox()
        for frame in ("Relative", "Absolute", "Terrain"):
            combo.addItem(frame, frame)
        index = combo.findText(self._normalize_frame(value))
        combo.setCurrentIndex(max(0, index))
        combo.currentTextChanged.connect(lambda text, seq=sequence: self._emit_frame_change(seq, text))
        self.table.setCellWidget(row, column, combo)

    def _emit_frame_change(self, sequence: int, frame: str):
        if self._updating_table:
            return
        for item in self.mission_items:
            if item.sequence == sequence:
                params = dict(item.parameters or {})
                params["frame"] = self._normalize_frame(frame)
                self.item_updated.emit(sequence, {"parameters": params})
                return

    @staticmethod
    def _normalize_frame(frame: str) -> str:
        text = str(frame or "").strip().casefold()
        if text in {"absolute", "global"}:
            return "Absolute"
        if text in {"terrain", "global_terrain_alt"}:
            return "Terrain"
        return "Relative"

    def _on_selection_changed(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            if row < len(self.mission_items):
                self.item_selected.emit(self.mission_items[row].sequence)

    def _remove_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            if row < len(self.mission_items):
                self.item_remove_requested.emit(self.mission_items[row].sequence)

    def select_sequence(self, sequence: int):
        for row, item in enumerate(self.mission_items):
            if item.sequence == sequence:
                self.table.selectRow(row)
                break
