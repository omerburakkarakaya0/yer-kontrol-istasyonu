import json
import socket
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QImage


class RefereeVideoStream:
    def __init__(self, port: int = 8092, fps: float = 10.0, jpeg_quality: int = 70):
        self.port = int(port)
        self.fps = max(1.0, min(30.0, float(fps)))
        self.jpeg_quality = max(25, min(95, int(jpeg_quality)))
        self._lock = threading.Lock()
        self._latest_jpeg: Optional[bytes] = None
        self._server: Optional[ThreadingHTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._upload_thread: Optional[threading.Thread] = None
        self._running = False
        self._upload_running = False
        self._upload_url: Optional[str] = None
        self._last_upload_error = ""
        self._next_upload_attempt_at = 0.0

    def start(self):
        if self._server is not None:
            return

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<html><body style='margin:0;background:#000'><img src='/video.mjpg' style='width:100%;height:100%;object-fit:contain'></body></html>")
                    return

                if self.path == "/snapshot.jpg":
                    frame = owner.latest_jpeg()
                    if not frame:
                        self.send_error(503, "No frame yet")
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(frame)))
                    self.end_headers()
                    self.wfile.write(frame)
                    return

                if self.path != "/video.mjpg":
                    self.send_error(404)
                    return

                self.send_response(200)
                self.send_header("Age", "0")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()

                delay = 1.0 / owner.fps
                while owner._running:
                    frame = owner.latest_jpeg()
                    if frame:
                        try:
                            self.wfile.write(b"--frame\r\n")
                            self.wfile.write(b"Content-Type: image/jpeg\r\n")
                            self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                            self.wfile.write(frame)
                            self.wfile.write(b"\r\n")
                            self.wfile.flush()
                        except Exception:
                            break
                    time.sleep(delay)

            def log_message(self, _format, *args):
                return

        self._server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self._server.daemon_threads = True
        self._running = True
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()

    def stop(self):
        self.stop_upload()
        self._running = False
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
        self._server = None
        self._server_thread = None

    def update_frame(self, image: QImage):
        if image is None or image.isNull():
            return
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        if not buffer.open(QIODevice.WriteOnly):
            return
        image.save(buffer, "JPG", self.jpeg_quality)
        frame = bytes(byte_array)
        if not frame:
            return
        with self._lock:
            self._latest_jpeg = frame

    def latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def stream_url(self, referee_host: str = "") -> str:
        host = self._local_ip_for(referee_host) or "127.0.0.1"
        return f"http://{host}:{self.port}/video.mjpg"

    def start_upload(self, base_url: str, path: str = "/api/kamera_gonder"):
        if not base_url:
            return
        self._upload_url = base_url.rstrip("/") + path
        if self._upload_running:
            return
        self._upload_running = True
        self._upload_thread = threading.Thread(target=self._upload_loop, daemon=True)
        self._upload_thread.start()

    def stop_upload(self):
        self._upload_running = False
        self._upload_thread = None

    def register_stream_url(self, base_url: str, stream_url: str, team_number: int = 1):
        if not base_url or not stream_url:
            return
        body = json.dumps({"takim_numarasi": team_number, "stream_url": stream_url, "url": stream_url}).encode("utf-8")
        for path in ("/api/kamera_adresi", "/api/video_stream"):
            try:
                req = urllib.request.Request(base_url.rstrip("/") + path, data=body, method="POST")
                req.add_header("Content-Type", "application/json")
                urllib.request.urlopen(req, timeout=1.0).read()
                return
            except Exception:
                continue

    def _upload_loop(self):
        delay = 1.0 / self.fps
        while self._upload_running:
            frame = self.latest_jpeg()
            now = time.time()
            if frame and self._upload_url and now >= self._next_upload_attempt_at:
                try:
                    req = urllib.request.Request(self._upload_url, data=frame, method="POST")
                    req.add_header("Content-Type", "image/jpeg")
                    urllib.request.urlopen(req, timeout=0.8).read()
                    self._last_upload_error = ""
                    self._next_upload_attempt_at = 0.0
                except Exception as exc:
                    self._last_upload_error = str(exc)
                    self._next_upload_attempt_at = time.time() + 5.0
            time.sleep(delay)

    @staticmethod
    def _local_ip_for(remote_host: str) -> str:
        host = str(remote_host or "").strip()
        if host.startswith("http://") or host.startswith("https://"):
            host = host.split("://", 1)[1].split("/", 1)[0].split(":", 1)[0]
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((host or "8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
            sock.close()
            return local_ip
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"
