"""Small, bounded live view of the application's shared log stream."""
from PyQt5.QtWidgets import QGroupBox, QPlainTextEdit, QVBoxLayout


class FlightLogsWidget(QGroupBox):
    def __init__(self, logger=None, parent=None):
        super().__init__("LOGS", parent)
        self.setObjectName("bluePanel")
        self.setMinimumHeight(112)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 14, 8, 8)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("flightLogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(200)
        self.log_view.setPlaceholderText("Sistem kayıtları burada görünecek.")
        self.log_view.setStyleSheet("""
            QPlainTextEdit {
                background: #0b0e0c; color: #b9c7b1;
                border: none; border-radius: 5px;
                font-family: 'Segoe UI'; font-size: 10px; padding: 3px;
                selection-background-color: #213b28;
            }
            QScrollBar:vertical { width: 6px; }
        """)
        layout.addWidget(self.log_view)
        if logger is not None:
            for entry in logger.logs[-200:]:
                self.append_entry(entry)
            logger.log_added.connect(self.append_entry)
            logger.logs_cleared.connect(self.log_view.clear)

    def append_entry(self, entry):
        scrollbar = self.log_view.verticalScrollBar()
        follow_latest = scrollbar.value() >= scrollbar.maximum() - 1
        previous_position = scrollbar.value()
        self.log_view.appendPlainText(
            f"{entry.get('time', '--:--:--')}  {entry.get('level', 'INFO')}  "
            f"{entry.get('message', '')}"
        )
        scrollbar.setValue(scrollbar.maximum() if follow_latest else previous_position)
