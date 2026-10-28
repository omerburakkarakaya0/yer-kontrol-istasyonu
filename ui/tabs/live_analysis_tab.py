from __future__ import annotations

import time
import webbrowser
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtWidgets import (
    QLabel,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from core.uavlogviewer_server import UAVLogViewerServer
from ui.tabs.analysis_tab import (
    LogViewerPage,
    OpponentAnalysisWidget,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineView,
)


class AnalysisTab(QWidget):
    """Stable dual-page analysis surface for logs and live 3D traffic."""

    def __init__(self, logger=None, shared_map_state=None, mission_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.shared_map_state = shared_map_state
        self.mission_manager = mission_manager
        self.viewer_server: UAVLogViewerServer | None = None
        self.web_view: QWebEngineView | None = None
        self.opponent_web_view: QWebEngineView | None = None
        self.web_profile = None
        self.opponent_widget: OpponentAnalysisWidget | None = None
        self.placeholder: QLabel | None = None
        self.opponent_placeholder: QLabel | None = None
        self.started = False
        self.viewer_url = ""
        self.current_mode = "opponents"
        self._own_log_loaded = False
        self._opponent_view_loaded = False
        self._health_retry_count = 0
        self._analysis_sync_pending = False
        self._vehicle_analysis_enabled = False
        self._own_track_started_at = time.monotonic()
        self._own_track = []
        self._last_own_signature = None
        self._init_ui()

        if self.mission_manager is not None:
            self.mission_manager.mission_changed.connect(self._schedule_analysis_sync)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setStyleSheet("background-color: #090c0a;")

        toolbar = QFrame()
        toolbar.setStyleSheet(
            "QFrame { background-color: #141d16; border-bottom: 1px solid #2c3b2e; }"
            "QPushButton { background-color: #1b2a1e; color: #f0f3eb; border: 1px solid #2c3b2e; "
            "border-radius: 4px; padding: 7px 12px; }"
            "QPushButton:checked { background-color: #124020; border-color: #7ea783; }"
        )
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 7, 8, 7)
        toolbar_layout.setSpacing(8)

        self.own_log_button = QPushButton("Bizim Ucus Logu")
        self.own_log_button.setCheckable(True)
        self.opponent_button = QPushButton("Rakip SIHA Analizi")
        self.opponent_button.setCheckable(True)
        self.opponent_button.setChecked(True)
        self.own_log_button.clicked.connect(lambda: self._set_mode("own"))
        self.opponent_button.clicked.connect(lambda: self._set_mode("opponents"))
        toolbar_layout.addWidget(self.own_log_button)
        toolbar_layout.addWidget(self.opponent_button)
        toolbar_layout.addStretch(1)
        main_layout.addWidget(toolbar)

        self.stack = QStackedLayout()
        main_layout.addLayout(self.stack)

        # Complete 2D fallback for systems without QtWebEngine/WebGL.
        self.opponent_widget = OpponentAnalysisWidget(self.logger)
        self.stack.addWidget(self.opponent_widget)
        self.stack.setCurrentWidget(self.opponent_widget)

        if QWebEngineView is None:
            return

        self.placeholder = self._loading_label("Ucus logu yukleniyor...")
        self.opponent_placeholder = self._loading_label("3B rakip SIHA analizi yukleniyor...")
        self.stack.addWidget(self.placeholder)
        self.stack.addWidget(self.opponent_placeholder)
        self.stack.setCurrentWidget(self.opponent_placeholder)

    @staticmethod
    def _loading_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 16px; color: #7ea783; background-color: #090c0a;")
        return label

    def activate(self):
        if QWebEngineView is None:
            if self.opponent_widget is not None:
                self.stack.setCurrentWidget(self.opponent_widget)
            return
        if not self.started:
            self.started = True
            self._create_web_views()
            self._start_viewer()
        self._show_current_mode()
        self._refresh_if_visible()

    def _create_web_views(self):
        if QWebEngineProfile is not None:
            self.web_profile = QWebEngineProfile(self)
            self.web_profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
            self.web_profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
            try:
                self.web_profile.clearHttpCache()
            except Exception:
                pass

        self.web_view = self._new_web_view(self._on_log_load_finished)
        self.opponent_web_view = self._new_web_view(self._on_opponent_load_finished)
        self.stack.addWidget(self.web_view)
        self.stack.addWidget(self.opponent_web_view)

    def _new_web_view(self, load_callback):
        view = QWebEngineView()
        view.setStyleSheet("background-color: #090c0a;")
        if QWebEnginePage is not None:
            if self.web_profile is not None:
                view.setPage(LogViewerPage(self.logger, self.web_profile, view))
            else:
                view.setPage(LogViewerPage(self.logger, parent=view))
        view.loadFinished.connect(load_callback)
        self._enable_webgl_settings(view)
        return view

    @staticmethod
    def _enable_webgl_settings(view):
        if QWebEngineSettings is None or view is None:
            return
        settings = view.settings()
        for name in (
            "JavascriptEnabled",
            "JavascriptCanOpenWindows",
            "LocalStorageEnabled",
            "WebGLEnabled",
            "Accelerated2dCanvasEnabled",
            "PluginsEnabled",
            "ErrorPageEnabled",
            "LocalContentCanAccessRemoteUrls",
            "LocalContentCanAccessFileUrls",
        ):
            attribute = getattr(QWebEngineSettings, name, None)
            if attribute is not None:
                settings.setAttribute(attribute, True)

    def _set_mode(self, mode: str):
        self.current_mode = mode
        self.own_log_button.setChecked(mode == "own")
        self.opponent_button.setChecked(mode == "opponents")
        self.activate()
        self._show_current_mode()

    def _show_current_mode(self):
        if self.current_mode == "own":
            target = self.web_view if self._own_log_loaded and self.web_view is not None else self.placeholder
        elif self.opponent_web_view is not None:
            target = self.opponent_web_view if self._opponent_view_loaded else self.opponent_placeholder
        else:
            target = self.opponent_widget
        if target is not None:
            self.stack.setCurrentWidget(target)

    def showEvent(self, event):
        super().showEvent(event)
        self.activate()

    def _refresh_if_visible(self):
        if not self.isVisible():
            return
        view = self.web_view if self.current_mode == "own" else self.opponent_web_view
        if view is None:
            return
        # Retain both pages and only notify them about their new viewport size.
        # Reloading here previously reset the sidebar and caused black flashes.
        QTimer.singleShot(
            50,
            lambda: view.page().runJavaScript("window.dispatchEvent(new Event('resize')); true"),
        )

    def _start_viewer(self):
        root = Path(__file__).resolve().parents[2]
        dist_dir = root / "third_party" / "uavlogviewer" / "dist"
        try:
            self.viewer_server = UAVLogViewerServer(dist_dir)
            self.viewer_server.start()
            self.viewer_url = self.viewer_server.url.replace("/#/", "/?embedded=1&v=offline-uavlogviewer-9#/")
            self._flush_analysis_payload()
            QTimer.singleShot(
                100,
                lambda: self.web_view is not None and self.web_view.setUrl(QUrl(self.viewer_url)),
            )
            QTimer.singleShot(
                100,
                lambda: self.opponent_web_view is not None
                and self.opponent_web_view.setUrl(QUrl(self._opponent_viewer_url())),
            )
            if self.logger:
                self.logger.success(f"Offline analiz goruntuleyicileri baslatildi: {self.viewer_server.url}")
        except Exception as exc:
            if self.logger:
                self.logger.error(f"Offline analiz goruntuleyicisi baslatilamadi: {exc}")
            self._show_start_error(str(exc))

    def _opponent_viewer_url(self) -> str:
        if self.viewer_server is None:
            return ""
        return self.viewer_server.url.replace("/#/", "/?embedded=1&v=offline-opponents-5#/opponents")

    def update_referee_telemetry(self, telemetry_items):
        if self.opponent_widget is not None:
            self.opponent_widget.update_from_referee_telemetry(telemetry_items)
        self._schedule_analysis_sync()

    def set_vehicle_analysis_enabled(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self._vehicle_analysis_enabled:
            return
        self._vehicle_analysis_enabled = enabled
        self._own_track.clear()
        self._last_own_signature = None
        self._own_track_started_at = time.monotonic()
        self._schedule_analysis_sync()

    def update_own_telemetry(self, telemetry):
        if not self._vehicle_analysis_enabled:
            return
        lat = getattr(telemetry, "latitude", None)
        lon = getattr(telemetry, "longitude", None)
        if lat is None or lon is None:
            return
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return
        if lat == 0.0 and lon == 0.0:
            return
        sample = {
            "timestamp": time.monotonic() - self._own_track_started_at,
            "latitude": lat,
            "longitude": lon,
            "altitude": float(getattr(telemetry, "altitude", 0.0) or 0.0),
            "speed": float(getattr(telemetry, "speed", 0.0) or 0.0),
            "heading": float(getattr(telemetry, "safe_yaw", 0.0) or 0.0),
            "pitch": float(getattr(telemetry, "safe_pitch", 0.0) or 0.0),
            "roll": float(getattr(telemetry, "safe_roll", 0.0) or 0.0),
            "battery": float(getattr(telemetry, "battery", 0.0) or 0.0),
        }
        signature = tuple(round(sample[key], 6) for key in ("latitude", "longitude", "altitude", "heading"))
        if signature == self._last_own_signature:
            return
        self._last_own_signature = signature
        self._own_track.append(sample)
        if len(self._own_track) > 5000:
            del self._own_track[:-5000]
        self._schedule_analysis_sync()

    def clear_referee_telemetry(self):
        if self.opponent_widget is not None:
            self.opponent_widget.clear_referee_telemetry()
        self._schedule_analysis_sync()

    def _schedule_analysis_sync(self):
        if self._analysis_sync_pending:
            return
        self._analysis_sync_pending = True
        QTimer.singleShot(100, self._flush_analysis_payload)

    def _flush_analysis_payload(self):
        self._analysis_sync_pending = False
        if self.viewer_server is None:
            return
        self.viewer_server.set_analysis_payload(self._build_analysis_payload())

    def _build_analysis_payload(self):
        if not self._vehicle_analysis_enabled:
            return {
                "analysis_active": False,
                "opponents": [],
                "mission": [],
                "ownship": None,
            }
        opponents = self.opponent_widget.analysis_payload() if self.opponent_widget is not None else []
        ownship = None
        if self._own_track:
            ownship = {
                "id": "bizim-siha",
                "callsign": "Bizim SIHA",
                "team": "Bizim Takim",
                "color": "#ffd447",
                "telemetry": list(self._own_track),
            }
        return {
            "analysis_active": True,
            "opponents": opponents,
            "mission": self._mission_payload(),
            "ownship": ownship,
        }

    def _mission_payload(self):
        if self.mission_manager is None:
            return []
        result = []
        for item in self.mission_manager.get_map_items():
            try:
                result.append({
                    "sequence": int(item.sequence),
                    "type": str(item.item_type),
                    "latitude": float(item.latitude),
                    "longitude": float(item.longitude),
                    "altitude": float(item.altitude or 0.0),
                    "speed": float(item.speed or 10.0),
                })
            except (TypeError, ValueError):
                continue
        return result

    def _on_log_load_finished(self, ok: bool):
        if ok and self.web_view is not None:
            self._own_log_loaded = True
            self.web_view.page().runJavaScript("document.title = 'Ucus Logu'; true")
            self._show_current_mode()
            QTimer.singleShot(500, self._check_log_health)
            return
        if self.logger and self.web_view is not None:
            self.logger.warning(f"Ucus logu sayfa yukleme uyarisi: {self.web_view.url().toString()}")

    def _on_opponent_load_finished(self, ok: bool):
        if ok:
            self._opponent_view_loaded = True
            self._show_current_mode()
            self._refresh_if_visible()
        elif self.logger and self.opponent_web_view is not None:
            self.logger.warning(f"3B analiz sayfa yukleme uyarisi: {self.opponent_web_view.url().toString()}")

    def _check_log_health(self):
        if self.web_view is None:
            return
        script = """
            (() => {
                const app = document.getElementById('app');
                return { hasApp: !!app, appLength: app ? app.innerHTML.length : 0 };
            })()
        """
        self.web_view.page().runJavaScript(script, self._on_log_health_result)

    def _on_log_health_result(self, result):
        if isinstance(result, dict) and result.get("hasApp") and result.get("appLength", 0) > 100:
            return
        if self.logger:
            self.logger.warning(f"Ucus logu health check bos gorundu: {result}")
        if self._health_retry_count == 0 and self.web_view is not None and self.viewer_url:
            self._health_retry_count += 1
            QTimer.singleShot(300, lambda: self.web_view.setUrl(QUrl(self.viewer_url)))

    def _show_start_error(self, message: str):
        fallback = QWidget()
        layout = QVBoxLayout(fallback)
        label = QLabel(f"Offline analiz goruntuleyicisi baslatilamadi.\n{message}")
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 15px; color: #fbbc05;")
        layout.addWidget(label)
        button = QPushButton("Ucus Logunu Online Ac")
        button.clicked.connect(lambda: webbrowser.open("https://plot.ardupilot.org/#/"))
        layout.addWidget(button)
        self.stack.addWidget(fallback)
        self.stack.setCurrentWidget(fallback)

    def stop(self):
        if self.viewer_server is not None:
            self.viewer_server.stop()
            self.viewer_server = None
