from __future__ import annotations

import json
import mimetypes
from io import BytesIO
import math
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import config


class UAVLogViewerServer:
    def __init__(self, root_dir: Path, mbtiles_path: Path | None = None, host: str = "127.0.0.1", port: int = 0):
        self.root_dir = Path(root_dir)
        self.mbtiles_paths = self._discover_mbtiles(mbtiles_path)
        self.host = host
        self.port = port
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._tile_connections: dict[Path, sqlite3.Connection] = {}
        self._tile_lock = threading.Lock()
        self._analysis_payload = {
            "analysis_active": False,
            "opponents": [],
            "mission": [],
            "ownship": None,
        }
        self._analysis_lock = threading.Lock()
        self._analysis_plane_cache: bytes | None = None
        self._analysis_plane_lock = threading.Lock()

    @property
    def url(self) -> str:
        if self.httpd is None:
            return ""
        return f"http://{self.host}:{self.httpd.server_address[1]}/#/"

    def start(self):
        if self.httpd is not None:
            return
        if not self.root_dir.exists():
            raise FileNotFoundError(f"UAVLogViewer dist not found: {self.root_dir}")

        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                server._handle_get(self)

            def log_message(self, _format, *_args):
                return

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        for connection in self._tile_connections.values():
            connection.close()
        self._tile_connections.clear()

    def set_analysis_payload(self, payload: dict):
        """Publish a JSON-safe snapshot for the embedded 3D analysis page."""
        try:
            serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            normalized = json.loads(serialized)
        except (TypeError, ValueError):
            return
        with self._analysis_lock:
            self._analysis_payload = normalized

    def _handle_get(self, handler: BaseHTTPRequestHandler):
        parsed = urlparse(handler.path)
        path = unquote(parsed.path)
        if path.startswith("/local-tiles/"):
            self._serve_tile(handler, path)
            return
        if path == "/local-mosaic.png":
            self._serve_mosaic(handler, parsed.query)
            return
        if path == "/local-backdrop.png":
            self._serve_mosaic(
                handler,
                parsed.query,
                default_z=14,
                max_dimension=2048,
                quality=70,
                fill_missing=True,
                blur_radius=10.0,
                cache_control="public, max-age=86400",
            )
            return
        if path == "/opponent-telemetry/sample":
            self._serve_opponent_sample(handler)
            return
        if path == "/analysis-data":
            self._serve_analysis_data(handler)
            return
        if path == "/analysis-plane.jpg":
            self._serve_analysis_plane(handler)
            return
        if path.startswith("/quantized/"):
            handler.send_response(404)
            handler.end_headers()
            return
        self._serve_static(handler, path)

    def _serve_analysis_data(self, handler: BaseHTTPRequestHandler):
        with self._analysis_lock:
            data = json.dumps(
                self._analysis_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        handler.end_headers()
        self._write_body(handler, data)

    def _serve_analysis_plane(self, handler: BaseHTTPRequestHandler):
        with self._analysis_plane_lock:
            if self._analysis_plane_cache is None:
                self._analysis_plane_cache = self._build_analysis_plane()
            data = self._analysis_plane_cache
        if data is None:
            handler.send_response(404)
            handler.end_headers()
            return
        handler.send_response(200)
        handler.send_header("Content-Type", "image/jpeg")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", "public, max-age=86400")
        handler.end_headers()
        self._write_body(handler, data)

    def _build_analysis_plane(self) -> bytes | None:
        try:
            from PIL import Image
        except Exception:
            return None

        inner = {"west": 38.4000, "south": 38.3083, "east": 38.4520, "north": 38.3360}
        outer = {"west": 38.3636, "south": 38.28891, "east": 38.4884, "north": 38.35539}
        mosaic_data = self._build_mosaic(
            inner["west"],
            inner["south"],
            inner["east"],
            inner["north"],
            z=17,
            max_dimension=1700,
            quality=92,
            fill_missing=False,
        )
        if mosaic_data is None:
            return None

        size = 2048
        plane = Image.new("RGB", (size, size), (117, 99, 72))
        mosaic = Image.open(BytesIO(mosaic_data)).convert("RGB")
        x0 = round((inner["west"] - outer["west"]) / (outer["east"] - outer["west"]) * size)
        x1 = round((inner["east"] - outer["west"]) / (outer["east"] - outer["west"]) * size)
        y0 = round((outer["north"] - inner["north"]) / (outer["north"] - outer["south"]) * size)
        y1 = round((outer["north"] - inner["south"]) / (outer["north"] - outer["south"]) * size)
        mosaic = mosaic.resize((max(1, x1 - x0), max(1, y1 - y0)), Image.Resampling.LANCZOS)
        plane.paste(mosaic, (x0, y0))

        output = BytesIO()
        plane.save(output, format="JPEG", quality=91, optimize=True)
        return output.getvalue()

    def _serve_opponent_sample(self, handler: BaseHTTPRequestHandler):
        sample_path = Path(__file__).resolve().parents[1] / "assets" / "data" / "sample_opponent_telemetry.json"
        if not sample_path.exists():
            handler.send_response(404)
            handler.end_headers()
            return

        data = sample_path.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        self._write_body(handler, data)

    def _serve_static(self, handler: BaseHTTPRequestHandler, path: str):
        relative = path.lstrip("/") or "index.html"
        file_path = (self.root_dir / relative).resolve()
        root = self.root_dir.resolve()
        if root not in file_path.parents and file_path != root:
            handler.send_response(403)
            handler.end_headers()
            return
        if not file_path.exists() or not file_path.is_file():
            file_path = self.root_dir / "index.html"

        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        served_path = file_path
        use_gzip = (
            "gzip" in handler.headers.get("Accept-Encoding", "")
            and file_path.name != "index.html"
            and file_path.with_name(file_path.name + ".gz").exists()
        )
        if use_gzip:
            served_path = file_path.with_name(file_path.name + ".gz")
        data = served_path.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        if use_gzip:
            handler.send_header("Content-Encoding", "gzip")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        self._write_body(handler, data)

    def _serve_tile(self, handler: BaseHTTPRequestHandler, path: str):
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            handler.send_response(404)
            handler.end_headers()
            return
        try:
            z = int(parts[1])
            x = int(parts[2])
            y_xyz = int(Path(parts[3]).stem)
        except ValueError:
            handler.send_response(404)
            handler.end_headers()
            return

        tile = self._read_mbtiles_tile(z, x, y_xyz)
        content_type = self._tile_content_type(tile) if tile else "application/octet-stream"
        if tile is None:
            tile = self._read_parent_tile(z, x, y_xyz)
            content_type = "image/jpeg" if tile else content_type
        if tile is None:
            tile = self._read_child_tile(z, x, y_xyz)
            content_type = "image/jpeg" if tile else content_type
        if tile is None:
            handler.send_response(204)
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            return

        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(tile)))
        handler.send_header("Cache-Control", "public, max-age=86400")
        handler.end_headers()
        self._write_body(handler, tile)

    def _serve_mosaic(
        self,
        handler: BaseHTTPRequestHandler,
        query: str,
        default_z: int = 17,
        max_dimension: int = 4096,
        quality: int = 88,
        fill_missing: bool = False,
        blur_radius: float = 0.0,
        cache_control: str = "no-store",
    ):
        try:
            from PIL import Image
        except Exception:
            handler.send_response(404)
            handler.end_headers()
            return

        params = parse_qs(query)
        try:
            west = float(params.get("west", [""])[0])
            south = float(params.get("south", [""])[0])
            east = float(params.get("east", [""])[0])
            north = float(params.get("north", [""])[0])
            z = int(params.get("z", [str(default_z)])[0])
        except ValueError:
            handler.send_response(400)
            handler.end_headers()
            return

        if not (-180 <= west < east <= 180 and -85 <= south < north <= 85):
            handler.send_response(400)
            handler.end_headers()
            return

        try:
            data = self._build_mosaic(
                west,
                south,
                east,
                north,
                max(0, min(19, z)),
                max_dimension,
                quality,
                fill_missing,
                blur_radius,
            )
        except Exception:
            data = None

        if data is None:
            handler.send_response(204)
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            return

        handler.send_response(200)
        handler.send_header("Content-Type", "image/jpeg")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", cache_control)
        handler.end_headers()
        self._write_body(handler, data)

    def _write_body(self, handler: BaseHTTPRequestHandler, data: bytes):
        try:
            handler.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _build_mosaic(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        z: int,
        max_dimension: int = 4096,
        quality: int = 88,
        fill_missing: bool = False,
        blur_radius: float = 0.0,
    ) -> bytes | None:
        try:
            from PIL import Image
        except Exception:
            return None

        tile_size = 256
        west_px, north_px = self._lonlat_to_world_pixel(west, north, z)
        east_px, south_px = self._lonlat_to_world_pixel(east, south, z)
        min_tile_x = math.floor(west_px / tile_size)
        max_tile_x = math.floor((east_px - 1) / tile_size)
        min_tile_y = math.floor(north_px / tile_size)
        max_tile_y = math.floor((south_px - 1) / tile_size)

        tile_count = (max_tile_x - min_tile_x + 1) * (max_tile_y - min_tile_y + 1)
        if tile_count <= 0 or tile_count > 900:
            return None

        width = (max_tile_x - min_tile_x + 1) * tile_size
        height = (max_tile_y - min_tile_y + 1) * tile_size
        mosaic = Image.new("RGB", (width, height), (54, 78, 58))
        found = False
        found_tiles = []
        missing_tiles = []

        for x in range(min_tile_x, max_tile_x + 1):
            for y in range(min_tile_y, max_tile_y + 1):
                tile = self._read_mbtiles_tile(z, x, y)
                if tile is None:
                    tile = self._read_parent_tile(z, x, y)
                if tile is None:
                    tile = self._read_child_tile(z, x, y)
                if tile is None:
                    missing_tiles.append((x, y))
                    continue
                try:
                    image = Image.open(BytesIO(tile)).convert("RGB")
                    image = image.resize((tile_size, tile_size))
                    mosaic.paste(image, ((x - min_tile_x) * tile_size, (y - min_tile_y) * tile_size))
                    found_tiles.append((x, y, image.copy()))
                    found = True
                except Exception:
                    missing_tiles.append((x, y))
                    continue

        if not found:
            return None

        if fill_missing and found_tiles and missing_tiles:
            for x, y in missing_tiles:
                nearest = min(found_tiles, key=lambda item: (item[0] - x) ** 2 + (item[1] - y) ** 2)
                image = nearest[2].resize((32, 32), Image.Resampling.BILINEAR)
                image = image.resize((tile_size, tile_size), Image.Resampling.BILINEAR)
                mosaic.paste(image, ((x - min_tile_x) * tile_size, (y - min_tile_y) * tile_size))

        crop_box = (
            max(0, int(round(west_px - min_tile_x * tile_size))),
            max(0, int(round(north_px - min_tile_y * tile_size))),
            min(width, int(round(east_px - min_tile_x * tile_size))),
            min(height, int(round(south_px - min_tile_y * tile_size))),
        )
        cropped = mosaic.crop(crop_box)
        if max(cropped.size) > max_dimension:
            cropped.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        if blur_radius > 0:
            # The backdrop covers a much wider area than the detailed flight
            # mosaic.  Blurring this single low-zoom image keeps the context
            # visible without asking Cesium to stream hundreds of sharp tiles.
            from PIL import ImageFilter
            cropped = cropped.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        output = BytesIO()
        cropped.save(output, format="JPEG", quality=quality)
        return output.getvalue()

    @staticmethod
    def _lonlat_to_world_pixel(lon: float, lat: float, z: int) -> tuple[float, float]:
        lat_rad = math.radians(max(-85.05112878, min(85.05112878, lat)))
        scale = (1 << z) * 256
        x = (lon + 180.0) / 360.0 * scale
        y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * scale
        return x, y

    def _read_mbtiles_tile(self, z: int, x: int, y_xyz: int) -> bytes | None:
        n = 1 << z
        if y_xyz < 0 or y_xyz >= n:
            return None
        y_tms = (n - 1) - y_xyz
        with self._tile_lock:
            for path in self.mbtiles_paths:
                if not path.exists():
                    continue
                connection = self._tile_connections.get(path)
                if connection is None:
                    connection = sqlite3.connect(str(path), check_same_thread=False)
                    self._tile_connections[path] = connection
                row = connection.execute(
                    "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                    (z, x % n, y_tms),
                ).fetchone()
                if row:
                    return bytes(row[0])
        return None

    def _read_parent_tile(self, z: int, x: int, y_xyz: int) -> bytes | None:
        try:
            from PIL import Image
        except Exception:
            return None

        child_z = z
        child_x = x
        child_y = y_xyz
        while child_z > 0:
            parent_z = child_z - 1
            parent_x = child_x // 2
            parent_y = child_y // 2
            parent_tile = self._read_mbtiles_tile(parent_z, parent_x, parent_y)
            if parent_tile is not None:
                try:
                    image = Image.open(BytesIO(parent_tile)).convert("RGB")
                    quadrant_x = child_x % 2
                    quadrant_y = child_y % 2
                    width, height = image.size
                    box = (
                        quadrant_x * width // 2,
                        quadrant_y * height // 2,
                        (quadrant_x + 1) * width // 2,
                        (quadrant_y + 1) * height // 2,
                    )
                    cropped = image.crop(box).resize((width, height), Image.Resampling.BILINEAR)
                    output = BytesIO()
                    cropped.save(output, format="JPEG", quality=88)
                    return output.getvalue()
                except Exception:
                    return parent_tile
            child_z = parent_z
            child_x = parent_x
            child_y = parent_y
        return None

    def _read_child_tile(self, z: int, x: int, y_xyz: int) -> bytes | None:
        try:
            from PIL import Image
        except Exception:
            return None

        with self._tile_lock:
            for path in self.mbtiles_paths:
                if not path.exists():
                    continue
                connection = self._tile_connections.get(path)
                if connection is None:
                    connection = sqlite3.connect(str(path), check_same_thread=False)
                    self._tile_connections[path] = connection

                zoom_rows = connection.execute(
                    "SELECT DISTINCT zoom_level FROM tiles WHERE zoom_level > ? ORDER BY zoom_level",
                    (z,),
                ).fetchall()
                for (child_z,) in zoom_rows:
                    factor = 1 << (child_z - z)
                    child_n = 1 << child_z
                    min_x = x * factor
                    max_x = ((x + 1) * factor) - 1
                    min_y_xyz = y_xyz * factor
                    max_y_xyz = ((y_xyz + 1) * factor) - 1
                    min_y_tms = (child_n - 1) - max_y_xyz
                    max_y_tms = (child_n - 1) - min_y_xyz

                    row = connection.execute(
                        """
                        SELECT tile_data
                        FROM tiles
                        WHERE zoom_level = ?
                          AND tile_column BETWEEN ? AND ?
                          AND tile_row BETWEEN ? AND ?
                        LIMIT 1
                        """,
                        (child_z, min_x, max_x, min_y_tms, max_y_tms),
                    ).fetchone()
                    if row:
                        try:
                            image = Image.open(BytesIO(row[0])).convert("RGB")
                            output = BytesIO()
                            image.save(output, format="JPEG", quality=86)
                            return output.getvalue()
                        except Exception:
                            return bytes(row[0])
        return None

    @staticmethod
    def _discover_mbtiles(mbtiles_path: Path | None) -> list[Path]:
        if mbtiles_path is not None:
            return [Path(mbtiles_path).resolve()]

        # Prefer the regular flight map, then fall back to purpose-built
        # analysis caches for logs recorded elsewhere.  Do not load unrelated
        # MBTiles (for example mission_map.mbtiles), because mixing basemap
        # styles in the same location produces visible seams.
        primary = Path(getattr(config, "MAP_MBTILES_PATH")).resolve()
        pattern = getattr(config, "ANALYSIS_MBTILES_GLOB", "analysis_*.mbtiles")
        paths = [primary]
        for candidate in sorted(primary.parent.glob(pattern)):
            resolved = candidate.resolve()
            if resolved not in paths:
                paths.append(resolved)
        return paths

    @staticmethod
    def _tile_content_type(tile: bytes) -> str:
        if tile.startswith(b"\x89PNG"):
            return "image/png"
        if tile.startswith(b"\xff\xd8"):
            return "image/jpeg"
        if tile.startswith(b"RIFF") and b"WEBP" in tile[:16]:
            return "image/webp"
        return "application/octet-stream"
