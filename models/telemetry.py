from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class TelemetryData:
    timestamp: float = 0.0
    connected: bool = False
    mode: Optional[str] = None
    armed: Optional[bool] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    relative_altitude: Optional[float] = None
    absolute_altitude: Optional[float] = None

    ground_speed: Optional[float] = None
    air_speed: Optional[float] = None
    vertical_speed: Optional[float] = None

    pitch: Optional[float] = None
    roll: Optional[float] = None
    yaw: Optional[float] = None
    heading: Optional[float] = None

    battery_voltage: Optional[float] = None
    battery_current: Optional[float] = None
    battery_remaining: Optional[float] = None

    gps_fix_type: Optional[int] = None
    satellites_visible: Optional[int] = None
    signal_quality: Optional[float] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    @property
    def altitude(self) -> float:
        return self._value(self.relative_altitude, self.absolute_altitude)

    @property
    def speed(self) -> float:
        return self._value(self.ground_speed, self.air_speed)

    @property
    def safe_ground_speed(self) -> float:
        return self._value(self.ground_speed)

    @property
    def safe_air_speed(self) -> float:
        return self._value(self.air_speed)

    @property
    def battery(self) -> float:
        return self._value(self.battery_remaining, 0.0)

    @property
    def safe_pitch(self) -> float:
        return self._value(self.pitch)

    @property
    def safe_roll(self) -> float:
        return self._value(self.roll)

    @property
    def safe_yaw(self) -> float:
        return self._value(self.heading, self.yaw)

    @staticmethod
    def _value(*values) -> float:
        for value in values:
            if value is not None:
                return float(value)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "connected": self.connected,
            "mode": self.mode,
            "armed": self.armed,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "relative_altitude": self.relative_altitude,
            "absolute_altitude": self.absolute_altitude,
            "ground_speed": self.ground_speed,
            "air_speed": self.air_speed,
            "vertical_speed": self.vertical_speed,
            "pitch": self.pitch,
            "roll": self.roll,
            "yaw": self.yaw,
            "heading": self.heading,
            "battery_voltage": self.battery_voltage,
            "battery_current": self.battery_current,
            "battery_remaining": self.battery_remaining,
            "gps_fix_type": self.gps_fix_type,
            "satellites_visible": self.satellites_visible,
            "signal_quality": self.signal_quality,
            "altitude": self.altitude,
            "speed": self.speed,
            "battery": self.battery,
        }
