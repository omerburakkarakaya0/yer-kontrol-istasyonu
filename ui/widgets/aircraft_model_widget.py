import math
import os
import struct
import zipfile
from dataclasses import dataclass
from typing import List, Tuple
from xml.etree import ElementTree as ET

from PyQt5.QtCore import Qt, QPointF, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF, QBrush, QFont
from PyQt5.QtWidgets import QWidget, QSizePolicy


Point3 = Tuple[float, float, float]


@dataclass
class Face:
    points: Tuple[Point3, Point3, Point3]
    normal: Point3


class AircraftModelWidget(QWidget):
    """Lightweight STL preview synchronized with aircraft attitude telemetry."""

    def __init__(self, model_path: str, max_faces: int = 4500, parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.max_faces = max_faces
        self.pitch = 0.0
        self.roll = 0.0
        self.yaw = 0.0
        self.heading = 0.0
        self._target_pitch = 0.0
        self._target_roll = 0.0
        self._target_yaw = 0.0
        self._has_attitude = False
        self.faces: List[Face] = []
        self.load_error = ""

        self.setMinimumSize(260, 210)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setToolTip("3D aircraft attitude preview")
        self._load_model()
        self._render_timer = QTimer(self)
        self._render_timer.timeout.connect(self._tick_render)
        self._configure_render_timer()

    def set_heading(self, heading: float):
        new_heading = float(heading or 0.0) % 360.0
        if abs(new_heading - self.heading) < 0.1:
            return
        self.heading = new_heading
        self.update()

    def set_attitude(self, pitch: float, roll: float, yaw: float):
        new_pitch = float(pitch or 0.0)
        new_roll = float(roll or 0.0)
        new_yaw = float(yaw or 0.0)

        try:
            import config
            min_delta = float(getattr(config, "AIRCRAFT_MODEL_MIN_ATTITUDE_DELTA_DEG", 0.25))
        except Exception:
            min_delta = 0.25

        if self._has_attitude and max(
            abs(new_pitch - self._target_pitch),
            abs(new_roll - self._target_roll),
            abs(new_yaw - self._target_yaw),
        ) < min_delta:
            return

        self._target_pitch = new_pitch
        self._target_roll = new_roll
        self._target_yaw = new_yaw
        self._has_attitude = True

    def _tick_render(self):
        if not self._has_attitude:
            return

        try:
            import config
            alpha = float(getattr(config, "AIRCRAFT_MODEL_SMOOTHING_ALPHA", 0.35))
        except Exception:
            alpha = 0.35
        alpha = max(0.0, min(1.0, alpha))

        old = (self.pitch, self.roll, self.yaw)
        if alpha >= 1.0:
            self.pitch = self._target_pitch
            self.roll = self._target_roll
            self.yaw = self._target_yaw
        else:
            self.pitch = self.pitch + (self._target_pitch - self.pitch) * alpha
            self.roll = self.roll + (self._target_roll - self.roll) * alpha
            self.yaw = self.yaw + (self._target_yaw - self.yaw) * alpha

        if max(
            abs(self.pitch - old[0]),
            abs(self.roll - old[1]),
            abs(self.yaw - old[2]),
        ) >= 0.01:
            self.update()

    def _configure_render_timer(self):
        try:
            import config
            max_fps = float(getattr(config, "AIRCRAFT_MODEL_MAX_FPS", 12))
        except Exception:
            max_fps = 12.0

        if max_fps <= 0:
            max_fps = 30.0
        interval_ms = max(16, int(1000.0 / max_fps))
        self._render_timer.start(interval_ms)

    def _load_model(self):
        if not self.model_path or not os.path.exists(self.model_path):
            self.load_error = "Model not found"
            return

        try:
            raw_faces = self._read_model(self.model_path)
            if not raw_faces:
                self.load_error = "Model has no faces"
                return

            if self.max_faces and self.max_faces > 0 and len(raw_faces) > self.max_faces:
                step = max(1, len(raw_faces) // self.max_faces)
                raw_faces = raw_faces[::step][: self.max_faces]

            self.faces = self._normalize_faces(raw_faces)
        except Exception as exc:
            self.faces = []
            self.load_error = f"Model load failed: {exc}"

    def _read_model(self, path: str) -> List[Face]:
        lower_path = path.lower()
        if os.path.isdir(path) or lower_path.endswith(".3mf") or zipfile.is_zipfile(path):
            return self._read_3mf(path)
        return self._read_stl(path)

    def _read_stl(self, path: str) -> List[Face]:
        with open(path, "rb") as fh:
            data = fh.read()

        if len(data) >= 84:
            face_count = struct.unpack_from("<I", data, 80)[0]
            expected_size = 84 + face_count * 50
            if face_count > 0 and expected_size <= len(data):
                return self._read_binary_stl(data, face_count)

        return self._read_ascii_stl(data.decode("utf-8", errors="ignore"))

    def _read_3mf(self, path: str) -> List[Face]:
        xml_data = self._read_3mf_model_xml(path)
        root = ET.fromstring(xml_data)
        faces: List[Face] = []

        for mesh in self._iter_by_local_name(root, "mesh"):
            vertices_node = self._first_child_by_local_name(mesh, "vertices")
            triangles_node = self._first_child_by_local_name(mesh, "triangles")
            if vertices_node is None or triangles_node is None:
                continue

            vertices: List[Point3] = []
            for vertex in self._iter_by_local_name(vertices_node, "vertex"):
                vertices.append((
                    float(vertex.attrib.get("x", "0")),
                    float(vertex.attrib.get("y", "0")),
                    float(vertex.attrib.get("z", "0")),
                ))

            for triangle in self._iter_by_local_name(triangles_node, "triangle"):
                try:
                    v1 = int(triangle.attrib["v1"])
                    v2 = int(triangle.attrib["v2"])
                    v3 = int(triangle.attrib["v3"])
                    p1, p2, p3 = vertices[v1], vertices[v2], vertices[v3]
                except (KeyError, ValueError, IndexError):
                    continue
                faces.append(Face((p1, p2, p3), self._face_normal(p1, p2, p3)))

        return faces

    def _read_3mf_model_xml(self, path: str) -> bytes:
        if os.path.isdir(path):
            model_path = os.path.join(path, "3D", "3dmodel.model")
            with open(model_path, "rb") as fh:
                return fh.read()

        with zipfile.ZipFile(path, "r") as archive:
            for name in archive.namelist():
                if name.lower().endswith("3d/3dmodel.model"):
                    return archive.read(name)
            for name in archive.namelist():
                if name.lower().endswith(".model"):
                    return archive.read(name)
        raise ValueError("3MF model XML not found")

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _iter_by_local_name(cls, node, name: str):
        for child in node.iter():
            if cls._local_name(child.tag) == name:
                yield child

    @classmethod
    def _first_child_by_local_name(cls, node, name: str):
        for child in list(node):
            if cls._local_name(child.tag) == name:
                return child
        return None

    def _read_binary_stl(self, data: bytes, face_count: int) -> List[Face]:
        faces: List[Face] = []
        offset = 84
        max_faces = self.max_faces if self.max_faces and self.max_faces > 0 else face_count
        step = max(1, face_count // max_faces)
        for index in range(face_count):
            if index % step != 0:
                offset += 50
                continue
            values = struct.unpack_from("<12f", data, offset)
            normal = values[0:3]
            p1 = values[3:6]
            p2 = values[6:9]
            p3 = values[9:12]
            faces.append(Face((p1, p2, p3), normal))
            offset += 50
            if len(faces) >= max_faces:
                break
        return faces

    def _read_ascii_stl(self, text: str) -> List[Face]:
        faces: List[Face] = []
        normal = (0.0, 0.0, 1.0)
        vertices: List[Point3] = []

        for line in text.splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            key = parts[0].lower()
            if key == "facet" and len(parts) >= 5 and parts[1].lower() == "normal":
                normal = (float(parts[2]), float(parts[3]), float(parts[4]))
            elif key == "vertex" and len(parts) >= 4:
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
                if len(vertices) == 3:
                    faces.append(Face((vertices[0], vertices[1], vertices[2]), normal))
                    vertices = []
        return faces

    def _normalize_faces(self, faces: List[Face]) -> List[Face]:
        points = [point for face in faces for point in face.points]
        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        min_z = min(p[2] for p in points)
        max_z = max(p[2] for p in points)

        center = (
            (min_x + max_x) / 2.0,
            (min_y + max_y) / 2.0,
            (min_z + max_z) / 2.0,
        )
        spans = [max_x - min_x, max_y - min_y, max_z - min_z]
        max_span = max(spans) or 1.0

        sorted_axes = sorted(range(3), key=lambda axis: spans[axis], reverse=True)
        right_axis = sorted_axes[0]
        forward_axis = sorted_axes[1]
        up_axis = sorted_axes[2]

        normalized: List[Face] = []
        for face in faces:
            mapped = []
            for point in face.points:
                centered = (
                    (point[0] - center[0]) / max_span,
                    (point[1] - center[1]) / max_span,
                    (point[2] - center[2]) / max_span,
                )
                mapped.append((
                    centered[right_axis],
                    centered[forward_axis],
                    centered[up_axis],
                ))
            normal = self._face_normal(mapped[0], mapped[1], mapped[2])
            normalized.append(Face((mapped[0], mapped[1], mapped[2]), normal))

        return normalized

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101811"))

        w = self.width()
        h = self.height()
        painter.setPen(QPen(QColor("#344b37"), 1))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

        if not self.faces:
            painter.setPen(QColor("#a1af9c"))
            painter.drawText(self.rect(), Qt.AlignCenter, self.load_error or "3D model unavailable")
            return

        cx = w / 2.0
        cy = h / 2.0
        try:
            import config
            view_scale = float(getattr(config, "AIRCRAFT_MODEL_VIEW_SCALE", 1.18))
        except Exception:
            view_scale = 1.18
        scale = min(w, h) * view_scale
        distance = 2.6

        try:
            render_mode = str(getattr(config, "AIRCRAFT_MODEL_RENDER_MODE", "surface")).lower()
        except Exception:
            render_mode = "surface"

        if render_mode == "outline":
            self._paint_outline_model(painter, cx, cy, scale, distance)
            self._draw_status_overlay(painter)
            self._draw_compass_overlay(painter)
            return

        transformed = []
        for face in self.faces:
            pts = [self._rotate(point) for point in face.points]
            normal = self._face_normal(pts[0], pts[1], pts[2])
            if normal[2] <= -0.95:
                continue

            projected = []
            for x, y, z in pts:
                perspective = distance / (distance + z + 0.7)
                projected.append(QPointF(cx + x * scale * perspective, cy - y * scale * perspective))

            depth = sum(point[2] for point in pts) / 3.0
            light = self._clamp(0.35 + 0.65 * max(0.0, normal[2]), 0.25, 1.0)
            transformed.append((depth, projected, light))

        transformed.sort(key=lambda item: item[0])

        for _, projected, light in transformed:
            color = QColor(
                int(80 + 100 * light),
                int(95 + 107 * light),
                int(72 + 92 * light),
            )
            painter.setBrush(color)
            if bool(getattr(config, "AIRCRAFT_MODEL_DRAW_EDGES", False)):
                painter.setPen(QPen(QColor(170, 192, 156, 95), 0.25))
            else:
                painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygonF(projected))

        self._draw_status_overlay(painter)
        self._draw_compass_overlay(painter)

    def _paint_outline_model(self, painter: QPainter, cx: float, cy: float, scale: float, distance: float):
        triangles = []
        all_points = []

        for face in self.faces:
            pts = [self._rotate(point) for point in face.points]
            projected = []
            for x, y, z in pts:
                perspective = distance / (distance + z + 0.7)
                point = QPointF(cx + x * scale * perspective, cy - y * scale * perspective)
                projected.append(point)
                all_points.append((point.x(), point.y()))
            triangles.append(projected)

        hull = self._convex_hull(all_points)
        if hull:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#b4c7a7"), 2.4))
            painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in hull]))

        detail_limit = 1400
        try:
            import config
            detail_limit = int(getattr(config, "AIRCRAFT_MODEL_OUTLINE_DETAIL_LINES", detail_limit))
        except Exception:
            pass

        step = max(1, len(triangles) // max(1, detail_limit))
        painter.setPen(QPen(QColor(154, 180, 139, 85), 0.7))
        for triangle in triangles[::step]:
            p1, p2, p3 = triangle
            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)
            painter.drawLine(p3, p1)

    @staticmethod
    def _convex_hull(points):
        unique = sorted(set((round(x, 2), round(y, 2)) for x, y in points))
        if len(unique) <= 1:
            return unique

        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower = []
        for point in unique:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
                lower.pop()
            lower.append(point)

        upper = []
        for point in reversed(unique):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
                upper.pop()
            upper.append(point)

        return lower[:-1] + upper[:-1]

    def _rotate(self, point: Point3) -> Point3:
        import config

        pitch = math.radians(
            self.pitch * float(getattr(config, "AIRCRAFT_MODEL_PITCH_SIGN", 1.0))
            + float(getattr(config, "AIRCRAFT_MODEL_PITCH_OFFSET_DEG", 0.0))
        )
        roll = math.radians(
            self.roll * float(getattr(config, "AIRCRAFT_MODEL_ROLL_SIGN", 1.0))
            + float(getattr(config, "AIRCRAFT_MODEL_ROLL_OFFSET_DEG", 0.0))
        )
        yaw = math.radians(
            self.yaw * float(getattr(config, "AIRCRAFT_MODEL_YAW_SIGN", 1.0))
            + float(getattr(config, "AIRCRAFT_MODEL_YAW_OFFSET_DEG", 0.0))
            + float(getattr(config, "AIRCRAFT_MODEL_VIEW_YAW_OFFSET_DEG", 0.0))
        )

        x, y, z = point

        cr = math.cos(roll)
        sr = math.sin(roll)
        x, z = x * cr + z * sr, -x * sr + z * cr

        cp = math.cos(pitch)
        sp = math.sin(pitch)
        y, z = y * cp - z * sp, y * sp + z * cp

        cy = math.cos(yaw)
        sy = math.sin(yaw)
        x, y = x * cy - y * sy, x * sy + y * cy

        camera_pitch = math.radians(float(getattr(config, "AIRCRAFT_MODEL_VIEW_CAMERA_PITCH_DEG", 0.0)))
        cc = math.cos(camera_pitch)
        sc = math.sin(camera_pitch)
        y, z = y * cc - z * sc, y * sc + z * cc
        return x, y, z

    def _draw_status_overlay(self, painter: QPainter):
        painter.setPen(QColor("#a9c49b"))
        painter.drawText(12, 22, f"P {self.pitch:+05.1f}  R {self.roll:+05.1f}  Y {self.yaw:05.1f}")

    def _draw_compass_overlay(self, painter: QPainter):
        painter.save()
        radius = 30
        margin = 12
        cx = self.width() - radius - margin
        cy = radius + margin

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QBrush(QColor(20, 30, 22, 220)))
        painter.setPen(QPen(QColor("#6e8265"), 1.4))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.setPen(QColor("#f8fafc"))
        painter.drawText(cx - 4, cy - radius + 12, "N")
        painter.drawText(cx + radius - 12, cy + 4, "E")
        painter.drawText(cx - 4, cy + radius - 4, "S")
        painter.drawText(cx - radius + 5, cy + 4, "W")

        angle = math.radians(self.heading - 90.0)
        tip = QPointF(cx + math.cos(angle) * (radius - 9), cy + math.sin(angle) * (radius - 9))
        left = QPointF(cx + math.cos(angle + 2.55) * 8, cy + math.sin(angle + 2.55) * 8)
        right = QPointF(cx + math.cos(angle - 2.55) * 8, cy + math.sin(angle - 2.55) * 8)

        painter.setBrush(QBrush(QColor("#ef4444")))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygonF([tip, left, right]))
        painter.setBrush(QBrush(QColor("#e2e8f0")))
        painter.drawEllipse(QPointF(cx, cy), 3, 3)

        painter.setPen(QColor("#a9c49b"))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(cx - 22, cy + radius + 13, f"{self.heading:03.0f} deg")
        painter.restore()

    @staticmethod
    def _face_normal(a: Point3, b: Point3, c: Point3) -> Point3:
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        return nx / length, ny / length, nz / length

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
