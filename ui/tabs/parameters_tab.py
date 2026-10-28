from collections import defaultdict
import math
import re

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QSplitter, QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QCheckBox, QFrame
)


class ParametersTab(QWidget):
    refresh_requested = pyqtSignal()
    write_requested = pyqtSignal(list)

    def __init__(self, logger=None, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.parameters = []
        self.pending_changes = {}
        self.active_group = "All"
        self.only_modified = False
        self._populating_table = False
        self._loading = False
        self._writing = False
        self.init_ui()

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)
        self.setObjectName("cockpitPage")

        status_panel = QFrame()
        status_panel.setObjectName("statusPanel")
        top_bar = QHBoxLayout(status_panel)
        top_bar.setContentsMargins(16, 10, 16, 10)
        top_bar.setSpacing(12)
        self.status_dot = QLabel("")
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setAlignment(Qt.AlignCenter)
        top_bar.addWidget(self.status_dot)

        status_text = QVBoxLayout()
        status_text.setSpacing(1)
        self.status_label = QLabel("Parameters: not loaded")
        self.status_label.setObjectName("statusTitle")
        self.status_detail_label = QLabel("Pixhawk parametreleri henüz okunmadı.")
        self.status_detail_label.setObjectName("mutedLabel")
        status_text.addWidget(self.status_label)
        status_text.addWidget(self.status_detail_label)
        top_bar.addLayout(status_text)
        top_bar.addStretch()

        self.refresh_btn = QPushButton("Read Pixhawk Parameters")
        self.refresh_btn.setObjectName("primaryButton")
        self.refresh_btn.clicked.connect(self._request_refresh)
        top_bar.addWidget(self.refresh_btn)
        root.addWidget(status_panel)

        content_shell = QFrame()
        content_shell.setObjectName("contentShell")
        content_layout = QHBoxLayout(content_shell)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)

        group_panel = QGroupBox("PARAMETRE GRUPLARI")
        group_panel.setObjectName("bluePanel")
        group_layout = QVBoxLayout(group_panel)
        group_layout.setContentsMargins(8, 18, 8, 8)
        self.group_tree = QTreeWidget()
        self.group_tree.setObjectName("categoryTree")
        self.group_tree.setHeaderHidden(True)
        self.group_tree.itemClicked.connect(self._on_group_clicked)
        group_layout.addWidget(self.group_tree)
        splitter.addWidget(group_panel)

        table_panel = QFrame()
        table_panel.setObjectName("tablePanel")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(8, 8, 8, 8)
        table_layout.setSpacing(8)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Parametre ara... (or. BAT_, EKF2_, NAV_)")
        self.search_input.textChanged.connect(self._refresh_table)
        search_row.addWidget(self.search_input, 1)
        filter_btn = QPushButton("Filtreler")
        filter_btn.setObjectName("ghostButton")
        filter_btn.setEnabled(False)
        search_row.addWidget(filter_btn)
        table_layout.addLayout(search_row)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName("parameterTable")
        self.table.setHorizontalHeaderLabels(["Name", "Value", "Default", "Units", "Options", "Desc"])
        self.table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed | QTableWidget.AnyKeyPressed
        )
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 165)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 82)
        self.table.setColumnWidth(4, 190)
        table_layout.addWidget(self.table, 1)
        splitter.addWidget(table_panel)

        side_group = QGroupBox("Parameter Tools")
        side_group.setObjectName("bluePanel")
        side_layout = QVBoxLayout(side_group)
        side_layout.setContentsMargins(14, 22, 14, 14)
        side_layout.setSpacing(12)
        self.write_btn = QPushButton("İşlemleri Güncelle")
        self.write_btn.setObjectName("primaryButton")
        self.write_btn.clicked.connect(self._request_write)
        self.write_btn.setEnabled(False)
        side_layout.addWidget(self.write_btn)

        self.modified_check = QCheckBox("Modified")
        self.modified_check.toggled.connect(self._set_modified_filter)
        side_layout.addWidget(self.modified_check)

        self.info_label = QLabel(
            "Value hücresine çift tıklayarak değeri düzenleyin.\n\n"
            "Değişiklikler Pixhawk'a MAVLink PARAM_SET ile gönderilir ve "
            "PARAM_VALUE cevabıyla doğrulanır.\n\n"
            "Kırmızı değerleri düzeltmeden güncelleme yapılamaz."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setObjectName("infoBox")
        side_layout.addWidget(self.info_label)
        side_layout.addStretch()
        splitter.addWidget(side_group)

        splitter.setSizes([220, 1000, 260])
        content_layout.addWidget(splitter)
        root.addWidget(content_shell, 1)

        self.setStyleSheet("""
            #cockpitPage {
                background-color: #090c0a;
                color: #e0e7dc;
            }
            QFrame#statusPanel, QFrame#contentShell {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #141d16, stop:1 #090c0a);
                border: 1px solid #2c3b2e;
                border-radius: 8px;
            }
            QFrame#contentShell {
                border-color: #3b5740;
            }
            QLabel#statusDot {
                color: #6df277;
                border: 1px solid #327e4c;
                border-radius: 13px;
                min-width: 26px;
                max-width: 26px;
                min-height: 26px;
                max-height: 26px;
                qproperty-alignment: AlignCenter;
                font-size: 16px;
                font-weight: 800;
            }
            QLabel#statusTitle {
                color: #f0f3eb;
                font-weight: 800;
                font-size: 14px;
            }
            QLabel#mutedLabel {
                color: #a1af9c;
            }
            QGroupBox#bluePanel {
                background-color: rgba(5, 13, 22, 220);
                border: 1px solid #2c3b2e;
                border-radius: 7px;
                margin-top: 14px;
                color: #b4ceac;
                font-weight: 800;
            }
            QGroupBox#bluePanel::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QFrame#tablePanel {
                background-color: rgba(4, 11, 19, 230);
                border: 1px solid #2c3b2e;
                border-radius: 7px;
            }
            QLineEdit#searchInput {
                background-color: #111712;
                color: #f0f3eb;
                border: 1px solid #2c3b2e;
                border-radius: 5px;
                padding: 9px 12px;
                selection-background-color: #03631b;
            }
            QLineEdit#searchInput:focus {
                border-color: #577b59;
            }
            QTreeWidget#categoryTree {
                background-color: transparent;
                color: #b9c7b1;
                border: none;
                outline: none;
                selection-background-color: #124020;
                selection-color: #f0f3eb;
                font-size: 13px;
            }
            QTreeWidget#categoryTree::item {
                min-height: 30px;
                padding: 4px 8px;
                border-radius: 5px;
            }
            QTreeWidget#categoryTree::item:selected {
                background-color: #17642b;
                color: #f0f3eb;
            }
            QTableWidget#parameterTable {
                background-color: #0b0e0c;
                color: #f0f3eb;
                border: 1px solid #2c3b2e;
                gridline-color: #202c23;
                alternate-background-color: #0e140f;
                selection-background-color: #124020;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #141d16;
                color: #e0e7dc;
                border: none;
                border-right: 1px solid #2c3b2e;
                border-bottom: 1px solid #2c3b2e;
                padding: 7px;
                font-weight: 700;
            }
            QTableWidget::item {
                background-color: #0b0e0c;
                color: #f0f3eb;
                padding: 4px;
            }
            QTableWidget::item:alternate {
                background-color: #0e140f;
                color: #f0f3eb;
            }
            QTableWidget::item:selected {
                background-color: #124020;
                color: white;
            }
            QPushButton#primaryButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #124020, stop:1 #102c18);
                color: #f0f3eb;
                border: 1px solid #577b59;
                border-radius: 5px;
                padding: 10px 18px;
                font-weight: 700;
            }
            QPushButton#primaryButton:hover {
                background-color: #17642b;
            }
            QPushButton#ghostButton {
                background-color: #111712;
                border: 1px solid #2c3b2e;
                border-radius: 5px;
                color: #f0f3eb;
                padding: 9px 14px;
            }
            QLabel#infoBox {
                background-color: rgba(9, 20, 33, 210);
                border: 1px solid #2c3b2e;
                border-radius: 7px;
                color: #a1af9c;
                padding: 14px;
                line-height: 150%;
            }
            QCheckBox {
                color: #e0e7dc;
                spacing: 8px;
            }
        """)

        self._rebuild_groups()

    def set_loading(self, loading: bool):
        self._loading = bool(loading)
        self.refresh_btn.setEnabled(not self._loading and not self._writing)
        self.table.setEnabled(not self._loading and not self._writing)
        self._update_write_button()
        if self._loading:
            self.status_dot.setText("…")
            self.status_label.setText("Parameters: reading from Pixhawk...")
            self.status_detail_label.setText("Pixhawk PARAM_VALUE verileri bekleniyor.")

    def set_writing(self, writing: bool):
        self._writing = bool(writing)
        self.refresh_btn.setEnabled(not self._loading and not self._writing)
        self.table.setEnabled(not self._loading and not self._writing)
        self._update_write_button()
        if self._writing:
            self.status_dot.setText("…")
            self.status_label.setText("Parameters: writing to Pixhawk...")
            self.status_detail_label.setText("PARAM_SET gönderildi; PARAM_VALUE doğrulaması bekleniyor.")

    def set_parameters(self, parameters):
        self.parameters = [dict(param) for param in list(parameters or [])]
        self.pending_changes.clear()
        for param in self.parameters:
            param["_original_value"] = param.get("value")
            param["modified"] = False
        self.active_group = "All"
        self._rebuild_groups()
        self._refresh_table()

    def _request_refresh(self):
        if self.pending_changes:
            self.status_dot.setText("!")
            self.status_label.setText("Parameters: unapplied changes")
            self.status_detail_label.setText(
                "Parametreleri yeniden okumadan önce değişiklikleri uygulayın veya eski değere döndürün."
            )
            return
        self.set_loading(True)
        self.refresh_requested.emit()

    def _request_write(self):
        if self._loading or self._writing:
            return
        invalid = [change for change in self.pending_changes.values() if change.get("error")]
        if invalid:
            self.status_dot.setText("!")
            self.status_label.setText("Parameters: invalid value")
            self.status_detail_label.setText(str(invalid[0].get("error")))
            return

        updates = [
            {
                "name": change["name"],
                "value": change["value"],
                "type": change.get("type", 9),
            }
            for change in self.pending_changes.values()
        ]
        if not updates:
            return
        self.set_writing(True)
        self.write_requested.emit(updates)

    def apply_write_result(self, result):
        result = result if isinstance(result, dict) else {}
        written = list(result.get("written") or [])
        failed = list(result.get("failed") or [])
        params_by_name = {str(param.get("name", "")): param for param in self.parameters}

        for item in written:
            name = str(item.get("name", ""))
            param = params_by_name.get(name)
            if param is None:
                continue
            confirmed = item.get("value", param.get("value"))
            param["value"] = confirmed
            param["_original_value"] = confirmed
            param["modified"] = False
            self.pending_changes.pop(name, None)

        for item in failed:
            name = str(item.get("name", ""))
            change = self.pending_changes.get(name)
            if change is not None:
                change["write_error"] = str(item.get("error") or "Pixhawk değişikliği doğrulamadı")

        self.set_writing(False)
        self._refresh_table()
        if failed:
            self.status_dot.setText("!")
            self.status_label.setText(
                f"Parameters: {len(written)} updated, {len(failed)} failed"
            )
            self.status_detail_label.setText(str(failed[0].get("error") or "Yazma işlemi başarısız."))
        else:
            self.status_dot.setText("✓")
            self.status_label.setText(f"Parameters: {len(written)} updated and verified")
            self.status_detail_label.setText("Pixhawk PARAM_VALUE cevabı yeni değerleri doğruladı.")

    def set_write_error(self, message: str):
        self.set_writing(False)
        self.status_dot.setText("!")
        self.status_label.setText("Parameters: write failed")
        self.status_detail_label.setText(str(message or "Parametre yazma işlemi başarısız."))

    def _set_modified_filter(self, checked: bool):
        self.only_modified = bool(checked)
        self._refresh_table()

    def _rebuild_groups(self):
        self.group_tree.clear()
        root = QTreeWidgetItem(["All"])
        self.group_tree.addTopLevelItem(root)

        groups = defaultdict(int)
        for param in self.parameters:
            groups[str(param.get("group") or self._group_for_name(param.get("name", "")))] += 1

        for group, count in sorted(groups.items()):
            item = QTreeWidgetItem([f"{group} ({count})"])
            item.setData(0, Qt.UserRole, group)
            root.addChild(item)

        root.setExpanded(True)
        self.group_tree.setCurrentItem(root)

    def _refresh_table(self):
        query = self.search_input.text().strip().lower()
        rows = []
        for param in self.parameters:
            name = str(param.get("name", ""))
            group = str(param.get("group") or self._group_for_name(name))
            if self.active_group != "All" and group != self.active_group:
                continue
            if query and query not in name.lower():
                continue
            if self.only_modified and not bool(param.get("modified", False)):
                continue
            rows.append(param)

        previous_blocked = self.table.blockSignals(True)
        self._populating_table = True
        try:
            self.table.setRowCount(len(rows))
            for row, param in enumerate(rows):
                name = str(param.get("name", ""))
                pending = self.pending_changes.get(name, {})
                value_text = pending.get("text", self._format_value(param.get("value")))
                values = [
                    name,
                    value_text,
                    self._format_value(param.get("default", param.get("value"))),
                    str(param.get("units", "")),
                    str(param.get("options") or param.get("range", "")),
                    str(param.get("description", "")),
                ]
                tooltip = self._tooltip_for_param(param)
                row_bg = QColor("#0b0e0c") if row % 2 == 0 else QColor("#0e140f")
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(tooltip)
                    item.setForeground(QBrush(QColor("#f0f3eb")))
                    item.setBackground(QBrush(row_bg))
                    if col == 1:
                        item.setData(Qt.UserRole, name)
                        item.setFlags(item.flags() | Qt.ItemIsEditable)
                        self._style_value_item(item, pending, row_bg)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    if col in (1, 2):
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.table.setItem(row, col, item)
        finally:
            self._populating_table = False
            self.table.blockSignals(previous_blocked)

        total = len(self.parameters)
        expected = max([int(p.get("count") or 0) for p in self.parameters], default=0)
        suffix = f" / {expected}" if expected else ""
        self.status_label.setText(f"Parameters: {total}{suffix} loaded, showing {len(rows)}")
        self.status_dot.setText("✓")
        self.status_detail_label.setText("Pixhawk parametreleri başarıyla okundu.")
        self.set_loading(False)
        self._update_write_button()

    def _on_item_changed(self, item):
        if self._populating_table or item is None or item.column() != 1:
            return
        name = str(item.data(Qt.UserRole) or "")
        param = next((entry for entry in self.parameters if str(entry.get("name", "")) == name), None)
        if param is None:
            return

        raw_text = item.text().strip()
        change = {
            "name": name,
            "text": raw_text,
            "type": int(param.get("type", 9) or 9),
        }
        try:
            value = self._parse_numeric_value(raw_text)
            limits = self._parse_range(param.get("range"))
            if limits is not None and not limits[0] <= value <= limits[1]:
                raise ValueError(
                    f"{name} değeri {self._format_value(limits[0])} ile "
                    f"{self._format_value(limits[1])} arasında olmalı."
                )
        except ValueError as exc:
            change["error"] = str(exc)
            self.pending_changes[name] = change
            param["modified"] = True
        else:
            original = param.get("_original_value", param.get("value"))
            if self._values_equal(value, original):
                self.pending_changes.pop(name, None)
                param["value"] = original
                param["modified"] = False
                change = {}
            else:
                change["value"] = value
                self.pending_changes[name] = change
                param["value"] = value
                param["modified"] = True

        row_bg = QColor("#0b0e0c") if item.row() % 2 == 0 else QColor("#0e140f")
        self._populating_table = True
        try:
            self._style_value_item(item, change, row_bg)
        finally:
            self._populating_table = False

        if self.only_modified:
            self._refresh_table()
        self._update_write_button()
        invalid = [entry for entry in self.pending_changes.values() if entry.get("error")]
        if invalid:
            self.status_dot.setText("!")
            self.status_label.setText("Parameters: invalid value")
            self.status_detail_label.setText(str(invalid[0]["error"]))
        elif self.pending_changes:
            self.status_dot.setText("*")
            self.status_label.setText(f"Parameters: {len(self.pending_changes)} modified")
            self.status_detail_label.setText(
                "Değişiklikleri Pixhawk'a göndermek için İşlemleri Güncelle'ye basın."
            )
        else:
            self.status_dot.setText("✓")
            self.status_label.setText("Parameters: no pending changes")
            self.status_detail_label.setText("Parametre değerleri Pixhawk ile eşleşiyor.")

    def _update_write_button(self):
        has_invalid = any(change.get("error") for change in self.pending_changes.values())
        self.write_btn.setEnabled(
            bool(self.pending_changes)
            and not has_invalid
            and not self._loading
            and not self._writing
        )

    @staticmethod
    def _style_value_item(item, change, row_bg):
        error = str(change.get("error") or change.get("write_error") or "")
        if error:
            item.setForeground(QBrush(QColor("#ffb4b4")))
            item.setBackground(QBrush(QColor("#4b151b")))
            item.setToolTip(error)
        elif change:
            item.setForeground(QBrush(QColor("#ffe070")))
            item.setBackground(QBrush(QColor("#3b2d08")))
        else:
            item.setForeground(QBrush(QColor("#f0f3eb")))
            item.setBackground(QBrush(row_bg))

    @staticmethod
    def _parse_numeric_value(text):
        normalized = str(text or "").strip()
        if not normalized:
            raise ValueError("Value alanı boş bırakılamaz.")
        if "," in normalized and "." not in normalized:
            normalized = normalized.replace(",", ".")
        try:
            value = float(normalized)
        except ValueError as exc:
            raise ValueError("Value alanına geçerli bir sayı girin.") from exc
        if not math.isfinite(value):
            raise ValueError("Value alanına sonlu bir sayı girin.")
        return value

    @staticmethod
    def _parse_range(range_text):
        matches = re.findall(
            r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?",
            str(range_text or ""),
        )
        if len(matches) < 2:
            return None
        low, high = float(matches[0]), float(matches[1])
        return (low, high) if low <= high else (high, low)

    @staticmethod
    def _values_equal(left, right):
        try:
            return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
        except (TypeError, ValueError):
            return str(left) == str(right)

    def _on_group_clicked(self, item, _column):
        if item.parent() is None:
            self.active_group = "All"
        else:
            self.active_group = item.data(0, Qt.UserRole) or item.text(0).split(" ", 1)[0]
        self._refresh_table()

    @staticmethod
    def _group_for_name(name: str) -> str:
        name = str(name or "")
        return name.split("_", 1)[0] if "_" in name else (name or "Other")

    @staticmethod
    def _format_value(value):
        try:
            numeric = float(value)
            if numeric.is_integer():
                return str(int(numeric))
            return f"{numeric:.7g}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _tooltip_for_param(param):
        lines = []
        display_name = str(param.get("display_name", "")).strip()
        description = str(param.get("description", "")).strip()
        units = str(param.get("units", "")).strip()
        options = str(param.get("options", "")).strip()
        range_text = str(param.get("range", "")).strip()
        increment = str(param.get("increment", "")).strip()
        user = str(param.get("user", "")).strip()
        if display_name:
            lines.append(display_name)
        if description:
            lines.append(description)
        if units:
            lines.append(f"Units: {units}")
        if options:
            lines.append(f"Options: {options}")
        if range_text:
            lines.append(f"Range: {range_text}")
        if increment:
            lines.append(f"Increment: {increment}")
        if user:
            lines.append(f"User: {user}")
        return "\n".join(lines)
