"""
Main Window
Ana pencere - Tüm tab'ları ve worker thread'leri yönetir

MİMARİ:
- QMainWindow kullanır
- Tab widget ile sekmeleri gösterir
- Worker thread'leri başlatır ve yönetir
- Signal/slot bağlantılarını yapar
"""
from PyQt5.QtWidgets import QMainWindow, QTabWidget, QStatusBar, QWidget, QHBoxLayout, QMessageBox
from PyQt5.QtCore import Qt, QTimer
import json
import socket
import threading
import time
import subprocess
import sys
import urllib.request
from pathlib import Path
from ui.tabs.flight_tab import FlightTab
from ui.tabs.mission_tab import MissionTab
from ui.tabs.logs_tab import LogsTab
from ui.tabs.parameters_tab import ParametersTab
from ui.tabs.live_analysis_tab import AnalysisTab
from ui.widgets.side_navigation import SideNavigation
from core.telemetry_worker import TelemetryWorker
from core.video_worker import VideoWorker
from core.communication_core_worker import CommunicationCoreStatusWorker
from core.referee_video_stream import RefereeVideoStream
from core.mission_manager import MissionManager
from models.telemetry import TelemetryData
from models.defense_zone import DefenseZone
from core.app_logger import AppLogger
from core.shared_map_state import SharedMapState
from core.altitude_voice_announcer import AltitudeVoiceAnnouncer
import config

class MainWindow(QMainWindow):
    """
    Ana pencere sınıfı.
    
    Bu sınıf:
    1. Tüm tab'ları içerir
    2. Worker thread'leri yönetir
    3. Signal/slot bağlantılarını yapar
    4. Uygulama yaşam döngüsünü yönetir
    """
    
    def __init__(self):
        super().__init__()
        self.mission_manager = MissionManager()
        self.telemetry_worker = None
        self.video_worker = None
        self.referee_video_stream = None
        self.communication_core_worker = None
        self.communication_core_process = None
        self.shared_map_state = SharedMapState()
        self._telemetry_perf_last_report = time.time()
        self._telemetry_perf_count = 0
        self._last_referee_hss_signature = None
        self._last_referee_overlay_signature = None
        self._last_referee_telemetry_push = 0.0
        self._referee_telemetry_push_inflight = False
        self._referee_qr_display_enabled = False
        self._referee_hss_display_enabled = False
        self._telemetry_analysis_connected = False
        self._referee_analysis_connected = False
        
        print("SharedMapState class file:", SharedMapState.__module__)
        print("Has defense_zones:", hasattr(self.shared_map_state, "defense_zones"))
        
        self.init_ui()
        self.altitude_voice_announcer = AltitudeVoiceAnnouncer(
            logger=self.logger,
            enabled=bool(getattr(config, "ALTITUDE_VOICE_ENABLED", True)),
            parent=self,
        )
        self.init_workers()
        self.setup_connections()
        
        # Worker'ları başlat
        self.start_workers()
    
    def init_ui(self):
        """UI'yi oluştur"""
        self.logger = AppLogger()
        self.setWindowTitle("BLACK BOX Yer Kontrol İstasyonu - Teknofest SİHA")
        self.setMinimumSize(1200, 800)
        
        central = QWidget()
        central.setObjectName("appCentral")
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("mainTabs")
        self.tab_widget.tabBar().hide()
        central_layout.addWidget(self.tab_widget, 1)
        self.setCentralWidget(central)
        
        # Tab'ları oluştur
        self.flight_tab = FlightTab(mission_manager=self.mission_manager, shared_map_state=self.shared_map_state, logger=self.logger)
        self.tab_widget.addTab(self.flight_tab, "UÇUŞ EKRANI")
        
        self.mission_tab = MissionTab(mission_manager=self.mission_manager, shared_map_state=self.shared_map_state, logger=self.logger)
        self.tab_widget.addTab(self.mission_tab, "GÖREV EKRANI")
        
        # Başlangıç harita görünümü
        self.shared_map_state.set_view(38.32185, 38.43050, 14.0)

        # Not: Kamera görüntüsü Flight sekmesine entegre edildi.
        # Ayrı Camera sekmesi, demo/sunumda karışıklık yaratmamak için kaldırıldı.
        
        self.logs_tab = LogsTab(self.logger)
        self.tab_widget.addTab(self.logs_tab, "LOGS EKRANI")

        self.parameters_tab = ParametersTab(self.logger)
        self.tab_widget.addTab(self.parameters_tab, "PARAMETRE EKRANI")

        self.analysis_tab = AnalysisTab(
            self.logger,
            shared_map_state=self.shared_map_state,
            mission_manager=self.mission_manager,
        )
        self.tab_widget.addTab(self.analysis_tab, "ANALİZ EKRANI")

        self.side_navigation = SideNavigation(self.tab_widget, self.flight_tab.telemetry_readouts)
        central_layout.addWidget(self.side_navigation)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.setStyleSheet("""
            QWidget#appCentral {
                background-color: #090c0a;
            }
            QTabWidget#mainTabs::pane {
                border: none;
                background-color: #090c0a;
                top: 0px;
            }
        """)

    def init_workers(self):
        """Worker thread'lerini oluştur"""
        # Telemetry worker
        # Start truly disconnected. Serial/UDP/TCP only starts after the
        # operator explicitly presses Connect.
        self.telemetry_worker = TelemetryWorker(autostart_simulation=False)
        
        # Video worker (demo için None - varsayılan kamera kullanır)
        self.video_worker = VideoWorker(video_source=getattr(config, "VIDEO_SOURCE", "webcam:0"))
        self.referee_video_stream = RefereeVideoStream(
            port=int(getattr(config, "REFEREE_VIDEO_STREAM_PORT", 8092)),
            fps=float(getattr(config, "REFEREE_VIDEO_STREAM_FPS", 10)),
            jpeg_quality=int(getattr(config, "REFEREE_VIDEO_JPEG_QUALITY", 70)),
        )
        self.communication_core_worker = CommunicationCoreStatusWorker(poll_hz=1.0)
    
    def setup_connections(self):
        """Signal/slot bağlantılarını yap"""
        # Telemetry worker sinyalleri
        self.telemetry_worker.telemetry_received.connect(self._on_telemetry_received)
        self.telemetry_worker.connection_status_changed.connect(self._on_connection_status_changed)
        self.telemetry_worker.log_message.connect(self._on_worker_log)
        self.telemetry_worker.mission_downloaded.connect(self._on_mission_downloaded)
        self.telemetry_worker.fence_downloaded.connect(self._on_fence_downloaded)
        self.telemetry_worker.parameters_downloaded.connect(self._on_parameters_downloaded)
        self.telemetry_worker.parameters_download_failed.connect(self._on_parameters_download_failed)
        self.telemetry_worker.guided_target_completed.connect(self._on_guided_target_completed)
        self.telemetry_worker.guided_target_failed.connect(self._on_guided_target_failed)
        self.telemetry_worker.mode_change_completed.connect(self._on_mode_change_completed)
        self.telemetry_worker.mode_change_failed.connect(self._on_mode_change_failed)
        
        # Video worker sinyalleri
        self.video_worker.frame_ready.connect(self._on_video_frame)
        self.video_worker.video_finished.connect(self._on_video_finished)
        self.communication_core_worker.status_received.connect(self._on_communication_core_status)
        self.communication_core_worker.log_message.connect(self._on_worker_log)

        # Flight tab UI aksiyonları
        self.flight_tab.connect_requested.connect(self._on_connect_requested)
        self.flight_tab.disconnect_requested.connect(self._on_disconnect_requested)
        self.flight_tab.mode_change_requested.connect(self._on_mode_change_requested)
        self.flight_tab.task_mode_requested.connect(self._on_task_mode_requested)
        self.flight_tab.video_source_selected.connect(self._on_video_source_selected)
        self.flight_tab.referee_connect_requested.connect(self._on_referee_connect_requested)
        self.flight_tab.referee_disconnect_requested.connect(self._on_referee_disconnect_requested)
        self.flight_tab.referee_qr_fetch_requested.connect(self._on_referee_qr_fetch_requested)
        self.flight_tab.referee_hss_fetch_requested.connect(self._on_referee_hss_fetch_requested)
        self.flight_tab.guided_target_requested.connect(self._on_guided_target_requested)
        self.mission_tab.mission_upload_requested.connect(self._on_mission_upload_requested)
        self.mission_tab.mission_download_requested.connect(self._on_mission_download_requested)
        self.parameters_tab.refresh_requested.connect(self._on_parameters_refresh_requested)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
    
    def start_workers(self):
        """Worker thread'lerini başlat"""
        self.telemetry_worker.start()
        self.video_worker.start()
        self.logger.info("Workers started")
    
    def _on_telemetry_received(self, telemetry: TelemetryData):
        """Telemetri verisi geldiğinde"""
        # Flight tab'a gönder
        update_start = time.perf_counter()
        now = time.time()
        self._telemetry_perf_count += 1
        self.flight_tab.update_telemetry(telemetry)
        self.altitude_voice_announcer.update_altitude(telemetry.altitude)
        self.analysis_tab.update_own_telemetry(telemetry)
        self._maybe_push_referee_telemetry(telemetry)
        update_ms = (time.perf_counter() - update_start) * 1000.0
        data_age_ms = max(0.0, (time.time() - getattr(telemetry, "timestamp", time.time())) * 1000.0)
        elapsed = now - self._telemetry_perf_last_report
        if elapsed >= 1.0:
            ui_hz = self._telemetry_perf_count / max(0.001, elapsed)
            try:
                import config
                perf_debug = bool(getattr(config, "TELEMETRY_PERF_DEBUG", False))
            except Exception:
                perf_debug = False
            if perf_debug:
                self.logger.info(
                    f"PERF telemetry_ui={ui_hz:.1f}Hz update={update_ms:.1f}ms "
                    f"data_age={data_age_ms:.0f}ms"
                )
            self._telemetry_perf_last_report = now
            self._telemetry_perf_count = 0
        
        # Status bar'ı güncelle
        self.status_bar.showMessage(
            f"Alt: {telemetry.altitude:.1f}m | "
            f"GS: {telemetry.safe_ground_speed:.1f}m/s | "
            f"AS: {telemetry.safe_air_speed:.1f}m/s | "
            f"Battery: {telemetry.battery:.1f}% | "
            f"UI: {update_ms:.1f}ms | Data: {data_age_ms:.0f}ms"
        )
    
    def _on_connection_status_changed(self, connected: bool):
        """Bağlantı durumu değiştiğinde"""
        self.flight_tab.set_connection_status(connected)
        self.logs_tab.update_telemetry_status(connected)
        self.altitude_voice_announcer.set_connected(connected)
        self._telemetry_analysis_connected = bool(connected)
        self._sync_live_analysis_enabled()
        if connected:
            self.logger.success("Telemetry connected")
        else:
            self.logger.warning("Telemetry disconnected")
    
    def _on_video_frame(self, image):
        """Video frame geldiğinde"""
        # Flight tab'a gönder (kamera Flight ekranında)
        self.flight_tab.update_video_frame(image)
        if self.referee_video_stream:
            self.referee_video_stream.update_frame(image)
        
        # Video durumunu güncelle (ilk frame geldiğinde)
        self.logs_tab.update_video_status(True)

    def _on_connect_requested(self, conn_cfg: dict):
        """Uçuş ekranından bağlantı isteği geldiğinde"""
        self.telemetry_worker.connect_backend(conn_cfg)
        self.logger.info(f"Connect requested: {conn_cfg}")

    def _on_disconnect_requested(self):
        """Uçuş ekranından bağlantı kes isteği"""
        self.telemetry_worker.disconnect_backend()
        self.logger.warning("Disconnect requested")

    def _on_worker_log(self, level: str, message: str):
        self.logger.log(level, message)

    def _on_mode_change_requested(self, mode_name: str):
        """Uçuş mod değişimi isteği"""
        self.logger.info(f"Mode change requested: {mode_name}")
        self.telemetry_worker.request_mode_change(mode_name)

    def _on_mode_change_completed(self, payload: dict):
        mode = str((payload or {}).get("mode") or "").upper()
        self.flight_tab.set_mode_change_result(mode, True)
        self.logger.success(f"Pixhawk aktif uçuş modu: {mode}")

    def _on_mode_change_failed(self, message: str):
        self.flight_tab.set_mode_change_result("", False)
        QMessageBox.critical(self, "Uçuş Modu Hatası", message)

    def _on_guided_target_requested(self, latitude: float, longitude: float, altitude: float):
        self.logger.info(
            f"Guided hedef istendi: {latitude:.7f}, {longitude:.7f}, {altitude:.1f} m"
        )
        self.telemetry_worker.request_guided_target(latitude, longitude, altitude)

    def _on_guided_target_completed(self, payload: dict):
        self.flight_tab.set_guided_target_result(payload, True)
        self.flight_tab.set_active_mode("GUIDED")
        self.logger.success("GUIDED hedef Pixhawk'a gönderildi")

    def _on_guided_target_failed(self, message: str):
        self.flight_tab.set_guided_target_result({}, False)
        QMessageBox.critical(self, "GUIDED Hedef Hatası", message)

    def _on_task_mode_requested(self, task_name: str):
        command_type = self._task_command_type(task_name)
        payload = {
            "type": command_type,
            "payload": {
                "task": command_type,
                "label": task_name,
                "active": command_type != "TASK_CANCEL",
                "timestamp_ms": int(time.time() * 1000),
            },
        }

        if self._send_vehicle_task_command(payload):
            self.logger.success(f"Gorev modu aktif: {task_name}")
        else:
            self.logger.error(f"Gorev modu komutu gonderilemedi: {task_name}")

    @staticmethod
    def _task_command_type(task_name: str) -> str:
        import unicodedata
        normalized = unicodedata.normalize("NFKD", str(task_name or "").casefold())
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        if "kamikaze" in normalized:
            return "KAMIKAZE_MODE"
        if "takip" in normalized:
            return "FOLLOW_MODE"
        if "iptal" in normalized:
            return "TASK_CANCEL"
        if "otonom" in normalized:
            return "AUTONOMOUS_LAND"
        if "savunma" in normalized:
            return "HSS_ESCAPE"
        return "TASK_MODE"

    def _send_vehicle_task_command(self, payload: dict) -> bool:
        host, port = self._vehicle_command_target()
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sent = sock.sendto(data, (host, port))
            self.logger.info(f"Vehicle task command -> {host}:{port} {payload.get('type')}")
            return sent == len(data)
        except Exception as exc:
            self.logger.error(f"Vehicle task command failed: {exc}")
            return False

    def _vehicle_command_target(self):
        host = "192.168.1.11"
        port = 9102
        config_path = Path(__file__).resolve().parents[1] / "communication_core" / "config" / "config.yaml"
        try:
            import yaml
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            vehicle_cfg = data.get("vehicle_manager", {}) or {}
            host = str(vehicle_cfg.get("vehicle_command_host", host)).strip() or host
            port = int(vehicle_cfg.get("vehicle_command_port", port))
        except Exception as exc:
            self.logger.warning(f"Vehicle command config okunamadi, varsayilan hedef kullaniliyor: {exc}")
        return host, port

    def _on_referee_connect_requested(self, cfg: dict):
        try:
            self._referee_qr_display_enabled = False
            self._referee_hss_display_enabled = False
            self._clear_referee_hss_zones()
            self._write_communication_core_config(cfg)
            self.communication_core_worker.set_referee_base_url(
                self._referee_base_url_from_cfg(cfg)
            )
            self._restart_communication_core()
            if self._communication_core_health_ok():
                self._referee_analysis_connected = True
                self._sync_live_analysis_enabled()
                self.flight_tab.set_referee_status(True, "Connected")
                self._start_communication_core_status_worker()
                self._start_referee_video_stream(cfg)
                self.logger.success("Hakem sunucu servisi baglandi")
            else:
                self.flight_tab.set_referee_status(False, "Baglanti yok")
                self.logger.error("Hakem sunucu servisi health check vermedi")
        except Exception as exc:
            self.flight_tab.set_referee_status(False, "Baglanti hatasi")
            self.logger.error(f"Hakem sunucu baglanti hatasi: {exc}")

    def _on_referee_disconnect_requested(self):
        self._referee_analysis_connected = False
        self._sync_live_analysis_enabled()
        self._stop_communication_core_status_worker()
        if self.communication_core_worker is not None:
            self.communication_core_worker.set_referee_base_url("")
        self._stop_referee_video_stream()
        self._stop_communication_core()
        self._last_referee_telemetry_push = 0.0
        self._referee_telemetry_push_inflight = False
        self._referee_qr_display_enabled = False
        self._referee_hss_display_enabled = False
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.clear_referee_telemetry()
        self.flight_tab.set_referee_status(False, "Disconnected")
        self.logger.warning("Hakem sunucu servisi durduruldu")

    def _sync_live_analysis_enabled(self):
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.set_vehicle_analysis_enabled(
                self._telemetry_analysis_connected or self._referee_analysis_connected
            )

    def _start_referee_video_stream(self, cfg: dict):
        if not self.referee_video_stream:
            return
        try:
            self.referee_video_stream.start()
            base_url = self._referee_base_url_from_cfg(cfg)
            stream_url = self.referee_video_stream.stream_url(cfg.get("ip", ""))
            self.referee_video_stream.register_stream_url(
                base_url,
                stream_url,
                team_number=self._referee_team_number_from_cfg(cfg),
            )
            self.referee_video_stream.start_upload(
                base_url,
                path=str(getattr(config, "REFEREE_VIDEO_UPLOAD_PATH", "/api/kamera_gonder")),
            )
            self.logger.success(f"Kamera hakem yayini aktif: {stream_url}")
        except Exception as exc:
            self.logger.error(f"Kamera hakem yayini baslatilamadi: {exc}")

    def _stop_referee_video_stream(self):
        if self.referee_video_stream:
            self.referee_video_stream.stop_upload()

    @staticmethod
    def _referee_base_url_from_cfg(cfg: dict) -> str:
        ip = str(cfg.get("ip", "")).strip()
        port = str(cfg.get("port", "")).strip()
        return ip if ip.startswith(("http://", "https://")) else f"http://{ip}:{port}"

    @staticmethod
    def _referee_team_number_from_cfg(cfg: dict) -> int:
        try:
            return int(str(cfg.get("team", "1")).strip())
        except Exception:
            return 1

    def _clear_referee_hss_zones(self):
        zones = [
            zone for zone in getattr(self.shared_map_state, "defense_zones", [])
            if not str(getattr(zone, "name", "")).startswith("Hakem HSS")
        ]
        if len(zones) == len(getattr(self.shared_map_state, "defense_zones", [])):
            return
        self.shared_map_state.defense_zones = zones
        self.shared_map_state.save_defense_zones()
        self.shared_map_state.overlay_changed.emit()

    def _on_referee_qr_fetch_requested(self):
        self._post_communication_core_command(
            "http://127.0.0.1:8090/vehicle/send_qr",
            "QR koordinatlari cekildi",
            "QR koordinatlari cekilemedi",
            on_success=lambda: setattr(self, "_referee_qr_display_enabled", True),
        )

    def _on_referee_hss_fetch_requested(self):
        self._post_communication_core_command(
            "http://127.0.0.1:8090/vehicle/send_hss",
            "Hava savunma koordinatlari cekildi",
            "Hava savunma koordinatlari cekilemedi",
            on_success=lambda: setattr(self, "_referee_hss_display_enabled", True),
        )

    def _post_communication_core_command(self, url: str, success_message: str, error_message: str, on_success=None):
        def worker():
            try:
                req = urllib.request.Request(url, data=b"{}", method="POST")
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=2.0) as response:
                    ok = 200 <= response.status < 300
                if ok:
                    if on_success is not None:
                        on_success()
                    self.logger.success(success_message)
                else:
                    self.logger.error(f"{error_message}: HTTP {response.status}")
            except Exception as exc:
                self.logger.error(f"{error_message}: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _maybe_push_referee_telemetry(self, telemetry: TelemetryData):
        if self.communication_core_worker is None or not self.communication_core_worker.isRunning():
            return
        if self._referee_telemetry_push_inflight:
            return
        now = time.time()
        if now - self._last_referee_telemetry_push < 1.0:
            return

        lat = getattr(telemetry, "latitude", None)
        lon = getattr(telemetry, "longitude", None)
        if lat is None or lon is None:
            return

        self._last_referee_telemetry_push = now
        self._referee_telemetry_push_inflight = True
        payload = self._telemetry_to_communication_core_state(telemetry)

        def worker():
            try:
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request("http://127.0.0.1:8090/vehicle/state", data=body, method="POST")
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=0.8) as response:
                    if response.status < 200 or response.status >= 300:
                        self.logger.warning(f"Hakem telemetri state aktarimi HTTP {response.status}")
            except Exception as exc:
                self.logger.warning(f"Hakem telemetri state aktarimi basarisiz: {exc}")
            finally:
                self._referee_telemetry_push_inflight = False

        threading.Thread(target=worker, daemon=True).start()

    def _telemetry_to_communication_core_state(self, telemetry: TelemetryData) -> dict:
        local_time = time.gmtime(getattr(telemetry, "timestamp", time.time()))
        gps_time = {
            "saat": local_time.tm_hour,
            "dakika": local_time.tm_min,
            "saniye": local_time.tm_sec,
            "milisaniye": int((getattr(telemetry, "timestamp", time.time()) % 1.0) * 1000),
        }
        return {
            "latitude": float(getattr(telemetry, "latitude", 0.0) or 0.0),
            "longitude": float(getattr(telemetry, "longitude", 0.0) or 0.0),
            "altitude": float(getattr(telemetry, "altitude", 0.0) or 0.0),
            "pitch": float(getattr(telemetry, "safe_pitch", 0.0) or 0.0),
            "yaw": float(getattr(telemetry, "safe_yaw", 0.0) or 0.0),
            "roll": float(getattr(telemetry, "safe_roll", 0.0) or 0.0),
            "ground_speed": float(getattr(telemetry, "speed", 0.0) or 0.0),
            "battery_percent": int(max(0, min(100, round(float(getattr(telemetry, "battery", 0.0) or 0.0))))),
            "autonomous_mode": str(getattr(telemetry, "mode", "") or "").upper() in {"AUTO", "GUIDED", "RTL"},
            "lock_active": False,
            "target_center_x": 0,
            "target_center_y": 0,
            "target_width": 0,
            "target_height": 0,
            "gps_time": gps_time,
        }

    def _start_communication_core_status_worker(self):
        if self.communication_core_worker is None:
            self.communication_core_worker = CommunicationCoreStatusWorker(poll_hz=1.0)
            self.communication_core_worker.status_received.connect(self._on_communication_core_status)
            self.communication_core_worker.log_message.connect(self._on_worker_log)
        if not self.communication_core_worker.isRunning():
            self.communication_core_worker.start()

    def _stop_communication_core_status_worker(self):
        if self.communication_core_worker:
            self.communication_core_worker.stop()

    def _on_communication_core_status(self, status: dict):
        self.flight_tab.update_referee_teams(status)
        self._update_referee_server_time(status.get("server_time"))
        self._apply_referee_map_overlays(status)
        self._apply_referee_hss_zones(status.get("hss_coordinates") or [])
        if hasattr(self, "analysis_tab"):
            # Forward the complete payload: the referee API has used several
            # wrapper names over time and the analysis normalizer understands
            # all of them without imposing an aircraft-count limit.
            self.analysis_tab.update_referee_telemetry(status)

    def _update_referee_server_time(self, server_time):
        if not server_time:
            return
        text = self._format_server_time(server_time)
        if hasattr(self.flight_tab, "set_referee_server_time"):
            self.flight_tab.set_referee_server_time(text)

    @staticmethod
    def _format_server_time(server_time) -> str:
        try:
            hour = int(server_time.get("saat", 0))
            minute = int(server_time.get("dakika", 0))
            second = int(server_time.get("saniye", 0))
            millisecond = int(server_time.get("milisaniye", 0))
            return f"{hour:02d}:{minute:02d}:{second:02d}.{millisecond:03d}"
        except Exception:
            return str(server_time)

    def _apply_referee_map_overlays(self, status: dict):
        markers = []

        aircraft_lat = getattr(self.shared_map_state, "aircraft_lat", None)
        aircraft_lon = getattr(self.shared_map_state, "aircraft_lon", None)
        if aircraft_lat is not None and aircraft_lon is not None:
            markers.append({
                "type": "aircraft",
                "lat": aircraft_lat,
                "lon": aircraft_lon,
                "heading": getattr(self.shared_map_state, "aircraft_heading", 0.0),
                "label": "UAV",
            })

        qr = status.get("qr_coordinate") if self._referee_qr_display_enabled else None
        if isinstance(qr, dict):
            lat = self._first_number(qr, ["qrEnlem", "qr_enlem", "lat", "latitude", "enlem"])
            lon = self._first_number(qr, ["qrBoylam", "qr_boylam", "lon", "lng", "longitude", "boylam"])
            if lat is not None and lon is not None:
                markers.append({"type": "qr", "lat": lat, "lon": lon, "label": "QR"})

        for index, opponent in enumerate(self._as_list(status.get("opponent_positions"))):
            if not isinstance(opponent, dict):
                continue
            lat = self._first_number(opponent, ["iha_enlem", "ihaEnlem", "enlem", "lat", "latitude"])
            lon = self._first_number(opponent, ["iha_boylam", "ihaBoylam", "boylam", "lon", "lng", "longitude"])
            if lat is None or lon is None:
                continue
            team = opponent.get("takim_numarasi", opponent.get("takimNumarasi", opponent.get("takimNo", opponent.get("id", index + 1))))
            heading = self._first_number(opponent, ["iha_yonelme", "ihaYonelme", "heading", "yaw"], 0.0)
            markers.append({
                "type": "enemy",
                "lat": lat,
                "lon": lon,
                "heading": heading,
                "label": f"Rakip {team}",
            })

        signature = self._marker_signature(markers)
        if signature != self._last_referee_overlay_signature:
            self._last_referee_overlay_signature = signature
            self.shared_map_state.set_overlay_markers(markers)

    def _apply_referee_hss_zones(self, hss_items):
        if not self._referee_hss_display_enabled:
            return
        hss_items = self._as_list(hss_items)

        zones = []
        for index, item in enumerate(hss_items):
            if not isinstance(item, dict):
                continue
            lat = self._first_number(item, ["hssEnlem", "hss_enlem", "lat", "latitude", "enlem"])
            lon = self._first_number(item, ["hssBoylam", "hss_boylam", "lon", "lng", "longitude", "boylam"])
            radius = self._first_number(item, ["hssYaricap", "hss_yaricap", "radius", "radius_m", "yaricap"], 0.0)
            if lat is None or lon is None or radius is None or radius <= 0:
                continue
            zone_id = item.get("id", index + 1)
            zones.append(DefenseZone(
                center_lat=lat,
                center_lon=lon,
                radius_m=radius,
                name=f"Hakem HSS {zone_id}",
                is_active=True,
                color=(255, 45, 45, 80),
            ))

        signature = tuple((round(z.center_lat, 7), round(z.center_lon, 7), round(z.radius_m, 2), z.name) for z in zones)
        if signature == self._last_referee_hss_signature:
            return
        self._last_referee_hss_signature = signature

        self.shared_map_state.defense_zones = zones
        self.shared_map_state.save_defense_zones()
        self.shared_map_state.overlay_changed.emit()
        if hasattr(self.mission_tab, "_refresh_fence_table"):
            self.mission_tab._refresh_fence_table()

    @staticmethod
    def _as_list(value):
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            if all(isinstance(v, dict) for v in value.values()):
                return list(value.values())
            return [value]
        return []

    @staticmethod
    def _first_number(data: dict, keys: list, default=None):
        for key in keys:
            if key in data and data.get(key) is not None:
                try:
                    return float(data.get(key))
                except (TypeError, ValueError):
                    continue
        return default

    @staticmethod
    def _marker_signature(markers):
        signature = []
        for marker in markers:
            signature.append((
                marker.get("type"),
                round(float(marker.get("lat", 0.0)), 7),
                round(float(marker.get("lon", 0.0)), 7),
                round(float(marker.get("heading", 0.0)), 1),
                marker.get("label", ""),
            ))
        return tuple(signature)

    def _write_communication_core_config(self, cfg: dict):
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("PyYAML gerekli. Kurulum: python -m pip install pyyaml") from exc

        root = Path(__file__).resolve().parents[1]
        config_path = root / "communication_core" / "config" / "config.yaml"
        if not config_path.exists():
            raise RuntimeError(f"communication_core config bulunamadi: {config_path}")

        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        server = data.setdefault("server", {})
        team_cfg = data.setdefault("team", {})

        ip = str(cfg.get("ip", "")).strip()
        port = str(cfg.get("port", "")).strip()
        base_url = ip if ip.startswith(("http://", "https://")) else f"http://{ip}:{port}"
        server["base_url"] = base_url
        server["username"] = str(cfg.get("team", "")).strip()
        server["password"] = str(cfg.get("password", "")).strip()
        try:
            team_cfg["team_number"] = int(str(cfg.get("team", "1")).strip())
        except ValueError:
            team_cfg["team_number"] = 1

        config_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        self.logger.info(f"communication_core config updated: {base_url}")

    def _restart_communication_core(self):
        self._stop_communication_core()
        root = Path(__file__).resolve().parents[1]
        exe = root / "communication_core" / "build_nmake" / "communication_core_service.exe"
        cfg = root / "communication_core" / "config" / "config.yaml"
        log_dir = root / "communication_core" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        if not exe.exists():
            raise RuntimeError(f"communication_core_service.exe bulunamadi: {exe}")

        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
        stdout = open(log_dir / "service.stdout.log", "a", encoding="utf-8")
        stderr = open(log_dir / "service.stderr.log", "a", encoding="utf-8")
        self.communication_core_process = subprocess.Popen(
            [str(exe), str(cfg)],
            cwd=str(root / "communication_core"),
            stdout=stdout,
            stderr=stderr,
            creationflags=creationflags,
        )
        time.sleep(1.5)
        if self.communication_core_process.poll() is not None:
            raise RuntimeError("communication_core servisi baslamadan kapandi")

    def _stop_communication_core(self):
        if sys.platform.startswith("win"):
            subprocess.run(
                ["taskkill", "/F", "/IM", "communication_core_service.exe", "/T"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        elif self.communication_core_process is not None:
            self.communication_core_process.terminate()
        self.communication_core_process = None

    @staticmethod
    def _communication_core_health_ok() -> bool:
        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8090/healthz", timeout=1.0) as response:
                    return response.status == 200
            except Exception:
                time.sleep(0.3)
        return False

    def _on_mission_upload_requested(self, mission_items: list, fence_zones: list):
        self.logger.info(
            f"Mission upload requested: {len(mission_items)} items, {len(fence_zones)} fence zones"
        )
        self.telemetry_worker.upload_mission(mission_items, fence_zones)

    def _on_mission_download_requested(self):
        self.logger.info("Mission download requested")
        self.telemetry_worker.download_mission()

    def _on_parameters_refresh_requested(self):
        self.logger.info("Parameter download requested")
        self.telemetry_worker.download_parameters()

    def _on_tab_changed(self, index: int):
        if self.tab_widget.widget(index) is getattr(self, "analysis_tab", None):
            self.analysis_tab.activate()

    def _on_parameters_downloaded(self, parameters):
        self.parameters_tab.set_parameters(parameters)
        self.logger.success(f"Parameters loaded from Pixhawk: {len(parameters or [])} items")

    def _on_parameters_download_failed(self, message: str):
        self.parameters_tab.set_loading(False)
        self.logger.error(f"Parameter download failed: {message}")

    def _on_mission_downloaded(self, mission_items):
        self.mission_manager.replace_items(list(mission_items or []))
        self.mission_tab.fit_mission_on_map()
        self.logger.success(f"Mission loaded from Pixhawk: {len(mission_items or [])} items")

    def _on_fence_downloaded(self, fence_zones):
        if hasattr(self.shared_map_state, "clear_defense_zones"):
            self.shared_map_state.clear_defense_zones()
            for zone in list(fence_zones or []):
                self.shared_map_state.add_defense_zone(zone)
        if hasattr(self.mission_tab, "_refresh_fence_table"):
            self.mission_tab._refresh_fence_table()
        self.logger.success(f"Fence loaded from Pixhawk: {len(fence_zones or [])} zones")

    def _on_video_source_selected(self, source: str):
        """Video kaynağı değiştirildi (dosya seçimi)"""
        # Basit yaklaşım: video worker'ı yeniden başlat.
        try:
            self.logger.info(f"Video source requested: {source}")
            if self.video_worker:
                self.video_worker.stop()
            self.video_worker = VideoWorker(video_source=source)
            self.video_worker.frame_ready.connect(self._on_video_frame)
            self.video_worker.video_finished.connect(self._on_video_finished)
            self.video_worker.start()
            self.logger.success(f"Video source set: {source}")
        except Exception as e:
            self.logger.error(f"Failed to set video source: {e}")
    
    def _on_video_finished(self):
        """Video bittiğinde"""
        self.logger.info("Video stream finished")
    
    def closeEvent(self, event):
        """Pencere kapatıldığında"""
        # Worker thread'lerini durdur
        if self.telemetry_worker:
            self.telemetry_worker.stop()
        if self.video_worker:
            self.video_worker.stop()
        if self.referee_video_stream:
            self.referee_video_stream.stop()
        if hasattr(self, "analysis_tab") and self.analysis_tab:
            self.analysis_tab.stop()
        if hasattr(self, "altitude_voice_announcer"):
            self.altitude_voice_announcer.stop()
        self._stop_communication_core_status_worker()
        self._stop_communication_core()
        
        self.logger.info("Ground Station shutting down")
        event.accept()
