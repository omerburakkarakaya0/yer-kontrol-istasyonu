"""
Logs tab.

Telemetry/video state and runtime log records are shown without changing the
central AppLogger signal contract.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class LogsTab(QWidget):
    def __init__(self, logger, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.auto_scroll = True
        self.init_ui()

        self.logger.log_added.connect(self._append_log_entry)
        self.logger.logs_cleared.connect(lambda: self.log_table.setRowCount(0))

        for entry in self.logger.logs:
            self._append_log_entry(entry)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        self.setObjectName("cockpitPage")

        status_group = QGroupBox("SISTEM DURUMU")
        status_group.setObjectName("bluePanel")
        status_layout = QHBoxLayout(status_group)
        status_layout.setContentsMargins(16, 18, 16, 14)
        status_layout.setSpacing(14)

        telemetry_card = self._build_status_card("TELEMETRİ")
        self.telemetry_status = telemetry_card.findChild(QLabel, "statusValue")
        status_layout.addWidget(telemetry_card)

        video_card = self._build_status_card("KAMERA")
        self.video_status = video_card.findChild(QLabel, "statusValue")
        status_layout.addWidget(video_card)
        status_layout.addStretch()
        layout.addWidget(status_group)

        log_group = QGroupBox("LOG KAYITLARI")
        log_group.setObjectName("bluePanel")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(14, 18, 14, 14)
        log_layout.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.addStretch()

        self.auto_scroll_check = QCheckBox("Auto Scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.toggled.connect(self._set_auto_scroll)
        top_bar.addWidget(self.auto_scroll_check)

        clear_btn = QPushButton("Log'ları Temizle")
        clear_btn.setObjectName("ghostButton")
        clear_btn.clicked.connect(self.logger.clear)
        top_bar.addWidget(clear_btn)
        log_layout.addLayout(top_bar)

        self.log_table = QTableWidget(0, 4)
        self.log_table.setObjectName("logTable")
        self.log_table.setHorizontalHeaderLabels(["SAAT", "SEVIYE", "KAYNAK", "MESAJ"])
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setAlternatingRowColors(False)
        self.log_table.setWordWrap(False)

        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.log_table.setColumnWidth(0, 110)
        self.log_table.setColumnWidth(1, 100)
        self.log_table.setColumnWidth(2, 120)
        log_layout.addWidget(self.log_table, 1)
        layout.addWidget(log_group, 1)

        self.setStyleSheet("""
            #cockpitPage {
                background-color: #090c0a;
                color: #e0e7dc;
            }
            QLabel {
                background-color: transparent;
                color: #e0e7dc;
            }
            QGroupBox#bluePanel {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #141d16, stop:1 #090c0a);
                border: 1px solid #3b5740;
                border-radius: 8px;
                margin-top: 14px;
                color: #f0f3eb;
                font-weight: 700;
            }
            QGroupBox#bluePanel::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
                color: #f0f3eb;
            }
            QFrame#statusCard {
                background-color: rgba(7, 18, 30, 210);
                border: 1px solid #2c3b2e;
                border-radius: 7px;
                min-width: 250px;
            }
            QFrame#statusCard[connected="true"] {
                background-color: rgba(13, 54, 32, 180);
                border-color: #1f7f4a;
            }
            QFrame#statusCard[connected="false"] {
                background-color: rgba(54, 18, 24, 180);
                border-color: #803040;
            }
            QLabel#statusTitle {
                color: #a1af9c;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#statusValue {
                color: #ff626d;
                font-size: 20px;
                font-weight: 800;
            }
            QFrame#statusCard[connected="true"] QLabel#statusValue {
                color: #63ee74;
            }
            QTableWidget#logTable {
                background-color: rgba(2, 8, 15, 230);
                color: #f0f3eb;
                border: 1px solid #2c3b2e;
                gridline-color: #202c23;
                font-family: Consolas, "Courier New", monospace;
                font-size: 13px;
                selection-background-color: #124020;
            }
            QHeaderView::section {
                background-color: #141d16;
                color: #a1af9c;
                border: none;
                border-right: 1px solid #2c3b2e;
                border-bottom: 1px solid #2c3b2e;
                padding: 7px 10px;
                font-weight: 700;
            }
            QPushButton#ghostButton {
                background-color: #111712;
                border: 1px solid #2c3b2e;
                border-radius: 5px;
                color: #f0f3eb;
                padding: 7px 14px;
                text-transform: uppercase;
            }
            QPushButton#ghostButton:hover {
                border-color: #577b59;
                background-color: #1b2a1e;
            }
            QCheckBox {
                color: #a1af9c;
                spacing: 8px;
                font-weight: 600;
            }
        """)

        self.update_telemetry_status(False)
        self.update_video_status(False)

    def _build_status_card(self, title: str):
        card = QFrame()
        card.setObjectName("statusCard")
        card.setProperty("connected", False)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("statusTitle")
        value_label = QLabel("BAĞLI DEĞİL")
        value_label.setObjectName("statusValue")

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        return card

    def _append_log_entry(self, entry: dict):
        level = entry.get("level", "INFO").upper()
        timestamp = entry.get("time", "--:--:--")
        message = entry.get("message", "")
        source = self._source_for_message(message)

        row = self.log_table.rowCount()
        self.log_table.insertRow(row)

        color = {
            "INFO": "#7ea783",
            "SUCCESS": "#51f06c",
            "WARNING": "#f6b82d",
            "ERROR": "#ff6570",
        }.get(level, "#f0f3eb")

        values = [timestamp, level, source, message]
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setForeground(QBrush(QColor(color if col in (0, 1, 3) else "#a1af9c")))
            item.setBackground(QBrush(QColor("#0b0e0c")))
            if col == 1:
                item.setTextAlignment(Qt.AlignCenter)
            self.log_table.setItem(row, col, item)

        if self.auto_scroll:
            scrollbar = self.log_table.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def add_log(self, level: str, message: str):
        self.logger.log(level, message)

    def _set_auto_scroll(self, checked: bool):
        self.auto_scroll = checked

    def update_telemetry_status(self, connected: bool):
        self.telemetry_status.setText("BAĞLI" if connected else "BAĞLI DEĞİL")
        self._set_status_card_state(self.telemetry_status, connected)

    def update_video_status(self, connected: bool):
        self.video_status.setText("BAĞLI" if connected else "BAĞLI DEĞİL")
        self._set_status_card_state(self.video_status, connected)

    @staticmethod
    def _source_for_message(message: str) -> str:
        text = str(message or "").lower()
        if "telemetry" in text or "mavlink" in text:
            return "TELEMETRY"
        if "video" in text or "kamera" in text:
            return "VIDEO"
        if "mission" in text or "waypoint" in text or "fence" in text:
            return "MISSION"
        if "worker" in text or "perf" in text:
            return "PERF"
        return "SYSTEM"

    @staticmethod
    def _set_status_card_state(label: QLabel, connected: bool):
        label.setStyleSheet(
            "color: #63ee74; font-size: 20px; font-weight: 800;"
            if connected
            else "color: #ff626d; font-size: 20px; font-weight: 800;"
        )
        card = label.parentWidget()
        if card is not None:
            card.setProperty("connected", bool(connected))
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()
