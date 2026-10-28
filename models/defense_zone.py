from dataclasses import dataclass

@dataclass
class DefenseZone:
    center_lat: float
    center_lon: float
    radius_m: float
    name: str = "Defense Zone"
    is_active: bool = True
    frame: str = "Absolute"
    color: tuple = (255, 0, 0, 90)  # RGBA
