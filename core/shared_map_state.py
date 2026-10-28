import json
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal

from models.defense_zone import DefenseZone


class SharedMapState(QObject):
    overlay_changed = pyqtSignal()
    view_changed = pyqtSignal(float, float, float)  # center_lat, center_lon, zoom

    def __init__(self, parent=None):
        super().__init__(parent)

        # Uçak / QR verileri
        self.aircraft_lat = None
        self.aircraft_lon = None
        self.aircraft_heading = 0.0

        self.qr_lat = None
        self.qr_lon = None

        # Çoklu overlay marker listesi
        self.overlay_markers = []

        # Ortak kamera / görünüm
        self.center_lat = None
        self.center_lon = None
        self.zoom = None

        # Savunma alanları
        self.defense_zones = []
        self.load_defense_zones()

    def _safe_float(self, value, default=0.0):
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def set_aircraft(self, lat, lon, heading=None):
        self.aircraft_lat = self._safe_float(lat, None)
        self.aircraft_lon = self._safe_float(lon, None)

        if heading is not None:
            self.aircraft_heading = self._safe_float(heading, 0.0) % 360

        # overlay_markers içinde aircraft varsa onu da güncelle
        updated = False

        for marker in self.overlay_markers:
            if marker.get("type") == "aircraft":
                marker["lat"] = self.aircraft_lat
                marker["lon"] = self.aircraft_lon
                marker["heading"] = self.aircraft_heading
                updated = True
                break

        if not updated:
            self.overlay_markers.append({
                "type": "aircraft",
                "lat": self.aircraft_lat,
                "lon": self.aircraft_lon,
                "heading": self.aircraft_heading,
                "label": "UAV"
            })

        self.overlay_changed.emit()

    def set_qr(self, lat, lon):
        self.qr_lat = self._safe_float(lat, None)
        self.qr_lon = self._safe_float(lon, None)
        self.overlay_changed.emit()

    def set_view(self, center_lat, center_lon, zoom):
        self.center_lat = self._safe_float(center_lat, 0.0)
        self.center_lon = self._safe_float(center_lon, 0.0)
        self.zoom = self._safe_float(zoom, 13.0)

        self.view_changed.emit(self.center_lat, self.center_lon, self.zoom)

    def set_overlay_markers(self, markers):
        self.overlay_markers = list(markers) if markers else []

        qr_marker = next(
            (m for m in self.overlay_markers if m.get("type") == "qr"),
            None
        )

        aircraft_marker = next(
            (m for m in self.overlay_markers if m.get("type") == "aircraft"),
            None
        )

        enemy_marker = next(
            (m for m in self.overlay_markers if m.get("type") == "enemy"),
            None
        )

        if qr_marker:
            self.qr_lat = self._safe_float(qr_marker.get("lat"), None)
            self.qr_lon = self._safe_float(qr_marker.get("lon"), None)

        # Öncelik gerçek aircraft marker’da
        if aircraft_marker:
            self.aircraft_lat = self._safe_float(aircraft_marker.get("lat"), None)
            self.aircraft_lon = self._safe_float(aircraft_marker.get("lon"), None)
            self.aircraft_heading = self._safe_float(
                aircraft_marker.get("heading", 0.0),
                0.0
            ) % 360

        # Aircraft yoksa enemy'yi aircraft gibi kabul etme.
        # Çünkü bu pusula/uçak yönünü bozuyordu.
        elif enemy_marker:
            pass

        self.overlay_changed.emit()

    def get_overlay_markers(self):
        return list(self.overlay_markers)

    def add_defense_zone(self, zone):
        self.defense_zones.append(zone)
        self.save_defense_zones()
        self.overlay_changed.emit()

    def update_defense_zone(self, index: int, **updates):
        if index < 0 or index >= len(self.defense_zones):
            return False

        zone = self.defense_zones[index]
        for key, value in updates.items():
            if hasattr(zone, key):
                setattr(zone, key, value)
        self.save_defense_zones()
        self.overlay_changed.emit()
        return True

    def remove_defense_zone(self, index: int):
        if index < 0 or index >= len(self.defense_zones):
            return False

        self.defense_zones.pop(index)
        self.save_defense_zones()
        self.overlay_changed.emit()
        return True

    def remove_last_defense_zone(self):
        if not self.defense_zones:
            return

        self.defense_zones.pop()
        self.save_defense_zones()
        self.overlay_changed.emit()

    def clear_defense_zones(self):
        self.defense_zones.clear()
        self.save_defense_zones()
        self.overlay_changed.emit()

    def load_defense_zones(self):
        path = self._defense_zones_path()
        if path is None or not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        zones = []
        for item in raw if isinstance(raw, list) else []:
            zone = self._zone_from_dict(item)
            if zone is not None:
                zones.append(zone)
        self.defense_zones = zones

    def save_defense_zones(self):
        path = self._defense_zones_path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = [self._zone_to_dict(zone) for zone in self.defense_zones]
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            return

    @staticmethod
    def _defense_zones_path():
        try:
            import config
            return Path(getattr(config, "DEFENSE_ZONES_PATH"))
        except Exception:
            return None

    @staticmethod
    def _zone_to_dict(zone):
        return {
            "center_lat": float(getattr(zone, "center_lat", 0.0)),
            "center_lon": float(getattr(zone, "center_lon", 0.0)),
            "radius_m": float(getattr(zone, "radius_m", 0.0)),
            "name": str(getattr(zone, "name", "Defense Zone")),
            "is_active": bool(getattr(zone, "is_active", True)),
            "frame": str(getattr(zone, "frame", "Absolute")),
            "color": list(getattr(zone, "color", (255, 0, 0, 90))),
        }

    @staticmethod
    def _zone_from_dict(data):
        if not isinstance(data, dict):
            return None
        try:
            return DefenseZone(
                center_lat=float(data.get("center_lat")),
                center_lon=float(data.get("center_lon")),
                radius_m=float(data.get("radius_m", 500)),
                name=str(data.get("name", "Defense Zone")),
                is_active=bool(data.get("is_active", True)),
                frame=str(data.get("frame", "Absolute")),
                color=tuple(data.get("color", (255, 0, 0, 90))),
            )
        except Exception:
            return None
