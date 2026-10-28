from PyQt5.QtCore import QObject, pyqtSignal
from datetime import datetime


class AppLogger(QObject):
    log_added = pyqtSignal(dict)
    logs_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logs = []

    def log(self, level: str, message: str):
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level.upper(),
            "message": message,
        }
        self.logs.append(entry)
        self.log_added.emit(entry)

    def info(self, message: str):
        self.log("INFO", message)

    def success(self, message: str):
        self.log("SUCCESS", message)

    def warning(self, message: str):
        self.log("WARNING", message)

    def error(self, message: str):
        self.log("ERROR", message)

    def clear(self):
        self.logs.clear()
        self.logs_cleared.emit()