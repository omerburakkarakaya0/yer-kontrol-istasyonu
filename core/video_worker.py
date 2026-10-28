"""
Video worker thread.

The UI receives ready-to-paint QImage frames while OpenCV capture and decode
work stays outside the Qt main thread.
"""
from typing import Optional, Union
import importlib
from pathlib import Path
import shutil
import subprocess

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPen


try:
    cv2 = importlib.import_module("cv2")
except ModuleNotFoundError:
    cv2 = None


class VideoWorker(QThread):
    frame_ready = pyqtSignal(QImage)
    video_finished = pyqtSignal()

    def __init__(self, video_source: Optional[Union[str, int]] = None, parent=None):
        super().__init__(parent)
        self.video_source = video_source
        self.running = False
        self.cap = None
        self.fps = 30
        self.gst_process = None

    def run(self):
        self.running = True

        source = self._normalize_source(self.video_source)
        if self._is_udp_h264_source(source):
            self._run_udp_h264(source)
            return

        if cv2 is None:
            self._generate_black_frame()
            return

        self.cap = self._open_capture(source)

        if not self.cap.isOpened():
            self._generate_black_frame()
            return

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        if self.fps <= 0 or self.fps > 120:
            self.fps = 30
        frame_delay_ms = max(1, int(1000 / self.fps))

        while self.running:
            ret, frame = self.cap.read()

            if not ret:
                self.video_finished.emit()
                if self._is_file_source(source):
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                self.msleep(100)
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, _ = frame_rgb.shape
            bytes_per_line = 3 * width
            q_image = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            self.frame_ready.emit(q_image.copy())
            self.msleep(frame_delay_ms)

        if self.cap:
            self.cap.release()

    def _run_udp_h264(self, source: str):
        decoder = self._preferred_udp_h264_decoder()
        if decoder in ("auto", "ffmpeg") and self._find_ffmpeg_launcher():
            self._run_ffmpeg_udp_h264(source)
            return
        if decoder == "ffmpeg":
            self._generate_black_frame("FFmpeg not found. Install FFmpeg or set FFMPEG_BIN_DIR.")
            return
        if decoder in ("auto", "gstreamer") and self._find_gstreamer_launcher():
            self._run_gstreamer_udp_h264(source)
            return
        self._generate_black_frame("Video decoder not available")

    def _run_gstreamer_udp_h264(self, source: str):
        gst = self._find_gstreamer_launcher()
        if not gst:
            self._generate_black_frame("GStreamer not available")
            return

        port = self._udp_h264_port(source)
        width = self._configured_width()
        height = self._configured_height()
        frame_size = width * height * 3
        cmd = self._gstreamer_udp_command(gst, port, width, height)

        try:
            self.gst_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=frame_size * 2,
            )
        except Exception:
            print("GStreamer stream failed:", " ".join(cmd))
            self._generate_black_frame("GStreamer stream failed")
            return

        while self.running and self.gst_process.poll() is None:
            raw = self.gst_process.stdout.read(frame_size)
            if len(raw) != frame_size:
                self.video_finished.emit()
                self.msleep(100)
                continue
            q_image = QImage(raw, width, height, width * 3, QImage.Format_RGB888)
            self.frame_ready.emit(q_image.copy())

        self._stop_gstreamer()

    def _gstreamer_udp_command(self, gst: str, port: int, width: int, height: int):
        input_format = self._udp_input_format()
        output = [
            "!",
            "videoconvert",
            "!",
            "videoscale",
            "!",
            f"video/x-raw,format=RGB,width={width},height={height}",
            "!",
            "queue",
            "leaky=downstream",
            "max-size-buffers=2",
            "max-size-time=0",
            "max-size-bytes=0",
            "!",
            "fdsink",
            "fd=1",
            "sync=false",
        ]

        if input_format == "rtp":
            return [
                gst,
                "-q",
                "udpsrc",
                f"port={port}",
                "buffer-size=1048576",
                "caps=application/x-rtp, media=(string)video, encoding-name=(string)H264, payload=(int)96, clock-rate=(int)90000",
                "!",
                "rtpjitterbuffer",
                "latency=30",
                "drop-on-latency=true",
                "!",
                "rtph264depay",
                "!",
                "h264parse",
                "disable-passthrough=true",
                "!",
                "avdec_h264",
                *output,
            ]

        if input_format == "rtp-jpeg":
            return [
                gst,
                "-q",
                "udpsrc",
                f"port={port}",
                "buffer-size=262144",
                "caps=application/x-rtp, media=(string)video, encoding-name=(string)JPEG, payload=(int)26, clock-rate=(int)90000",
                "!",
                "rtpjitterbuffer",
                "latency=0",
                "drop-on-latency=true",
                "do-lost=true",
                "!",
                "rtpjpegdepay",
                "!",
                "jpegdec",
                *output,
            ]

        if input_format == "mpegts":
            return [
                gst,
                "-q",
                "udpsrc",
                f"port={port}",
                "buffer-size=1048576",
                "!",
                "tsdemux",
                "!",
                "h264parse",
                "!",
                "avdec_h264",
                *output,
            ]

        if input_format == "raw-h264":
            return [
                gst,
                "-q",
                "udpsrc",
                f"port={port}",
                "buffer-size=1048576",
                "caps=video/x-h264, stream-format=(string)byte-stream, alignment=(string)nal",
                "!",
                "h264parse",
                "!",
                "avdec_h264",
                *output,
            ]

        return [
            gst,
            "-q",
            "udpsrc",
            f"port={port}",
            "buffer-size=1048576",
            "!",
            "queue",
            "leaky=downstream",
            "max-size-buffers=2",
            "max-size-time=0",
            "max-size-bytes=0",
            "!",
            "decodebin",
            *output,
        ]

    def _run_ffmpeg_udp_h264(self, source: str):
        ffmpeg = self._find_ffmpeg_launcher()
        if not ffmpeg:
            self._generate_black_frame("FFmpeg not found. Install FFmpeg or set FFMPEG_BIN_DIR.")
            return

        port = self._udp_h264_port(source)
        width = self._configured_width()
        height = self._configured_height()
        frame_size = width * height * 3
        input_url = f"udp://@:{port}?fifo_size=1000000&overrun_nonfatal=1"
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-probesize",
            "32",
            "-analyzeduration",
            "0",
            "-i",
            input_url,
            "-an",
            "-vf",
            f"scale={width}:{height}",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        ]

        retry_delay_ms = 1000
        self._emit_status_frame(f"Listening UDP video on port {port}...")

        while self.running:
            frame_count = 0
            try:
                self.gst_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=frame_size * 2,
                )
            except Exception as exc:
                print(f"FFmpeg stream failed to start: {exc}")
                print("FFmpeg command:", " ".join(cmd))
                self._emit_status_frame("FFmpeg stream failed")
                self.msleep(retry_delay_ms)
                continue

            while self.running and self.gst_process.poll() is None:
                raw = self.gst_process.stdout.read(frame_size)
                if len(raw) != frame_size:
                    self.video_finished.emit()
                    self.msleep(100)
                    continue
                q_image = QImage(raw, width, height, width * 3, QImage.Format_RGB888)
                self.frame_ready.emit(q_image.copy())
                frame_count += 1

            if frame_count == 0 and self.running:
                stderr_text = ""
                try:
                    stderr = self.gst_process.stderr.read() if self.gst_process and self.gst_process.stderr else b""
                    stderr_text = stderr.decode("utf-8", errors="replace").strip()
                except Exception:
                    stderr_text = ""
                if stderr_text:
                    print("FFmpeg video stderr:", stderr_text)
                print("FFmpeg command:", " ".join(cmd))
                self._emit_status_frame(f"No UDP video on port {port}. Retrying...")
                self._stop_gstreamer()
                self.msleep(retry_delay_ms)
                continue

            self._stop_gstreamer()

    def _open_capture(self, source):
        if isinstance(source, int):
            for index in self._candidate_camera_indexes(source):
                for backend in self._candidate_camera_backends():
                    cap = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
                    self.cap = cap
                    self._configure_webcam_capture()
                    if cap.isOpened():
                        return cap
                    cap.release()
            return cv2.VideoCapture(source)
        return cv2.VideoCapture(source)

    def _configure_webcam_capture(self):
        try:
            import config
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(getattr(config, "VIDEO_WIDTH", 640)))
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(getattr(config, "VIDEO_HEIGHT", 480)))
            self.cap.set(cv2.CAP_PROP_FPS, float(getattr(config, "VIDEO_FPS", 30)))
        except Exception:
            pass

    @staticmethod
    def _find_gstreamer_launcher() -> Optional[str]:
        found = shutil.which("gst-launch-1.0")
        if found:
            return found

        candidates = []
        try:
            import config
            configured = str(getattr(config, "GSTREAMER_BIN_DIR", "") or "").strip()
            if configured:
                candidates.append(Path(configured) / "gst-launch-1.0.exe")
        except Exception:
            pass

        candidates.extend([
            Path("C:/gstreamer/1.0/msvc_x86_64/bin/gst-launch-1.0.exe"),
            Path("C:/gstreamer/1.0/mingw_x86_64/bin/gst-launch-1.0.exe"),
            Path("C:/Program Files/gstreamer/1.0/msvc_x86_64/bin/gst-launch-1.0.exe"),
            Path("C:/Program Files/gstreamer/1.0/mingw_x86_64/bin/gst-launch-1.0.exe"),
        ])
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    @staticmethod
    def _find_ffmpeg_launcher() -> Optional[str]:
        found = shutil.which("ffmpeg")
        if found:
            return found

        candidates = []
        try:
            import config
            configured = str(getattr(config, "FFMPEG_BIN_DIR", "") or "").strip()
            if configured:
                candidates.append(Path(configured) / "ffmpeg.exe")
        except Exception:
            pass

        candidates.extend([
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files/FFmpeg/bin/ffmpeg.exe"),
        ])
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        winget_root = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
        try:
            matches = sorted(
                winget_root.glob("Gyan.FFmpeg_*/*/bin/ffmpeg.exe"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if matches:
                return str(matches[0])
        except Exception:
            pass
        return None

    @staticmethod
    def _preferred_udp_h264_decoder() -> str:
        try:
            import config
            decoder = str(getattr(config, "VIDEO_UDP_H264_DECODER", "auto") or "auto").strip().lower()
            if decoder in ("auto", "ffmpeg", "gstreamer"):
                return decoder
        except Exception:
            pass
        return "auto"

    @staticmethod
    def _udp_input_format() -> str:
        try:
            import config
            input_format = str(getattr(config, "VIDEO_UDP_INPUT_FORMAT", "auto") or "auto").strip().lower()
            if input_format in ("auto", "rtp", "rtp-jpeg", "mpegts", "raw-h264", "udp"):
                return input_format
        except Exception:
            pass
        return "auto"

    @staticmethod
    def _normalize_source(source):
        if source is None or source == "":
            return 0
        if isinstance(source, int):
            return source

        text = str(source).strip()
        lowered = text.lower()
        for prefix in ("webcam:", "camera:", "cam:"):
            if lowered.startswith(prefix):
                value = text.split(":", 1)[1].strip().lower()
                if value in ("", "auto", "default"):
                    return 0
                try:
                    return int(value)
                except ValueError:
                    return 0
        if lowered.isdigit():
            return int(lowered)
        return text

    @staticmethod
    def _is_udp_h264_source(source) -> bool:
        text = str(source or "").strip().lower()
        return text.startswith(("udp-h264://", "rtp-h264://"))

    @staticmethod
    def _udp_h264_port(source) -> int:
        text = str(source or "").strip()
        try:
            return int(text.rsplit(":", 1)[1].split("/", 1)[0])
        except Exception:
            return 5600

    @staticmethod
    def _configured_width() -> int:
        try:
            import config
            return int(getattr(config, "VIDEO_WIDTH", 640))
        except Exception:
            return 640

    @staticmethod
    def _configured_height() -> int:
        try:
            import config
            return int(getattr(config, "VIDEO_HEIGHT", 480))
        except Exception:
            return 480

    @staticmethod
    def _candidate_camera_indexes(first_index: int):
        indexes = [first_index, 0, 1, 2, 3]
        result = []
        for index in indexes:
            if index not in result:
                result.append(index)
        return result

    @staticmethod
    def _candidate_camera_backends():
        backends = []
        for name in ("CAP_DSHOW", "CAP_MSMF"):
            value = getattr(cv2, name, None)
            if value is not None:
                backends.append(value)
        backends.append(None)
        return backends

    @staticmethod
    def _is_file_source(source) -> bool:
        if isinstance(source, int):
            return False
        text = str(source or "").lower()
        return not text.startswith(("rtsp://", "rtmp://", "udp://", "http://", "https://"))

    def _generate_black_frame(self, message: str = "Camera not available"):
        black_frame = self._status_frame(message)
        while self.running:
            self.frame_ready.emit(black_frame)
            self.msleep(33)

    def _emit_status_frame(self, message: str):
        self.frame_ready.emit(self._status_frame(message))

    @staticmethod
    def _status_frame(message: str):
        black_frame = QImage(640, 480, QImage.Format_RGB888)
        black_frame.fill(0)
        painter = QPainter(black_frame)
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(black_frame.rect(), 0x84, message)
        painter.end()
        return black_frame

    def stop(self):
        self.running = False
        self._stop_gstreamer()
        self.wait()

    def set_video_source(self, source: Union[str, int]):
        self.video_source = source

    def _stop_gstreamer(self):
        if self.gst_process is None:
            return
        try:
            self.gst_process.terminate()
            self.gst_process.wait(timeout=1.0)
        except Exception:
            try:
                self.gst_process.kill()
            except Exception:
                pass
        self.gst_process = None
