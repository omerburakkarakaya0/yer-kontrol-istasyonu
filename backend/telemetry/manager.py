from typing import Optional

from backend.telemetry.base import TelemetryBackend, TelemetryLogCallback
from backend.telemetry.cpp_bridge_backend import CppTelemetryBackend
from backend.telemetry.mavlink_backend import MavlinkTelemetryBackend
from backend.telemetry.simulation_backend import SimulationTelemetryBackend
from models.telemetry import TelemetryData


class TelemetryManager:
    def __init__(self, log_callback: Optional[TelemetryLogCallback] = None):
        self.log_callback = log_callback
        self.backend: Optional[TelemetryBackend] = None
        self.config = {"type": "Demo", "target": "", "baud": ""}

    @property
    def connected(self) -> bool:
        return bool(self.backend and self.backend.connected)

    def connect(self, config: Optional[dict] = None):
        if config:
            self.config.update(config)

        self.disconnect()
        self.backend = self._create_backend(self.config)
        try:
            self.backend.start()
        except Exception as exc:
            if isinstance(self.backend, CppTelemetryBackend):
                if self.log_callback:
                    self.log_callback("WARNING", f"C++ telemetry start failed, trying Python MAVLink backend: {exc}")
                self.backend = self._create_python_backend(self.config)
                self.backend.start()
            else:
                self.backend = None
                raise

    def disconnect(self):
        if self.backend is not None:
            self.backend.stop()
        self.backend = None

    def read(self, timeout: float = 0.2) -> Optional[TelemetryData]:
        if self.backend is None:
            return None
        return self.backend.read(timeout=timeout)

    def set_mode(self, mode_name: str):
        if self.backend is None:
            raise RuntimeError("Telemetry backend is not connected")
        return self.backend.set_mode(mode_name)

    def goto_guided(self, latitude: float, longitude: float, altitude: float):
        if self.backend is None:
            raise RuntimeError("Telemetry backend is not connected")
        return self.backend.goto_guided(latitude, longitude, altitude)

    def upload_mission(self, mission_items, fence_zones=None):
        if self.backend is None:
            raise RuntimeError("Telemetry backend is not connected")
        if isinstance(self.backend, CppTelemetryBackend):
            return self._with_python_mavlink_backend(
                lambda backend: self._upload_plan_with_backend(backend, mission_items, fence_zones)
            )
        self._upload_plan_with_backend(self.backend, mission_items, fence_zones)

    def upload_fence(self, fence_zones):
        if self.backend is None:
            raise RuntimeError("Telemetry backend is not connected")
        if isinstance(self.backend, CppTelemetryBackend):
            return self._with_python_mavlink_backend(lambda backend: backend.upload_fence(fence_zones))
        self.backend.upload_fence(fence_zones)

    def download_fence(self):
        if self.backend is None:
            raise RuntimeError("Telemetry backend is not connected")
        if isinstance(self.backend, CppTelemetryBackend):
            return self._with_python_mavlink_backend(lambda backend: backend.download_fence())
        return self.backend.download_fence()

    @staticmethod
    def _upload_plan_with_backend(backend, mission_items, fence_zones=None):
        backend.upload_mission(mission_items)
        if fence_zones is not None:
            backend.upload_fence(fence_zones)

    def download_mission(self):
        if self.backend is None:
            raise RuntimeError("Telemetry backend is not connected")
        if isinstance(self.backend, CppTelemetryBackend):
            return self._with_python_mavlink_backend(lambda backend: backend.download_mission())
        return self.backend.download_mission()

    def download_parameters(self):
        if self.backend is None:
            raise RuntimeError("Telemetry backend is not connected")
        if isinstance(self.backend, CppTelemetryBackend):
            return self._with_python_mavlink_backend(lambda backend: backend.download_parameters())
        return self.backend.download_parameters()

    def write_parameters(self, updates):
        if self.backend is None:
            raise RuntimeError("Telemetry backend is not connected")
        updates = list(updates or [])
        if isinstance(self.backend, CppTelemetryBackend):
            return self._with_python_mavlink_backend(lambda backend: backend.write_parameters(updates))
        return self.backend.write_parameters(updates)

    def _with_python_mavlink_backend(self, operation):
        original_config = dict(self.config)
        original_backend = self.backend

        if self.log_callback:
            self.log_callback("INFO", "Temporarily switching to pymavlink for MAVLink transfer")

        try:
            if original_backend is not None:
                original_backend.stop()

            backend = MavlinkTelemetryBackend(
                connection_type=original_config.get("type", "Serial"),
                target=original_config.get("target", ""),
                baud=self._parse_baud(original_config.get("baud")),
                log_callback=self.log_callback,
            )
            backend.start()
            try:
                return operation(backend)
            finally:
                backend.stop()
        finally:
            self.backend = self._create_backend(original_config)
            self.backend.start()
            if self.log_callback:
                self.log_callback("SUCCESS", "Telemetry bridge restored after MAVLink transfer")

    def _create_backend(self, config: dict) -> TelemetryBackend:
        conn_type = (config.get("type") or "Demo").strip()
        target = (config.get("target") or "").strip()
        baud = self._parse_baud(config.get("baud"))

        if conn_type.lower() in ("demo", "simulation", "sim"):
            return SimulationTelemetryBackend(log_callback=self.log_callback)

        # The current native bridge supports bidirectional commands only on
        # serial links. Use pymavlink for UDP/TCP so flight-mode and Guided
        # commands are sent back to the actual peer instead of becoming
        # telemetry-only no-ops.
        if self._use_cpp_backend() and conn_type.upper() == "SERIAL":
            try:
                return CppTelemetryBackend(
                    connection_type=conn_type,
                    target=target,
                    baud=baud,
                    log_callback=self.log_callback,
                )
            except RuntimeError as exc:
                if self.log_callback:
                    self.log_callback("WARNING", f"C++ telemetry unavailable, using Python backend: {exc}")

        return self._create_python_backend(config)

    def _create_python_backend(self, config: dict) -> TelemetryBackend:
        conn_type = (config.get("type") or "Demo").strip()
        target = (config.get("target") or "").strip()
        baud = self._parse_baud(config.get("baud"))
        return MavlinkTelemetryBackend(
            connection_type=conn_type,
            target=target,
            baud=baud,
            log_callback=self.log_callback,
        )

    @staticmethod
    def _parse_baud(value) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _use_cpp_backend() -> bool:
        try:
            import config
            return bool(getattr(config, "USE_CPP_TELEMETRY_BACKEND", False))
        except Exception:
            return False
