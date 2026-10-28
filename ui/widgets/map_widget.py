"""
Map Widget
MBTiles tabanlı offline harita gösterimi, rota çizimi ve waypoint yönetimi.

ÖZELLİKLER:
- Offline MBTiles render
- Smooth zoom (wheel)
- Sürükleyerek pan
- Waypoint ve rota çizimi
- Izgara (grid) overlay
- Nokta seçimi
- SharedMapState ile senkron görünüm
- QR ve uçak/enemy overlay çizimi
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QPoint, QPointF, QRect, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QTransform, QBrush, QPolygonF
from PyQt5.QtWidgets import QWidget

import config
from models.mission_item import MissionItem

TILE_SIZE = 256
EARTH_MAX_LAT = 85.05112878


@dataclass
class VisibleMarker:
    sequence: int
    x: float
    y: float
    item: MissionItem


class MBTilesSource:
    """Basit MBTiles okuyucu."""

    def __init__(self, mbtiles_path: Path):
        self.mbtiles_path = Path(mbtiles_path)
        self.connection: Optional[sqlite3.Connection] = None
        self.min_zoom = 0
        self.max_zoom = 18
        self.bounds: Optional[Tuple[float, float, float, float]] = None
        self.center: Optional[Tuple[float, float, int]] = None
        self.format = "png"
        self._tile_cache: Dict[Tuple[int, int, int], QPixmap] = {}

    @property
    def available(self) -> bool:
        return self.mbtiles_path.exists()

    def open(self):
        if not self.available:
            return
        if self.connection is None:
            self.connection = sqlite3.connect(str(self.mbtiles_path))
            self.connection.row_factory = sqlite3.Row
            self._load_metadata()

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            self._tile_cache.clear()

    def _load_metadata(self):
        cur = self.connection.cursor()
        metadata = {}

        try:
            cur.execute("SELECT name, value FROM metadata")
            metadata = {row["name"]: row["value"] for row in cur.fetchall()}
        except sqlite3.Error:
            metadata = {}

        try:
            cur.execute("SELECT MIN(zoom_level) AS min_z, MAX(zoom_level) AS max_z FROM tiles")
            row = cur.fetchone()
            if row and row["min_z"] is not None:
                self.min_zoom = int(row["min_z"])
                self.max_zoom = int(row["max_z"])
        except sqlite3.Error:
            pass

        bounds = metadata.get("bounds")
        if bounds:
            try:
                min_lon, min_lat, max_lon, max_lat = map(float, bounds.split(","))
                self.bounds = (min_lat, min_lon, max_lat, max_lon)
            except Exception:
                self.bounds = None

        center = metadata.get("center")
        if center:
            try:
                lon, lat, zoom = center.split(",")
                self.center = (float(lat), float(lon), int(float(zoom)))
            except Exception:
                self.center = None

        fmt = metadata.get("format")
        if fmt:
            self.format = fmt

    def get_tile(self, z: int, x: int, y_xyz: int) -> Optional[QPixmap]:
        self.open()
        if self.connection is None:
            return None

        n = 1 << z
        if n <= 0:
            return None

        x %= n
        if y_xyz < 0 or y_xyz >= n:
            return None

        key = (z, x, y_xyz)
        if key in self._tile_cache:
            return self._tile_cache[key]

        y_tms = (n - 1) - y_xyz
        cur = self.connection.cursor()

        try:
            cur.execute(
                "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                (z, x, y_tms),
            )
            row = cur.fetchone()
        except sqlite3.Error:
            row = None

        if not row:
            return None

        data = row[0]
        image = QImage()
        image.loadFromData(data)
        if image.isNull():
            return None

        pixmap = QPixmap.fromImage(image)
        self._tile_cache[key] = pixmap

        if len(self._tile_cache) > 600:
            self._tile_cache.pop(next(iter(self._tile_cache)))

        return pixmap


class MapWidget(QWidget):
    waypoint_clicked = pyqtSignal(int)
    coordinate_double_clicked = pyqtSignal(float, float)
    coordinate_clicked = pyqtSignal(float, float)
    status_message = pyqtSignal(str)

    def __init__(self, parent=None, shared_map_state=None):
        super().__init__(parent)
        self.setMinimumSize(700, 450)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.shared_map_state = shared_map_state
        self._applying_shared_view = False

        base_dir = Path(__file__).resolve().parents[2]
        self.mbtiles_path = Path(
            getattr(config, "MAP_MBTILES_PATH", base_dir / "assets" / "maps" / "mission_map.mbtiles")
        )
        self.map_source = MBTilesSource(self.mbtiles_path)

        self.map_items: List[MissionItem] = []
        self.analysis_route: List[Tuple[float, float]] = []
        self.analysis_route_label = ""
        self.analysis_routes = []
        self.current_position: Optional[Tuple[float, float]] = None
        self.visible_markers: List[VisibleMarker] = []
        self.guided_target = None

        self.overlay_markers = []
        self.defense_zones = []
        
        # Sabit uçuş sahası (dikdörtgen)
        self.flight_area_enabled = True
        self.flight_area_bounds = {
            "min_lat": 38.30830,
            "max_lat": 38.33600,
            "min_lon": 38.40000,
            "max_lon": 38.45200,
        }

        self.qr_pixmap = QPixmap(str(base_dir / "assets" / "images" / "qr_target.png"))
        self.enemy_pixmap = QPixmap(str(base_dir / "assets" / "images" / "enemy_plane.png"))

        self.center_lat = 39.9000
        self.center_lon = 32.8000
        self.zoom = 14.0
        self.min_zoom = 2.0
        self.max_zoom = 19.0

        self._dragging = False
        self._drag_start = QPoint()
        self._click_candidate = False
        self._last_mouse_pos = QPoint(self.width() // 2, self.height() // 2)
        self._grid_enabled = True
        self._route_enabled = True

        self.setStyleSheet("background-color: #161616; border: 1px solid #333;")
        self._initialize_from_mbtiles()
        self._connect_shared_state()
        self._pull_initial_shared_state()

    # =========================================================
    # DEFENSE ZONES
    # =========================================================
    def _get_defense_zones(self):
        if self.shared_map_state is not None and hasattr(self.shared_map_state, "defense_zones"):
            return self.shared_map_state.defense_zones
        return self.defense_zones

    def add_defense_zone(self, zone):
        if self.shared_map_state is not None and hasattr(self.shared_map_state, "add_defense_zone"):
            self.shared_map_state.add_defense_zone(zone)
            self.defense_zones = list(self.shared_map_state.defense_zones)
        else:
            self.defense_zones.append(zone)

        self.update()

    def clear_defense_zones(self):
        if self.shared_map_state is not None and hasattr(self.shared_map_state, "clear_defense_zones"):
            self.shared_map_state.clear_defense_zones()
            self.defense_zones = list(self.shared_map_state.defense_zones)
        else:
            self.defense_zones.clear()

        self.update()

    def remove_last_defense_zone(self):
        if self.shared_map_state is not None and hasattr(self.shared_map_state, "remove_last_defense_zone"):
            self.shared_map_state.remove_last_defense_zone()
            self.defense_zones = list(self.shared_map_state.defense_zones)
        else:
            if not self.defense_zones:
                return
            self.defense_zones.pop()

        self.update()

    def meters_per_pixel(self, lat=None, zoom=None):
        if lat is None:
            lat = self.center_lat
        if zoom is None:
            zoom = self.zoom
        return 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)

    def draw_defense_zones(self, painter):
        zones = self._get_defense_zones()
        if not zones:
            return
    
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
    
        for zone in zones:
            if not getattr(zone, "is_active", True):
                continue
            
            point = self._latlon_to_screen(zone.center_lat, zone.center_lon)
            x = point.x()
            y = point.y()
    
            mpp = self.meters_per_pixel(zone.center_lat, self.zoom)
            if mpp <= 0:
                continue
            
            radius_px = zone.radius_m / mpp
    
            r, g, b, a = zone.color
    
            painter.setBrush(QBrush(QColor(255, 80, 40, max(45, a))))
            painter.setPen(QPen(QColor(255, 70, 35), 2, Qt.DashLine))
            painter.drawEllipse(QPointF(x, y), radius_px, radius_px)
    
            painter.setPen(QPen(QColor(255, 70, 35), 1))
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            painter.drawEllipse(QPointF(x, y), 4, 4)
    
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawText(int(x + 8), int(y - 8), f"{zone.name} ({int(zone.radius_m)} m)")
    
        painter.restore()
    
    def draw_flight_area(self, painter):
        if not getattr(self, "flight_area_enabled", False):
            return

        bounds = getattr(self, "flight_area_bounds", None)
        if not bounds:
            return

        min_lat = bounds["min_lat"]
        max_lat = bounds["max_lat"]
        min_lon = bounds["min_lon"]
        max_lon = bounds["max_lon"]

        # Dikdörtgenin köşeleri
        top_left = self._latlon_to_screen(max_lat, min_lon)
        top_right = self._latlon_to_screen(max_lat, max_lon)
        bottom_left = self._latlon_to_screen(min_lat, min_lon)
        bottom_right = self._latlon_to_screen(min_lat, max_lon)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # İç dolgu
        polygon = [
            QPointF(top_left.x(), top_left.y()),
            QPointF(top_right.x(), top_right.y()),
            QPointF(bottom_right.x(), bottom_right.y()),
            QPointF(bottom_left.x(), bottom_left.y()),
        ]

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 0, 0), 3))

        # Kenarlar
        painter.drawLine(top_left, top_right)
        painter.drawLine(top_right, bottom_right)
        painter.drawLine(bottom_right, bottom_left)
        painter.drawLine(bottom_left, top_left)

        # İstersen köşe noktaları
        painter.setBrush(QBrush(QColor(255, 0, 0)))
        for p in [top_left, top_right, bottom_right, bottom_left]:
            painter.drawEllipse(p, 4, 4)

        # Yazı
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawText(int(top_left.x() + 8), int(top_left.y() - 8), "Ucus Sahasi")

        painter.restore()

    def haversine_distance_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    def is_inside_defense_zone(self, aircraft_lat: float, aircraft_lon: float, zone) -> bool:
        distance = self.haversine_distance_m(
            aircraft_lat,
            aircraft_lon,
            zone.center_lat,
            zone.center_lon
        )
        return distance <= zone.radius_m

    def check_defense_zone_breach(self):
        zones = self._get_defense_zones()
        if not zones:
            return

        aircraft_lat = None
        aircraft_lon = None

        if self.shared_map_state is not None:
            aircraft_lat = getattr(self.shared_map_state, "aircraft_lat", None)
            aircraft_lon = getattr(self.shared_map_state, "aircraft_lon", None)

        if aircraft_lat is None or aircraft_lon is None:
            if self.current_position is not None:
                aircraft_lat, aircraft_lon = self.current_position
            else:
                return

        for zone in zones:
            if not getattr(zone, "is_active", True):
                continue

            if self.is_inside_defense_zone(aircraft_lat, aircraft_lon, zone):
                print(f"UYARI: {zone.name} içine girdin!")

    # =========================================================
    # SHARED STATE
    # =========================================================
    def _connect_shared_state(self):
        if self.shared_map_state is None:
            return

        if hasattr(self.shared_map_state, "overlay_changed"):
            self.shared_map_state.overlay_changed.connect(self._sync_from_shared_state)

        if hasattr(self.shared_map_state, "view_changed"):
            self.shared_map_state.view_changed.connect(self._apply_shared_view)
            
    def _sync_from_shared_state(self):
        """
        SharedMapState içindeki overlay verilerini local widget state'ine kopyalar.
        Böylece Flight ve Mission haritaları aynı veriyi kesin olarak çizer.
        """
        if self.shared_map_state is None:
            self.update()
            return

        # Savunma alanlarını local'e kopyala
        if hasattr(self.shared_map_state, "defense_zones"):
            self.defense_zones = list(self.shared_map_state.defense_zones)
        else:
            self.defense_zones = []

        # Overlay markerları local'e kopyala
        if hasattr(self.shared_map_state, "get_overlay_markers"):
            try:
                self.overlay_markers = list(self.shared_map_state.get_overlay_markers())
            except Exception:
                self.overlay_markers = []
        else:
            self.overlay_markers = []

        self.update()

    def _pull_initial_shared_state(self):
        """
        Açılışta önce shared state gerçekten dolu mu kontrol et.
        Dolu değilse MBTiles / mevcut harita merkezi korunur ve shared state'e yazılır.
        """
        if self.shared_map_state is None:
            return

        state_lat = getattr(self.shared_map_state, "center_lat", None)
        state_lon = getattr(self.shared_map_state, "center_lon", None)
        state_zoom = getattr(self.shared_map_state, "zoom", None)

        if state_lat is None or state_lon is None or state_zoom is None:
            if hasattr(self.shared_map_state, "set_view"):
                self.shared_map_state.set_view(self.center_lat, self.center_lon, self.zoom)
            return

        try:
            self.center_lat = float(state_lat)
            self.center_lon = float(state_lon)
            self.zoom = max(self.min_zoom, min(self.max_zoom, float(state_zoom)))
        except Exception:
            if hasattr(self.shared_map_state, "set_view"):
                self.shared_map_state.set_view(self.center_lat, self.center_lon, self.zoom)

        self._sync_from_shared_state()

    def _apply_shared_view(self, center_lat, center_lon, zoom):
        if self._applying_shared_view:
            return

        self._applying_shared_view = True
        self.center_lat = float(center_lat)
        self.center_lon = float(center_lon)
        self.zoom = max(self.min_zoom, min(self.max_zoom, float(zoom)))
        self.update()
        self._applying_shared_view = False

    def _publish_shared_view(self):
        if self.shared_map_state is None:
            return
        if self._applying_shared_view:
            return
        if not hasattr(self.shared_map_state, "set_view"):
            return

        self.shared_map_state.set_view(self.center_lat, self.center_lon, self.zoom)

    # =========================================================
    # MAP SETUP
    # =========================================================
    def _initialize_from_mbtiles(self):
        if not self.map_source.available:
            self.status_message.emit("MBTiles dosyası bulunamadı. assets/maps/mission_map.mbtiles ekleyin.")
            return

        self.map_source.open()
        self.min_zoom = float(self.map_source.min_zoom)
        self.max_zoom = min(20.0, float(self.map_source.max_zoom) + 1.0)

        if self.map_source.center:
            lat, lon, z = self.map_source.center
            self.center_lat = lat
            self.center_lon = lon
            self.zoom = float(max(self.min_zoom, min(self.max_zoom, z)))
        elif self.map_source.bounds:
            min_lat, min_lon, max_lat, max_lon = self.map_source.bounds
            self.center_lat = (min_lat + max_lat) / 2.0
            self.center_lon = (min_lon + max_lon) / 2.0
            self.zoom = max(self.min_zoom, min(self.max_zoom, self._estimate_fit_zoom(self.map_source.bounds)))

    def toggle_grid(self, enabled: bool):
        self._grid_enabled = enabled
        self.update()

    def toggle_route(self, enabled: bool):
        self._route_enabled = enabled
        self.update()

    def update_waypoints(self, items: List[MissionItem]):
        self.map_items = list(items)
        self.update()

    def fit_to_waypoints(self):
        coords = [
            (item.latitude, item.longitude)
            for item in self.map_items
            if item.latitude is not None and item.longitude is not None
        ]
        if not coords:
            return

        min_lat = min(lat for lat, _ in coords)
        max_lat = max(lat for lat, _ in coords)
        min_lon = min(lon for _, lon in coords)
        max_lon = max(lon for _, lon in coords)

        if len(coords) == 1:
            self.center_lat, self.center_lon = coords[0]
            self.zoom = max(self.min_zoom, min(self.max_zoom, 17.0))
        else:
            lat_pad = max((max_lat - min_lat) * 0.25, 0.0005)
            lon_pad = max((max_lon - min_lon) * 0.25, 0.0005)
            bounds = (
                min_lat - lat_pad,
                min_lon - lon_pad,
                max_lat + lat_pad,
                max_lon + lon_pad,
            )
            self.center_lat = (bounds[0] + bounds[2]) / 2.0
            self.center_lon = (bounds[1] + bounds[3]) / 2.0
            self.zoom = max(self.min_zoom, min(self.max_zoom, self._estimate_fit_zoom(bounds)))

        self._publish_shared_view()
        self.update()

    def set_analysis_route(self, route: List[Tuple[float, float]], label: str = "Log route"):
        self.analysis_route = [
            (float(lat), float(lon))
            for lat, lon in list(route or [])
            if lat is not None and lon is not None
        ]
        self.analysis_route_label = label
        self.analysis_routes = []
        self.fit_to_analysis_route()

    def set_analysis_routes(self, routes):
        self.analysis_route = []
        self.analysis_route_label = ""
        normalized = []

        for index, route_info in enumerate(list(routes or [])):
            if isinstance(route_info, dict):
                raw_route = route_info.get("route") or route_info.get("points") or []
                label = str(route_info.get("label") or route_info.get("id") or f"Route {index + 1}")
                color = route_info.get("color")
            else:
                raw_route = route_info
                label = f"Route {index + 1}"
                color = None

            route = [
                (float(lat), float(lon))
                for lat, lon in list(raw_route or [])
                if lat is not None and lon is not None
            ]
            if route:
                normalized.append({"route": route, "label": label, "color": color})

        self.analysis_routes = normalized
        self.fit_to_analysis_route()

    def fit_to_analysis_route(self):
        coords = list(self.analysis_route)
        for route_info in self.analysis_routes:
            coords.extend(route_info.get("route", []))
        if not coords:
            self.update()
            return

        min_lat = min(lat for lat, _ in coords)
        max_lat = max(lat for lat, _ in coords)
        min_lon = min(lon for _, lon in coords)
        max_lon = max(lon for _, lon in coords)

        if len(coords) == 1:
            self.center_lat, self.center_lon = coords[0]
            self.zoom = max(self.min_zoom, min(self.max_zoom, 17.0))
        else:
            lat_pad = max((max_lat - min_lat) * 0.18, 0.0005)
            lon_pad = max((max_lon - min_lon) * 0.18, 0.0005)
            bounds = (
                min_lat - lat_pad,
                min_lon - lon_pad,
                max_lat + lat_pad,
                max_lon + lon_pad,
            )
            self.center_lat = (bounds[0] + bounds[2]) / 2.0
            self.center_lon = (bounds[1] + bounds[3]) / 2.0
            self.zoom = max(self.min_zoom, min(self.max_zoom, self._estimate_fit_zoom(bounds)))

        self.update()

    def update_current_position(self, latitude: float, longitude: float):
        self.current_position = (latitude, longitude)
        self.update()

    def coordinate_at(self, position) -> Tuple[float, float]:
        return self._screen_to_latlon(position)

    def set_guided_target(self, latitude: float, longitude: float, altitude: float, status: str = "pending"):
        self.guided_target = {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "altitude": float(altitude),
            "status": str(status or "pending"),
        }
        self.update()

    def clear_guided_target(self):
        self.guided_target = None
        self.update()

    def set_mbtiles_path(self, mbtiles_path: str):
        self.map_source.close()
        self.mbtiles_path = Path(mbtiles_path)
        self.map_source = MBTilesSource(self.mbtiles_path)
        self._initialize_from_mbtiles()
        self._publish_shared_view()
        self.update()

    def _fit_to_items_if_needed(self):
        coords = [
            (item.latitude, item.longitude)
            for item in self.map_items
            if item.latitude is not None and item.longitude is not None
        ]
        if len(coords) < 2:
            return

        min_lat = min(lat for lat, _ in coords)
        max_lat = max(lat for lat, _ in coords)
        min_lon = min(lon for _, lon in coords)
        max_lon = max(lon for _, lon in coords)

        self.center_lat = (min_lat + max_lat) / 2.0
        self.center_lon = (min_lon + max_lon) / 2.0
        self._publish_shared_view()

    def _estimate_fit_zoom(self, bounds: Tuple[float, float, float, float]) -> float:
        min_lat, min_lon, max_lat, max_lon = bounds
        width = max(self.width(), 700)
        height = max(self.height(), 450)

        for z in range(int(self.max_zoom), int(self.min_zoom) - 1, -1):
            x1, y1 = self._latlon_to_world(min_lat, min_lon, z)
            x2, y2 = self._latlon_to_world(max_lat, max_lon, z)
            span_x = abs(x2 - x1)
            span_y = abs(y2 - y1)
            if span_x <= width * 0.85 and span_y <= height * 0.85:
                return float(z)

        return self.min_zoom

    @staticmethod
    def _clip_lat(lat: float) -> float:
        return max(-EARTH_MAX_LAT, min(EARTH_MAX_LAT, lat))

    def _latlon_to_world(self, lat: float, lon: float, zoom_int: int) -> Tuple[float, float]:
        lat = self._clip_lat(lat)
        world_size = TILE_SIZE * (2 ** zoom_int)

        x = (lon + 180.0) / 360.0 * world_size
        lat_rad = math.radians(lat)
        y = (
            1.0
            - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi
        ) / 2.0 * world_size

        return x, y

    def _world_to_latlon(self, x: float, y: float, zoom_int: int) -> Tuple[float, float]:
        world_size = TILE_SIZE * (2 ** zoom_int)
        lon = x / world_size * 360.0 - 180.0
        n = math.pi - 2.0 * math.pi * y / world_size
        lat = math.degrees(math.atan(math.sinh(n)))
        return lat, lon

    def _screen_to_latlon(self, pos: QPointF) -> Tuple[float, float]:
        zoom_int = int(math.floor(self.zoom))
        scale = 2 ** (self.zoom - zoom_int)

        center_world_x, center_world_y = self._latlon_to_world(self.center_lat, self.center_lon, zoom_int)
        world_x = center_world_x + (pos.x() - self.width() / 2.0) / scale
        world_y = center_world_y + (pos.y() - self.height() / 2.0) / scale

        return self._world_to_latlon(world_x, world_y, zoom_int)

    def _latlon_to_screen(self, lat: float, lon: float) -> QPointF:
        zoom_int = int(math.floor(self.zoom))
        scale = 2 ** (self.zoom - zoom_int)

        center_world_x, center_world_y = self._latlon_to_world(self.center_lat, self.center_lon, zoom_int)
        world_x, world_y = self._latlon_to_world(lat, lon, zoom_int)

        screen_x = (world_x - center_world_x) * scale + self.width() / 2.0
        screen_y = (world_y - center_world_y) * scale + self.height() / 2.0

        return QPointF(screen_x, screen_y)

    # =========================================================
    # INPUT EVENTS
    # =========================================================
    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle == 0:
            return

        before_lat, before_lon = self._screen_to_latlon(event.pos())
        delta = 0.25 if angle > 0 else -0.25
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom + delta))

        zoom_int = int(math.floor(self.zoom))
        scale = 2 ** (self.zoom - zoom_int)

        target_world_x, target_world_y = self._latlon_to_world(before_lat, before_lon, zoom_int)
        center_world_x = target_world_x - (event.pos().x() - self.width() / 2.0) / scale
        center_world_y = target_world_y - (event.pos().y() - self.height() / 2.0) / scale
        self.center_lat, self.center_lon = self._world_to_latlon(center_world_x, center_world_y, zoom_int)

        self._publish_shared_view()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.pos()
            self._click_candidate = True
            self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._last_mouse_pos = event.pos()

        if self._dragging:
            delta = event.pos() - self._drag_start
            if delta.manhattanLength() > 4:
                self._click_candidate = False

            zoom_int = int(math.floor(self.zoom))
            scale = 2 ** (self.zoom - zoom_int)

            center_world_x, center_world_y = self._latlon_to_world(
                self.center_lat, self.center_lon, zoom_int
            )
            center_world_x -= delta.x() / scale
            center_world_y -= delta.y() / scale
            self.center_lat, self.center_lon = self._world_to_latlon(
                center_world_x, center_world_y, zoom_int
            )

            self._drag_start = event.pos()
            self._publish_shared_view()
            self.update()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False

            if self._click_candidate:
                marker = self._find_marker_at(event.pos())
                if marker is not None:
                    self.waypoint_clicked.emit(marker.sequence)
                else:
                    lat, lon = self._screen_to_latlon(event.pos())
                    self.coordinate_clicked.emit(lat, lon)

            self._click_candidate = False

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    def _find_marker_at(self, pos: QPoint) -> Optional[VisibleMarker]:
        for marker in reversed(self.visible_markers):
            if (marker.x - pos.x()) ** 2 + (marker.y - pos.y()) ** 2 <= 12 ** 2:
                return marker
        return None

    # =========================================================
    # PAINT
    # =========================================================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#141414"))

        self._draw_tiles(painter)

        if self._grid_enabled:
            self._draw_geo_grid(painter)
            
        self.draw_flight_area(painter)
        self.draw_defense_zones(painter)
        self._draw_route(painter)
        self._draw_analysis_route(painter)
        self._draw_markers(painter)
        self._draw_current_position(painter)
        self._draw_guided_target(painter)
        self._draw_effective_overlay_markers(painter)
        self._draw_status_overlay(painter)

        painter.end()

    def _draw_tiles(self, painter: QPainter):
        if not self.map_source.available:
            return

        zoom_int = int(math.floor(self.zoom))
        scale = 2 ** (self.zoom - zoom_int)
        center_world_x, center_world_y = self._latlon_to_world(self.center_lat, self.center_lon, zoom_int)
        world_tiles = 1 << zoom_int

        left_world = center_world_x - self.width() / (2 * scale)
        right_world = center_world_x + self.width() / (2 * scale)
        top_world = center_world_y - self.height() / (2 * scale)
        bottom_world = center_world_y + self.height() / (2 * scale)

        start_tx = math.floor(left_world / TILE_SIZE)
        end_tx = math.floor(right_world / TILE_SIZE)
        start_ty = math.floor(top_world / TILE_SIZE)
        end_ty = math.floor(bottom_world / TILE_SIZE)

        for tx in range(start_tx, end_tx + 1):
            for ty in range(start_ty, end_ty + 1):
                if ty < 0 or ty >= world_tiles:
                    continue

                tile = self.map_source.get_tile(zoom_int, tx, ty)
                tile_rect = QRectF(
                    (tx * TILE_SIZE - center_world_x) * scale + self.width() / 2.0,
                    (ty * TILE_SIZE - center_world_y) * scale + self.height() / 2.0,
                    TILE_SIZE * scale,
                    TILE_SIZE * scale,
                )

                if tile is not None:
                    source_rect = QRectF(0.0, 0.0, float(tile.width()), float(tile.height()))
                    painter.drawPixmap(tile_rect, tile, source_rect)
                else:
                    painter.fillRect(tile_rect, QColor(34, 34, 34))
                    painter.setPen(QPen(QColor(50, 50, 50)))
                    painter.drawRect(tile_rect.toRect())

    def _draw_geo_grid(self, painter: QPainter):
        top_left = self._screen_to_latlon(QPointF(0, 0))
        bottom_right = self._screen_to_latlon(QPointF(self.width(), self.height()))

        max_lat = top_left[0]
        min_lat = bottom_right[0]
        min_lon = top_left[1]
        max_lon = bottom_right[1]

        lon_span = abs(max_lon - min_lon)
        lat_span = abs(max_lat - min_lat)
        step = self._choose_grid_step(max(lon_span, lat_span))

        painter.setPen(QPen(QColor(255, 255, 255, 55), 1, Qt.DotLine))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        lon = math.floor(min_lon / step) * step
        while lon <= max_lon:
            p1 = self._latlon_to_screen(max_lat, lon)
            p2 = self._latlon_to_screen(min_lat, lon)
            painter.drawLine(QPointF(p1.x(), 0), QPointF(p2.x(), self.height()))
            painter.drawText(QPointF(p1.x() + 4, 14), f"{lon:.4f}")
            lon += step

        lat = math.floor(min_lat / step) * step
        while lat <= max_lat:
            p1 = self._latlon_to_screen(lat, min_lon)
            painter.drawLine(QPointF(0, p1.y()), QPointF(self.width(), p1.y()))
            painter.drawText(QPointF(6, p1.y() - 4), f"{lat:.4f}")
            lat += step

    @staticmethod
    def _choose_grid_step(span: float) -> float:
        candidates = [
            0.0002, 0.0005, 0.001, 0.002, 0.005,
            0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
            1.0, 2.0, 5.0, 10.0,
        ]
        target = max(span / 8.0, 0.0002)

        for step in candidates:
            if step >= target:
                return step
        return candidates[-1]

    def _draw_route(self, painter: QPainter):
        routable = [
            item for item in self.map_items
            if item.latitude is not None and item.longitude is not None
        ]

        if len(routable) < 2 or not self._route_enabled:
            return

        painter.setPen(QPen(QColor(74, 169, 255), 3))
        last = None

        for item in sorted(routable, key=lambda x: x.sequence):
            current = self._latlon_to_screen(item.latitude, item.longitude)
            if last is not None:
                painter.drawLine(last, current)
            last = current

    def _draw_analysis_route(self, painter: QPainter):
        if self.analysis_routes:
            self._draw_analysis_routes(painter)
            return

        if len(self.analysis_route) < 2:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor("#ff8800"), 4))

        last = None
        for lat, lon in self.analysis_route:
            current = self._latlon_to_screen(lat, lon)
            if last is not None:
                painter.drawLine(last, current)
            last = current

        painter.setPen(QPen(QColor("#ffffff"), 1, Qt.DashLine))
        waypoint_step = max(1, len(self.analysis_route) // 18)
        waypoint_points = [self._latlon_to_screen(lat, lon) for lat, lon in self.analysis_route[::waypoint_step]]
        for index in range(1, len(waypoint_points)):
            painter.drawLine(waypoint_points[index - 1], waypoint_points[index])

        painter.setBrush(QBrush(QColor("#d32f2f")))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        for number, pos in enumerate(waypoint_points, start=1):
            painter.drawEllipse(QPointF(pos.x(), pos.y()), 4, 4)
            painter.drawText(int(pos.x() + 6), int(pos.y() - 6), str(number))

        if self.analysis_route_label:
            start = self._latlon_to_screen(*self.analysis_route[0])
            painter.setPen(QColor("#ffcc80"))
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(int(start.x() + 10), int(start.y() + 18), self.analysis_route_label)

        painter.restore()

    def _draw_analysis_routes(self, painter: QPainter):
        colors = [
            "#ff8800", "#35c7ff", "#ff4f81", "#9cff57",
            "#ffd447", "#b980ff", "#ff6b35", "#48f2b4",
        ]

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        for index, route_info in enumerate(self.analysis_routes):
            route = route_info.get("route", [])
            if len(route) < 1:
                continue

            color = route_info.get("color") or colors[index % len(colors)]
            qcolor = QColor(str(color))
            if not qcolor.isValid():
                qcolor = QColor(colors[index % len(colors)])

            painter.setPen(QPen(qcolor, 4))
            last = None
            for lat, lon in route:
                current = self._latlon_to_screen(lat, lon)
                if last is not None:
                    painter.drawLine(last, current)
                last = current

            start = self._latlon_to_screen(*route[0])
            end = self._latlon_to_screen(*route[-1])
            painter.setBrush(QBrush(qcolor))
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.drawEllipse(QPointF(start.x(), start.y()), 5, 5)
            painter.drawRect(int(end.x() - 5), int(end.y() - 5), 10, 10)

            label = route_info.get("label", "")
            if label:
                painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("Arial", 9, QFont.Bold))
                painter.drawText(int(start.x() + 10), int(start.y() - 8), str(label))

        painter.restore()

    def _draw_markers(self, painter: QPainter):
        self.visible_markers.clear()

        marker_font = QFont()
        marker_font.setPointSize(9)
        marker_font.setBold(True)
        painter.setFont(marker_font)

        for item in sorted(self.map_items, key=lambda x: x.sequence):
            if item.latitude is None or item.longitude is None:
                continue

            pos = self._latlon_to_screen(item.latitude, item.longitude)
            if pos.x() < -30 or pos.x() > self.width() + 30 or pos.y() < -30 or pos.y() > self.height() + 30:
                continue

            radius = 9
            fill = QColor(74, 169, 255)

            if item.item_type.value == "Takeoff":
                fill = QColor(76, 175, 80)
            elif item.item_type.value == "Land":
                fill = QColor(244, 67, 54)

            painter.setPen(QPen(QColor("white"), 2))
            painter.setBrush(fill)
            painter.drawEllipse(QPointF(pos.x(), pos.y()), radius, radius)

            painter.setPen(QColor("white"))
            painter.drawText(QPointF(pos.x() + 12, pos.y() - 10), f"WP{item.sequence}")

            self.visible_markers.append(
                VisibleMarker(item.sequence, pos.x(), pos.y(), item)
            )

    def _draw_guided_target(self, painter: QPainter):
        target = self.guided_target
        if not isinstance(target, dict):
            return
        pos = self._latlon_to_screen(target["latitude"], target["longitude"])
        status = target.get("status", "pending")
        color = QColor("#35e58a" if status == "accepted" else "#ffd447" if status == "pending" else "#ff4f4f")

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(pos.x(), pos.y()), 8, 8)
        painter.setPen(QPen(color, 2, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(pos.x(), pos.y()), 15, 15)
        painter.drawLine(QPointF(pos.x() - 20, pos.y()), QPointF(pos.x() + 20, pos.y()))
        painter.drawLine(QPointF(pos.x(), pos.y() - 20), QPointF(pos.x(), pos.y() + 20))
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        label = f"GUIDED HEDEF  {target['altitude']:.1f} m"
        if status == "pending":
            label += "  (gönderiliyor)"
        elif status == "rejected":
            label += "  (reddedildi)"
        painter.drawText(int(pos.x() + 18), int(pos.y() - 18), label)
        painter.restore()

    def _draw_current_position(self, painter: QPainter):
        if self.current_position is None:
            return
        if self.shared_map_state is not None and getattr(self.shared_map_state, "aircraft_lat", None) is not None:
            return

        pos = self._latlon_to_screen(*self.current_position)
        heading = 0.0
        if self.shared_map_state is not None:
            heading = float(getattr(self.shared_map_state, "aircraft_heading", 0.0) or 0.0)
        self._draw_aircraft_symbol(painter, pos.x(), pos.y(), heading, "UAV")

    def _draw_status_overlay(self, painter: QPainter):
        if self.property("hideStatusOverlay") and self.map_source.available:
            return
        panel_rect = QRectF(12, 12, 290, 90)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(15, 15, 15, 180))
        painter.drawRoundedRect(panel_rect, 10, 10)

        painter.setPen(QColor("white"))
        info_font = QFont()
        info_font.setPointSize(9)
        painter.setFont(info_font)

        map_state = "Yüklü" if self.map_source.available else "Yok"
        painter.drawText(22, 33, f"MBTiles: {map_state}")
        painter.drawText(22, 50, f"Zoom: {self.zoom:.2f}")
        painter.drawText(22, 67, f"Merkez: {self.center_lat:.5f}, {self.center_lon:.5f}")
        painter.drawText(22, 84, "Sol tık/sürükle: pan | Teker: zoom")

        if not self.map_source.available:
            msg_rect = self.rect().adjusted(20, 110, -20, -20)
            painter.setPen(QColor(220, 220, 220))
            painter.drawText(
                msg_rect,
                Qt.AlignTop | Qt.AlignHCenter,
                "Harita bulunamadı.\nassets/maps/mission_map.mbtiles dosyasını ekleyin.",
            )

    # =========================================================
    # OVERLAY MARKERS
    # =========================================================
    def set_overlay_markers(self, markers):
        self.overlay_markers = list(markers) if markers else []

        if self.shared_map_state is not None and hasattr(self.shared_map_state, "set_overlay_markers"):
            self.shared_map_state.set_overlay_markers(self.overlay_markers)

        self.update()

    def _get_effective_overlay_markers(self):
        if self.shared_map_state is not None and hasattr(self.shared_map_state, "get_overlay_markers"):
            markers = list(self.shared_map_state.get_overlay_markers())
            if markers:
                return markers

        markers = []

        if self.shared_map_state is not None:
            aircraft_lat = getattr(self.shared_map_state, "aircraft_lat", None)
            aircraft_lon = getattr(self.shared_map_state, "aircraft_lon", None)
            aircraft_heading = float(getattr(self.shared_map_state, "aircraft_heading", 0.0))

            if aircraft_lat is not None and aircraft_lon is not None:
                markers.append({
                    "type": "aircraft",
                    "lat": aircraft_lat,
                    "lon": aircraft_lon,
                    "label": "UAV",
                    "heading": aircraft_heading
                })

        if markers:
            return markers

        return [
            marker for marker in self.overlay_markers
            if marker.get("type") == "aircraft"
        ]

    def _draw_effective_overlay_markers(self, painter: QPainter):
        markers = self._get_effective_overlay_markers()
        if not markers:
            return

        for marker in markers:
            lat = marker.get("lat")
            lon = marker.get("lon")

            if lat is None or lon is None:
                continue

            pos = self._latlon_to_screen(lat, lon)

            if pos.x() < -50 or pos.x() > self.width() + 50:
                continue
            if pos.y() < -50 or pos.y() > self.height() + 50:
                continue

            marker_type = marker.get("type", "")

            if marker_type == "aircraft":
                heading = float(marker.get("heading", 0.0))
                self._draw_aircraft_symbol(painter, pos.x(), pos.y(), heading, marker.get("label", "UAV"))
                continue

            if marker_type == "qr":
                if self._draw_pixmap_marker(
                    painter,
                    self.qr_pixmap,
                    pos.x(),
                    pos.y(),
                    marker.get("label", "QR"),
                    size=34,
                    angle=0.0,
                    label_color=QColor("#ffffff"),
                ):
                    continue
                fill = QColor("#9c27b0")
                outline = QColor("white")
            elif marker_type == "enemy":
                heading = float(marker.get("heading", 0.0) or 0.0)
                if self._draw_pixmap_marker(
                    painter,
                    self.enemy_pixmap,
                    pos.x(),
                    pos.y(),
                    marker.get("label", "Rakip"),
                    size=34,
                    angle=heading - 45.0,
                    label_color=QColor("#ff5252"),
                ):
                    continue
                fill = QColor("#ff3b30")
                outline = QColor("white")
            else:
                fill = QColor("#ff9800")
                outline = QColor("white")

            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(outline, 2))
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(QPointF(pos.x(), pos.y()), 7, 7)
            painter.restore()

            label = marker.get("label")
            if label:
                painter.save()
                painter.setPen(QColor("white"))
                painter.setFont(QFont("Arial", 9, QFont.Bold))
                painter.drawText(int(pos.x() + 11), int(pos.y() - 9), label)
                painter.restore()

    def _draw_pixmap_marker(
        self,
        painter: QPainter,
        pixmap: QPixmap,
        center_x: float,
        center_y: float,
        label: str = "",
        size: int = 34,
        angle: float = 0.0,
        label_color: QColor = QColor("white"),
    ) -> bool:
        if pixmap is None or pixmap.isNull():
            return False

        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if abs(float(angle or 0.0)) > 0.01:
            self._draw_rotated_pixmap(painter, pixmap, center_x, center_y, size, size, float(angle))
        else:
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(
                QRect(
                    int(center_x - scaled.width() / 2),
                    int(center_y - scaled.height() / 2),
                    scaled.width(),
                    scaled.height(),
                ),
                scaled,
            )
        painter.restore()

        if label:
            painter.save()
            painter.setPen(label_color)
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(int(center_x + size / 2 + 4), int(center_y - size / 2 + 10), str(label))
            painter.restore()
        return True

    def _draw_aircraft_symbol(self, painter: QPainter, center_x: float, center_y: float, heading: float, label: str = "UAV"):
        angle = math.radians(float(heading) % 360.0)
        forward = QPointF(math.sin(angle), -math.cos(angle))
        right = QPointF(math.cos(angle), math.sin(angle))
        center = QPointF(center_x, center_y)

        def point(fwd: float, side: float) -> QPointF:
            return QPointF(
                center.x() + forward.x() * fwd + right.x() * side,
                center.y() + forward.y() * fwd + right.y() * side,
            )

        body = QPolygonF([
            point(20, 0),
            point(3, 6),
            point(-14, 4),
            point(-9, 0),
            point(-14, -4),
            point(3, -6),
        ])
        left_wing = QPolygonF([point(4, -4), point(-5, -22), point(-9, -8)])
        right_wing = QPolygonF([point(4, 4), point(-5, 22), point(-9, 8)])
        tail_left = QPolygonF([point(-10, -3), point(-18, -12), point(-16, -4)])
        tail_right = QPolygonF([point(-10, 3), point(-18, 12), point(-16, 4)])

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor("#061018"), 2))
        painter.setBrush(QBrush(QColor("#f7f9fb")))
        painter.drawPolygon(left_wing)
        painter.drawPolygon(right_wing)
        painter.drawPolygon(tail_left)
        painter.drawPolygon(tail_right)
        painter.drawPolygon(body)

        painter.setPen(QPen(QColor("#00e676"), 2))
        painter.drawLine(point(-12, 0), point(17, 0))
        painter.setPen(QPen(QColor("#061018"), 2))
        painter.setBrush(QBrush(QColor("#00e676")))
        painter.drawEllipse(center, 3.5, 3.5)

        if label:
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.setPen(QColor("#00e676"))
            painter.drawText(int(center_x + 15), int(center_y - 12), label)
        painter.restore()

    def _draw_rotated_pixmap(
        self,
        painter: QPainter,
        pixmap: QPixmap,
        center_x: float,
        center_y: float,
        width: int,
        height: int,
        angle: float
    ):
        scaled = pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        transform = QTransform()
        transform.translate(scaled.width() / 2, scaled.height() / 2)
        transform.rotate(angle)
        transform.translate(-scaled.width() / 2, -scaled.height() / 2)
        rotated = scaled.transformed(transform, Qt.SmoothTransformation)

        painter.drawPixmap(
            int(center_x - rotated.width() / 2),
            int(center_y - rotated.height() / 2),
            rotated
        )

    def set_initial_view(self, lat: float, lon: float, zoom: float = 16.0):
        self.center_lat = float(lat)
        self.center_lon = float(lon)
        self.zoom = max(self.min_zoom, min(self.max_zoom, float(zoom)))
        self._publish_shared_view()
        self.update()
