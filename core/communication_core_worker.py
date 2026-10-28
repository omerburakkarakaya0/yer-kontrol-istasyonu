import json
import threading
import time
import urllib.error
import urllib.request

from PyQt5.QtCore import QThread, pyqtSignal

from core.referee_telemetry import extract_opponent_positions


class CommunicationCoreStatusWorker(QThread):
    status_received = pyqtSignal(dict)
    log_message = pyqtSignal(str, str)

    def __init__(self, status_url="http://127.0.0.1:8090/status", poll_hz=1.0, parent=None):
        super().__init__(parent)
        self.status_url = status_url
        self.poll_hz = max(0.2, float(poll_hz))
        self._running = False
        self._was_connected = False
        self._snapshot_lock = threading.Lock()
        self._referee_snapshot_url = ""
        self._snapshot_unsupported_url = ""
        self._last_snapshot_count = None

    def set_referee_base_url(self, base_url: str):
        base_url = str(base_url or "").strip().rstrip("/")
        snapshot_url = f"{base_url}/hakem_veri" if base_url else ""
        with self._snapshot_lock:
            self._referee_snapshot_url = snapshot_url
            self._snapshot_unsupported_url = ""
            self._last_snapshot_count = None

    def run(self):
        self._running = True
        period = 1.0 / self.poll_hz

        while self._running:
            start = time.time()
            try:
                with urllib.request.urlopen(self.status_url, timeout=0.8) as response:
                    payload = response.read().decode("utf-8")
                status = json.loads(payload)
                status = self._merge_full_referee_snapshot(status)
                self.status_received.emit(status)
                if not self._was_connected:
                    self.log_message.emit("success", "Hakem status worker aktif")
                self._was_connected = True
            except Exception as exc:
                if self._was_connected:
                    self.log_message.emit("warning", f"Hakem status okunamadi: {exc}")
                self._was_connected = False

            sleep_for = period - (time.time() - start)
            if sleep_for > 0:
                time.sleep(sleep_for)

    def _merge_full_referee_snapshot(self, status: dict) -> dict:
        with self._snapshot_lock:
            snapshot_url = self._referee_snapshot_url
            unsupported = self._snapshot_unsupported_url == snapshot_url
        if not snapshot_url or unsupported:
            return status

        try:
            with urllib.request.urlopen(snapshot_url, timeout=0.8) as response:
                payload = response.read().decode("utf-8")
            snapshot = json.loads(payload)
            merged = self.merge_referee_snapshot(status, snapshot)
            count = len(extract_opponent_positions(merged.get("opponent_positions")))
            if count and count != self._last_snapshot_count:
                self.log_message.emit("success", f"Hakem tam SIHA listesi alindi: {count} takim")
            self._last_snapshot_count = count
            return merged
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 405):
                with self._snapshot_lock:
                    self._snapshot_unsupported_url = snapshot_url
            return status
        except Exception:
            return status

    @staticmethod
    def merge_referee_snapshot(status: dict, snapshot) -> dict:
        if not isinstance(status, dict) or not isinstance(snapshot, dict):
            return status
        positions = extract_opponent_positions(snapshot.get("takimlar"))
        if not positions:
            return status
        merged = dict(status)
        merged["opponent_positions"] = positions
        merged["opponent_positions_source"] = "hakem_veri"
        return merged

    def stop(self):
        self._running = False
        if self.isRunning():
            self.wait(1500)
