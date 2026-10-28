import threading
import time

from PyQt5.QtCore import QThread, pyqtSignal

from backend.telemetry.manager import TelemetryManager
from core.parameter_metadata import parameter_metadata_store


class TelemetryWorker(QThread):
    telemetry_received = pyqtSignal(object)
    connection_status_changed = pyqtSignal(bool)
    log_message = pyqtSignal(str, str)
    mission_downloaded = pyqtSignal(object)
    fence_downloaded = pyqtSignal(object)
    parameters_downloaded = pyqtSignal(object)
    parameters_download_failed = pyqtSignal(str)
    parameters_written = pyqtSignal(object)
    parameters_write_failed = pyqtSignal(str)
    guided_target_completed = pyqtSignal(object)
    guided_target_failed = pyqtSignal(str)
    mode_change_completed = pyqtSignal(object)
    mode_change_failed = pyqtSignal(str)

    def __init__(self, parent=None, autostart_simulation: bool = True):
        super().__init__(parent)
        self.running = False
        self.connected = False
        self.connection_config = {"type": "Demo", "target": "", "baud": ""}
        self.manager = TelemetryManager(log_callback=self._emit_backend_log)
        self._lock = threading.Lock()
        self._pending_connect_config = dict(self.connection_config) if autostart_simulation else None
        self._pending_disconnect = False
        self._pending_mode_name = None
        self._pending_guided_target = None
        self._pending_mission_plan = None
        self._pending_mission_download = False
        self._pending_parameter_download = False
        self._pending_parameter_writes = None
        self._mission_busy = False
        self._last_status = None
        self._last_emit = 0.0
        self.ui_rate_hz = 25.0

    def run(self):
        self.running = True
        self._publish_status(False)

        while self.running:
            self._process_pending_commands()

            telemetry = None
            if self.manager.backend is not None:
                try:
                    telemetry = self.manager.read(timeout=0.05)
                except Exception as exc:
                    self.log_message.emit("ERROR", f"Telemetry read error: {exc}")
                    self._disconnect_backend()

            self._publish_status(self.manager.connected)

            if telemetry is not None and self._should_emit():
                self.telemetry_received.emit(telemetry)

            if self.manager.backend is None:
                self.msleep(50)

        self._disconnect_backend()
        self._publish_status(False)

    def stop(self):
        self.running = False
        self.wait(6000)

    def connect_backend(self, cfg: dict):
        if isinstance(cfg, dict):
            with self._lock:
                self.connection_config.update(cfg)
                self._pending_connect_config = dict(self.connection_config)
                self._pending_disconnect = False

    def disconnect_backend(self):
        with self._lock:
            self._pending_disconnect = True
            self._pending_connect_config = None

    def request_mode_change(self, mode_name: str):
        with self._lock:
            self._pending_mode_name = str(mode_name or "").strip()

    def request_guided_target(self, latitude: float, longitude: float, altitude: float):
        with self._lock:
            if self._transfer_in_progress():
                self.guided_target_failed.emit("MAVLink transferi sürerken Guided hedef gönderilemez")
                return
            self._pending_guided_target = (float(latitude), float(longitude), float(altitude))

    def upload_mission(self, mission_items, fence_zones=None):
        with self._lock:
            if self._transfer_in_progress():
                self.log_message.emit("WARNING", "Mission transfer already in progress")
                return
            self._pending_mission_plan = (list(mission_items or []), list(fence_zones or []))

    def download_mission(self):
        with self._lock:
            if self._transfer_in_progress():
                self.log_message.emit("WARNING", "Mission transfer already in progress")
                return
            self._pending_mission_download = True

    def download_parameters(self):
        with self._lock:
            if self._transfer_in_progress():
                self.log_message.emit("WARNING", "Transfer already in progress")
                self.parameters_download_failed.emit("Another MAVLink transfer is already in progress")
                return
            self._pending_parameter_download = True

    def write_parameters(self, updates):
        updates = list(updates or [])
        if not updates:
            self.parameters_written.emit({"written": [], "failed": []})
            return
        with self._lock:
            if self._transfer_in_progress():
                self.log_message.emit("WARNING", "Transfer already in progress")
                self.parameters_write_failed.emit("Another MAVLink transfer is already in progress")
                return
            self._pending_parameter_writes = updates

    def _transfer_in_progress(self):
        return bool(
            self._mission_busy
            or self._pending_mission_plan is not None
            or self._pending_mission_download
            or self._pending_parameter_download
            or self._pending_parameter_writes is not None
        )

    def configure_connection(self, cfg: dict):
        if isinstance(cfg, dict):
            with self._lock:
                self.connection_config.update(cfg)

    def set_connection_status(self, connected: bool):
        if connected:
            self.connect_backend(self.connection_config)
        else:
            self.disconnect_backend()

    def _process_pending_commands(self):
        with self._lock:
            disconnect_requested = self._pending_disconnect
            connect_config = self._pending_connect_config
            mode_name = self._pending_mode_name
            guided_target = self._pending_guided_target
            mission_plan = self._pending_mission_plan
            download_mission = self._pending_mission_download
            download_parameters = self._pending_parameter_download
            parameter_writes = self._pending_parameter_writes
            self._pending_disconnect = False
            self._pending_connect_config = None
            self._pending_mode_name = None
            self._pending_guided_target = None
            self._pending_mission_plan = None
            self._pending_mission_download = False
            self._pending_parameter_download = False
            self._pending_parameter_writes = None

        if disconnect_requested:
            self._disconnect_backend()
            self.log_message.emit("WARNING", "Telemetry disconnect requested")

        if connect_config is not None:
            self._connect_backend(connect_config)

        if mode_name:
            self._set_mode(mode_name)

        if guided_target is not None:
            self._goto_guided(*guided_target)

        if mission_plan is not None:
            mission_items, fence_zones = mission_plan
            self._upload_mission(mission_items, fence_zones)

        if download_mission:
            self._download_mission()

        if download_parameters:
            self._download_parameters()

        if parameter_writes is not None:
            self._write_parameters(parameter_writes)

    def _connect_backend(self, cfg: dict):
        try:
            self.log_message.emit("INFO", f"Telemetry connect requested: {cfg}")
            self.manager.connect(cfg)
            self.log_message.emit("SUCCESS", f"Telemetry backend active: {cfg.get('type', 'Demo')}")
        except Exception as exc:
            self.log_message.emit("ERROR", f"Telemetry connection failed: {exc}")
            self._disconnect_backend()

    def _disconnect_backend(self):
        try:
            self.manager.disconnect()
        except Exception as exc:
            self.log_message.emit("WARNING", f"Telemetry disconnect warning: {exc}")

    def _set_mode(self, mode_name: str):
        try:
            result = dict(self.manager.set_mode(mode_name) or {})
            result.setdefault("mode", str(mode_name or "").strip().upper())
            self.mode_change_completed.emit(result)
            self.log_message.emit("SUCCESS", f"Mode change confirmed: {result['mode']}")
        except Exception as exc:
            message = f"Mode change failed ({mode_name}): {exc}"
            self.mode_change_failed.emit(message)
            self.log_message.emit("ERROR", message)

    def _goto_guided(self, latitude: float, longitude: float, altitude: float):
        try:
            result = self.manager.goto_guided(latitude, longitude, altitude)
            payload = dict(result or {})
            payload.setdefault("latitude", latitude)
            payload.setdefault("longitude", longitude)
            payload.setdefault("altitude", altitude)
            payload.setdefault("mode", "GUIDED")
            self.guided_target_completed.emit(payload)
            self.log_message.emit(
                "SUCCESS",
                f"Guided hedef gönderildi: {latitude:.7f}, {longitude:.7f}, {altitude:.1f} m",
            )
        except Exception as exc:
            message = f"Guided hedef gönderilemedi: {exc}"
            self.guided_target_failed.emit(message)
            self.log_message.emit("ERROR", message)

    def _upload_mission(self, mission_items, fence_zones=None):
        self._mission_busy = True
        try:
            fence_zones = list(fence_zones or [])
            self.manager.upload_mission(mission_items, fence_zones)
            self.log_message.emit("SUCCESS", "Mission upload command completed")
            downloaded = self.manager.download_mission()
            self.mission_downloaded.emit(downloaded)
            self.log_message.emit("SUCCESS", f"Mission verified from Pixhawk: {len(downloaded)} items")
            for item in downloaded:
                self.log_message.emit(
                    "INFO",
                    (
                        f"Verified mission item: seq={getattr(item, 'sequence', '?')} "
                        f"type={getattr(getattr(item, 'item_type', None), 'value', getattr(item, 'item_type', '?'))} "
                        f"lat={getattr(item, 'latitude', None)} lon={getattr(item, 'longitude', None)} "
                        f"alt={getattr(item, 'altitude', None)}"
                    )
                )
            downloaded_fence = self.manager.download_fence()
            self.fence_downloaded.emit(downloaded_fence)
            self.log_message.emit("SUCCESS", f"Fence verified from Pixhawk: {len(downloaded_fence)} zones")
            for index, zone in enumerate(downloaded_fence):
                self.log_message.emit(
                    "INFO",
                    (
                        f"Verified fence zone: seq={index} "
                        f"lat={getattr(zone, 'center_lat', None)} lon={getattr(zone, 'center_lon', None)} "
                        f"radius={getattr(zone, 'radius_m', None)}"
                    )
                )
        except Exception as exc:
            self.log_message.emit("ERROR", f"Mission upload failed: {exc}")
        finally:
            self._mission_busy = False

    def _download_mission(self):
        self._mission_busy = True
        try:
            mission_items = self.manager.download_mission()
            self.mission_downloaded.emit(mission_items)
            self.log_message.emit("SUCCESS", f"Mission downloaded: {len(mission_items)} items")
            try:
                fence_zones = self.manager.download_fence()
                self.fence_downloaded.emit(fence_zones)
                self.log_message.emit("SUCCESS", f"Fence downloaded: {len(fence_zones)} zones")
            except Exception as exc:
                self.log_message.emit("WARNING", f"Fence download skipped: {exc}")
        except Exception as exc:
            self.log_message.emit("ERROR", f"Mission download failed: {exc}")
        finally:
            self._mission_busy = False

    def _download_parameters(self):
        self._mission_busy = True
        try:
            params = self.manager.download_parameters()
            try:
                params = parameter_metadata_store.enrich(params)
                described = sum(1 for item in params if item.get("description"))
                self.log_message.emit("SUCCESS", f"Parameter metadata matched: {described}/{len(params)} items")
            except Exception as exc:
                self.log_message.emit("WARNING", f"Parameter metadata skipped: {exc}")
            self.parameters_downloaded.emit(params)
            self.log_message.emit("SUCCESS", f"Parameters downloaded: {len(params)} items")
        except Exception as exc:
            self.log_message.emit("ERROR", f"Parameter download failed: {exc}")
            self.parameters_download_failed.emit(str(exc))
        finally:
            self._mission_busy = False

    def _write_parameters(self, updates):
        self._mission_busy = True
        try:
            result = self.manager.write_parameters(updates)
            result = result if isinstance(result, dict) else {"written": [], "failed": []}
            written = list(result.get("written") or [])
            failed = list(result.get("failed") or [])
            self.parameters_written.emit({"written": written, "failed": failed})
            self.log_message.emit(
                "SUCCESS" if not failed else "WARNING",
                f"Parameter write complete: {len(written)} verified, {len(failed)} failed",
            )
        except Exception as exc:
            self.log_message.emit("ERROR", f"Parameter write failed: {exc}")
            self.parameters_write_failed.emit(str(exc))
        finally:
            self._mission_busy = False

    def _publish_status(self, connected: bool):
        self.connected = connected
        if self._last_status is connected:
            return
        self._last_status = connected
        self.connection_status_changed.emit(connected)

    def _should_emit(self) -> bool:
        now = time.time()
        min_interval = 1.0 / max(1.0, float(self.ui_rate_hz))
        if now - self._last_emit < min_interval:
            return False
        self._last_emit = now
        return True

    def _emit_backend_log(self, level: str, message: str):
        self.log_message.emit(level.upper(), message)
