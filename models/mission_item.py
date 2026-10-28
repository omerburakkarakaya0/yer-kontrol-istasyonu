"""
Mission Item Model
Rota planlama için mission item'larını tutan sınıf
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


class MissionItemType(Enum):
    """
    Mission item tipleri.
    Enum kullanarak tip güvenliği sağlıyoruz.
    """
    TAKEOFF = "Takeoff"
    WAYPOINT = "Waypoint"
    DO_JUMP = "Do Jump"
    RTL = "Return to Launch"
    DO_LAND_START = "Do Land Start"
    LAND = "Land"
    
    def __str__(self):
        return self.value


@dataclass
class MissionItem:
    """
    Bir mission item'ı temsil eder.
    
    Her mission item'ın:
    - Tipi (Takeoff, Waypoint, vb.)
    - Sırası (sequence number)
    - Parametreleri (hız, yükseklik, vb.)
    - Konumu (lat/lon) - eğer waypoint ise
    """
    item_type: MissionItemType
    sequence: int = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None  # Metre
    speed: Optional[float] = None     # m/s
    parameters: Dict[str, Any] = field(default_factory=dict)  # Ek parametreler
    
    def __post_init__(self):
        """Varsayılan değerleri ayarla"""
        if self.altitude is None:
            self.altitude = 50.0  # Varsayılan 50 metre
        if self.speed is None:
            self.speed = 10.0     # Varsayılan 10 m/s
    
    def to_dict(self) -> dict:
        """Dictionary formatına çevir (serialization için)"""
        return {
            'type': self.item_type.value,
            'sequence': self.sequence,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'speed': self.speed,
            'parameters': self.parameters
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MissionItem':
        """Dictionary'den MissionItem oluştur"""
        item_type = MissionItemType(data['type'])
        return cls(
            item_type=item_type,
            sequence=data.get('sequence', 0),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            altitude=data.get('altitude'),
            speed=data.get('speed'),
            parameters=data.get('parameters', {})
        )
