import math
import random
import time
from typing import Optional

from backend.telemetry.base import TelemetryBackend, TelemetryLogCallback
from models.telemetry import TelemetryData


class SimulationTelemetryBackend(TelemetryBackend):
    def __init__(self, log_callback: Optional[TelemetryLogCallback] = None):
        super().__init__(log_callback)
        self._last_emit = 0.0
        self._started_at = 0.0
        self._lat = 38.32185
        self._lon = 38.43050
        self._battery = 100.0
        self._altitude = 55.0
        self._mode = "SIM"
        self._guided_target = None
        self._mission_items = []
        self._fence_zones = []
        self._parameters = {}

    def start(self):
        self.connected = True
        self._started_at = time.time()
        self._last_emit = 0.0
        self.log("INFO", "Simulation telemetry backend started")

    def stop(self):
        self.connected = False
        self.log("INFO", "Simulation telemetry backend stopped")

    def read(self, timeout: float = 0.2) -> Optional[TelemetryData]:
        if not self.connected:
            return None

        now = time.time()
        elapsed = now - self._started_at
        wait_for = max(0.0, 0.05 - (now - self._last_emit))
        if wait_for:
            time.sleep(min(wait_for, timeout))

        self._last_emit = time.time()
        heading = (elapsed * 12.0) % 360.0
        speed = 12.0 + math.sin(elapsed * 0.8) * 2.0
        if self._guided_target is not None:
            target_lat, target_lon, target_alt = self._guided_target
            dlat = target_lat - self._lat
            dlon = target_lon - self._lon
            distance_deg = math.hypot(dlat, dlon)
            if distance_deg > 1e-8:
                step = min(0.000020, distance_deg)
                self._lat += dlat / distance_deg * step
                self._lon += dlon / distance_deg * step
                heading = (math.degrees(math.atan2(dlon, dlat)) + 360.0) % 360.0
            altitude_delta = target_alt - self._altitude
            self._altitude += max(-0.15, min(0.15, altitude_delta))
        else:
            self._altitude = 55.0 + math.sin(elapsed * 0.25) * 18.0
            self._lat += math.cos(math.radians(heading)) * 0.000015
            self._lon += math.sin(math.radians(heading)) * 0.000015
        self._battery = max(0.0, self._battery - 0.003)

        return TelemetryData(
            timestamp=time.time(),
            connected=True,
            mode=self._mode,
            armed=True,
            latitude=self._lat,
            longitude=self._lon,
            relative_altitude=self._altitude,
            absolute_altitude=self._altitude + 850.0,
            ground_speed=speed,
            air_speed=speed + random.uniform(-0.4, 0.4),
            vertical_speed=math.cos(elapsed * 0.25) * 0.8,
            pitch=math.sin(elapsed * 1.3) * 6.0,
            roll=math.sin(elapsed * 0.9) * 18.0,
            yaw=heading,
            heading=heading,
            battery_voltage=15.2 * self._battery / 100.0,
            battery_current=8.0 + random.uniform(-1.0, 1.0),
            battery_remaining=self._battery,
            gps_fix_type=3,
            satellites_visible=14,
            signal_quality=100.0,
        )

    def set_mode(self, mode_name: str):
        self._mode = str(mode_name or "SIM").upper()
        self.log("SUCCESS", f"Simulation mode changed to {self._mode}")
        return {"mode": self._mode, "mode_id": None, "already_active": False}

    def goto_guided(self, latitude: float, longitude: float, altitude: float):
        latitude = float(latitude)
        longitude = float(longitude)
        altitude = float(altitude)
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0 and altitude > 0.0):
            raise ValueError("Invalid Guided target")
        self._mode = "GUIDED"
        self._guided_target = (latitude, longitude, altitude)
        self.log("SUCCESS", f"Simulation Guided target: {latitude:.7f}, {longitude:.7f}, {altitude:.1f} m")
        return {"latitude": latitude, "longitude": longitude, "altitude": altitude, "mode": "GUIDED"}

    def upload_mission(self, mission_items):
        self._mission_items = list(mission_items or [])
        count = len(self._mission_items)
        self.log("SUCCESS", f"Simulation mission upload accepted: {count} items")

    def download_mission(self):
        self.log("SUCCESS", f"Simulation mission download: {len(self._mission_items)} items")
        return list(self._mission_items)

    def upload_fence(self, fence_zones):
        self._fence_zones = list(fence_zones or [])
        self.log("SUCCESS", f"Simulation fence upload accepted: {len(self._fence_zones)} zones")

    def download_fence(self):
        self.log("SUCCESS", f"Simulation fence download: {len(self._fence_zones)} zones")
        return list(self._fence_zones)

    def write_parameters(self, updates):
        written = []
        for update in list(updates or []):
            name = str(update.get("name", "")).strip()
            if not name:
                continue
            value = float(update.get("value"))
            self._parameters[name] = value
            written.append({"name": name, "value": value, "type": int(update.get("type", 9) or 9)})
        self.log("SUCCESS", f"Simulation parameter write: {len(written)} items")
        return {"written": written, "failed": []}
