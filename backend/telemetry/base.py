from abc import ABC, abstractmethod
from typing import Callable, Optional

from models.telemetry import TelemetryData

TelemetryLogCallback = Callable[[str, str], None]


class TelemetryBackend(ABC):
    def __init__(self, log_callback: Optional[TelemetryLogCallback] = None):
        self.log_callback = log_callback
        self.connected = False

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def read(self, timeout: float = 0.2) -> Optional[TelemetryData]:
        pass

    def set_mode(self, mode_name: str):
        raise NotImplementedError("Mode change is not supported by this backend")

    def goto_guided(self, latitude: float, longitude: float, altitude: float):
        raise NotImplementedError("Guided target is not supported by this backend")

    def upload_mission(self, mission_items):
        raise NotImplementedError("Mission upload is not supported by this backend")

    def download_mission(self):
        raise NotImplementedError("Mission download is not supported by this backend")

    def upload_fence(self, fence_zones):
        raise NotImplementedError("Fence upload is not supported by this backend")

    def download_fence(self):
        raise NotImplementedError("Fence download is not supported by this backend")

    def download_parameters(self):
        raise NotImplementedError("Parameter download is not supported by this backend")

    def write_parameters(self, updates):
        raise NotImplementedError("Parameter write is not supported by this backend")

    def log(self, level: str, message: str):
        if self.log_callback:
            self.log_callback(level, message)
