from __future__ import annotations

import argparse
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import cv2
except ModuleNotFoundError as exc:
    raise SystemExit("OpenCV gerekli: python -m pip install opencv-python") from exc


class CameraStreamer:
    def __init__(self, source: str | int, width: int, height: int, fps: float, quality: int):
        self.source = source
        self.width = width
        self.height = height
        self.fps = max(1.0, min(30.0, fps))
        self.quality = max(25, min(95, quality))

    def open_capture(self):
        cap = cv2.VideoCapture(self.source)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.width))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.height))
        cap.set(cv2.CAP_PROP_FPS, float(self.fps))
        if not cap.isOpened():
            raise RuntimeError(f"Kamera acilamadi: {self.source}")
        return cap

    def frame_generator(self):
        cap = self.open_capture()
        delay = 1.0 / self.fps
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.1)
                    continue
                ok, encoded = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), self.quality],
                )
                if not ok:
                    continue
                data = encoded.tobytes()
                yield data
                time.sleep(delay)
        finally:
            cap.release()


def parse_source(value: str):
    text = str(value).strip()
    return int(text) if text.isdigit() else text


def main():
    parser = argparse.ArgumentParser(description="BLACK BOX aircraft camera MJPEG streamer")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8092)
    parser.add_argument("--source", default="0")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--quality", type=int, default=70)
    args = parser.parse_args()

    streamer = CameraStreamer(
        source=parse_source(args.source),
        width=args.width,
        height=args.height,
        fps=args.fps,
        quality=args.quality,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body style='margin:0;background:#000'>"
                    b"<img src='/video.mjpg' style='width:100%;height:100%;object-fit:contain'>"
                    b"</body></html>"
                )
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

            try:
                for frame in streamer.frame_generator():
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
            except Exception:
                return

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Aircraft camera stream: http://{args.host}:{args.port}/video.mjpg")
    server.serve_forever()


if __name__ == "__main__":
    main()
