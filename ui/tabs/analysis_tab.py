from __future__ import annotations

import json
from pathlib import Path
import time
import webbrowser

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.uavlogviewer_server import UAVLogViewerServer
from core.referee_telemetry import extract_opponent_positions
from ui.widgets.map_widget import MapWidget

try:
    from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineView
except Exception:  # pragma: no cover - optional package
    QWebEnginePage = None
    QWebEngineProfile = None
    QWebEngineSettings = None
    QWebEngineView = None


class LogViewerPage(QWebEnginePage if QWebEnginePage is not None else object):
    def __init__(self, logger=None, profile=None, parent=None):
        if QWebEnginePage is not None:
            if profile is not None:
                super().__init__(profile, parent)
            else:
                super().__init__(parent)
        self.logger = logger

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        source = sourceID.rsplit("/", 1)[-1] if sourceID else "viewer"
        text = f"UAVLogViewer JS {source}:{lineNumber}: {message}"
        print(text)
        if self.logger:
            try:
                self.logger.warning(text)
            except Exception:
                pass


class OpponentAnalysisWidget(QWidget):
    def __init__(self, logger=None, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.opponents = []
        self._referee_tracks = {}
        self._track_started_at = time.monotonic()
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(10)

        side = QFrame()
        side.setObjectName("OpponentAnalysisSide")
        side.setFixedWidth(310)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(8)

        title = QLabel("Rakip SIHA Analizi")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f0f3eb;")
        side_layout.addWidget(title)

        self.summary_label = QLabel("Hakem sunucusundan rakip telemetri bekleniyor.")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color: #a1af9c;")
        side_layout.addWidget(self.summary_label)

        load_row = QHBoxLayout()
        self.load_button = QPushButton("JSON Yukle")
        self.sample_button = QPushButton("Ornek Ac")
        self.load_button.clicked.connect(self.browse_file)
        self.sample_button.clicked.connect(self.load_sample)
        load_row.addWidget(self.load_button)
        load_row.addWidget(self.sample_button)
        side_layout.addLayout(load_row)

        self.opponent_list = QListWidget()
        self.opponent_list.currentRowChanged.connect(self._on_selected_opponent)
        side_layout.addWidget(self.opponent_list, 1)

        self.detail_table = QTableWidget(0, 2)
        self.detail_table.setHorizontalHeaderLabels(["Alan", "Deger"])
        self.detail_table.horizontalHeader().setStretchLastSection(True)
        self.detail_table.verticalHeader().setVisible(False)
        side_layout.addWidget(self.detail_table)

        layout.addWidget(side)

        self.map_widget = MapWidget(shared_map_state=None)
        self.map_widget.flight_area_enabled = True
        layout.addWidget(self.map_widget, 1)

        self.setStyleSheet(
            """
            QWidget { background-color: #090c0a; color: #f0f3eb; }
            QFrame#OpponentAnalysisSide {
                background-color: #141d16;
                border: 1px solid #2c3b2e;
                border-radius: 6px;
            }
            QPushButton {
                background-color: #1b2a1e;
                color: #f0f3eb;
                border: 1px solid #3b5740;
                border-radius: 5px;
                padding: 7px 10px;
            }
            QPushButton:hover { background-color: #213b28; }
            QListWidget, QTableWidget {
                background-color: #111712;
                border: 1px solid #2c3b2e;
                gridline-color: #2c3b2e;
                selection-background-color: #124020;
            }
            QHeaderView::section {
                background-color: #1b2a1e;
                color: #f0f3eb;
                border: 0;
                padding: 4px;
            }
            """
        )

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Rakip SİHA telemetri dosyası seç",
            str(Path(__file__).resolve().parents[2] / "assets" / "data"),
            "Telemetry JSON (*.json);;All Files (*)",
        )
        if path:
            self.load_file(Path(path))

    def load_sample(self):
        sample_path = Path(__file__).resolve().parents[2] / "assets" / "data" / "sample_opponent_telemetry.json"
        self.load_file(sample_path)

    def load_file(self, path: Path):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.load_payload(payload, source_name=path.name)
            if self.logger:
                self.logger.success(f"Rakip SİHA analizi yüklendi: {path.name}")
        except Exception as exc:
            self.summary_label.setText(f"Dosya okunamadı: {exc}")
            if self.logger:
                self.logger.error(f"Rakip SİHA dosyası okunamadı: {exc}")

    def load_payload(self, payload, source_name: str = ""):
        self.opponents = self._normalize_opponents(payload)
        self._render_opponents(source_name)

    def update_from_referee_telemetry(self, telemetry_items):
        items = extract_opponent_positions(telemetry_items)
        if not items:
            return

        changed = False
        for index, sample in enumerate(items):
            if not isinstance(sample, dict):
                continue
            normalized = self._normalize_referee_sample(sample)
            if normalized is None:
                continue
            try:
                normalized["timestamp"] = float(normalized.get("timestamp"))
            except (TypeError, ValueError):
                normalized["timestamp"] = time.monotonic() - self._track_started_at

            key = str(
                sample.get("takim_numarasi")
                or sample.get("takimNumarasi")
                or sample.get("takimNo")
                or sample.get("team")
                or sample.get("id")
                or f"rakip-{index + 1}"
            )
            opponent = self._referee_tracks.setdefault(
                key,
                {
                    "id": key,
                    "callsign": f"Rakip {key}",
                    "team": key,
                    "telemetry": [],
                },
            )
            signature = self._sample_signature(normalized)
            if signature != opponent.get("_last_signature"):
                opponent["telemetry"].append(normalized)
                if len(opponent["telemetry"]) > 5000:
                    del opponent["telemetry"][:-5000]
                opponent["_last_signature"] = signature
                changed = True

        if changed:
            self.opponents = [dict(value) for value in self._referee_tracks.values()]
            self._render_opponents("hakem telemetri")

    def clear_referee_telemetry(self):
        self._referee_tracks.clear()
        self._track_started_at = time.monotonic()
        self.opponents = []
        self.opponent_list.clear()
        self.detail_table.setRowCount(0)
        self.map_widget.set_analysis_routes([])
        self.summary_label.setText("Hakem sunucusundan rakip telemetri bekleniyor.")

    def _render_opponents(self, source_name: str = ""):
        routes = []
        current_item = self.opponent_list.currentItem()
        selected_key = current_item.data(Qt.UserRole) if current_item is not None else None
        self.opponent_list.clear()
        selected_row = -1

        for index, opponent in enumerate(self.opponents):
            route = self._route_for_opponent(opponent)
            opponent["route"] = route
            color = opponent.get("color") or self._default_color(index)
            opponent["color"] = color
            routes.append({
                "label": opponent.get("callsign") or opponent.get("id") or f"Rakip {index + 1}",
                "color": color,
                "route": route,
            })

            item = QListWidgetItem(self._list_label(opponent, index))
            item.setForeground(QColor(color))
            opponent_key = str(opponent.get("id", index))
            item.setData(Qt.UserRole, opponent_key)
            self.opponent_list.addItem(item)
            if selected_key is not None and opponent_key == str(selected_key):
                selected_row = index

        self.map_widget.set_analysis_routes(routes)
        if self.opponents:
            self.opponent_list.setCurrentRow(selected_row if selected_row >= 0 else 0)

        point_count = sum(len(opponent.get("route", [])) for opponent in self.opponents)
        source_text = f" ({source_name})" if source_name else ""
        self.summary_label.setText(
            f"{len(self.opponents)} rakip SİHA, {point_count} telemetri noktası yüklendi{source_text}."
        )

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
    def _normalize_referee_sample(sample: dict):
        lat = OpponentAnalysisWidget._first(sample, "iha_enlem", "ihaEnlem", "enlem", "lat", "latitude")
        lon = OpponentAnalysisWidget._first(sample, "iha_boylam", "ihaBoylam", "boylam", "lon", "lng", "longitude")
        if lat is None or lon is None:
            return None

        normalized = dict(sample)
        normalized["timestamp"] = OpponentAnalysisWidget._first(
            sample,
            "timestamp",
            "time",
            "t",
            "zaman",
        )
        normalized["latitude"] = lat
        normalized["longitude"] = lon
        normalized["altitude"] = OpponentAnalysisWidget._first(sample, "iha_irtifa", "ihaIrtifa", "irtifa", "altitude", "relative_altitude")
        normalized["speed"] = OpponentAnalysisWidget._first(sample, "iha_hiz", "ihaHiz", "hiz", "speed", "ground_speed")
        normalized["heading"] = OpponentAnalysisWidget._first(sample, "iha_yonelme", "ihaYonelme", "heading", "yaw")
        normalized["pitch"] = OpponentAnalysisWidget._first(sample, "iha_dikilme", "ihaDikilme", "pitch")
        normalized["roll"] = OpponentAnalysisWidget._first(sample, "iha_yatis", "ihaYatis", "roll")
        normalized["battery"] = OpponentAnalysisWidget._first(sample, "iha_batarya", "ihaBatarya", "battery")
        return normalized

    def analysis_payload(self):
        payload = []
        for opponent in self.opponents:
            payload.append({
                "id": str(opponent.get("id", "")),
                "callsign": str(opponent.get("callsign", opponent.get("id", "Rakip SIHA"))),
                "team": opponent.get("team", ""),
                "color": opponent.get("color"),
                "telemetry": [dict(sample) for sample in opponent.get("telemetry", [])],
            })
        return payload

    @staticmethod
    def _sample_signature(sample: dict):
        signature = []
        for key in ("latitude", "longitude", "altitude", "speed", "heading"):
            value = sample.get(key)
            try:
                signature.append(round(float(value), 6))
            except (TypeError, ValueError):
                signature.append(value)
        return tuple(signature)

    @staticmethod
    def _normalize_opponents(payload):
        if isinstance(payload, list):
            raw = payload
        elif isinstance(payload, dict):
            raw = (
                payload.get("opponents")
                or payload.get("rakipler")
                or payload.get("aircraft")
                or payload.get("vehicles")
                or payload.get("data")
                or []
            )
        else:
            raw = []

        opponents = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            telemetry = (
                item.get("telemetry")
                or item.get("samples")
                or item.get("positions")
                or item.get("track")
                or []
            )
            if not isinstance(telemetry, list):
                continue
            normalized = dict(item)
            normalized["telemetry"] = telemetry
            normalized.setdefault("id", f"opponent-{index + 1}")
            normalized.setdefault("callsign", f"Rakip {index + 1}")
            opponents.append(normalized)
        return opponents

    @staticmethod
    def _route_for_opponent(opponent):
        route = []
        for sample in opponent.get("telemetry", []):
            if not isinstance(sample, dict):
                continue
            lat = OpponentAnalysisWidget._first(sample, "latitude", "lat", "enlem")
            lon = OpponentAnalysisWidget._first(sample, "longitude", "lon", "lng", "boylam")
            if lat is None or lon is None:
                continue
            try:
                route.append((float(lat), float(lon)))
            except (TypeError, ValueError):
                continue
        return route

    @staticmethod
    def _first(data: dict, *keys):
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        return None

    @staticmethod
    def _default_color(index: int) -> str:
        colors = ["#35c7ff", "#ff4f81", "#9cff57", "#ffd447", "#b980ff", "#ff6b35"]
        return colors[index % len(colors)]

    @staticmethod
    def _list_label(opponent, index: int) -> str:
        name = opponent.get("callsign") or opponent.get("id") or f"Rakip {index + 1}"
        samples = len(opponent.get("telemetry", []))
        return f"{name}  ({samples} nokta)"

    def _on_selected_opponent(self, row: int):
        if row < 0 or row >= len(self.opponents):
            self.detail_table.setRowCount(0)
            return

        opponent = self.opponents[row]
        telemetry = opponent.get("telemetry", [])
        last = telemetry[-1] if telemetry else {}
        route = opponent.get("route", [])
        details = [
            ("ID", opponent.get("id", "-")),
            ("Çağrı adı", opponent.get("callsign", "-")),
            ("Takım", opponent.get("team", "-")),
            ("Nokta", str(len(route))),
            ("Son enlem", self._fmt(self._first(last, "latitude", "lat", "enlem"))),
            ("Son boylam", self._fmt(self._first(last, "longitude", "lon", "lng", "boylam"))),
            ("Son irtifa", self._fmt(self._first(last, "altitude", "relative_altitude", "irtifa"), " m")),
            ("Son hız", self._fmt(self._first(last, "speed", "ground_speed", "hiz"), " m/s")),
            ("Son heading", self._fmt(self._first(last, "heading", "yaw"), " deg")),
        ]
        self.detail_table.setRowCount(len(details))
        for index, (key, value) in enumerate(details):
            self.detail_table.setItem(index, 0, QTableWidgetItem(key))
            self.detail_table.setItem(index, 1, QTableWidgetItem(value))

    @staticmethod
    def _fmt(value, suffix: str = "") -> str:
        if value is None:
            return "-"
        try:
            return f"{float(value):.5f}{suffix}" if not suffix else f"{float(value):.1f}{suffix}"
        except (TypeError, ValueError):
            return str(value)


class AnalysisTab(QWidget):
    def __init__(self, logger=None, shared_map_state=None, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.shared_map_state = shared_map_state
        self.viewer_server: UAVLogViewerServer | None = None
        self.web_view: QWebEngineView | None = None
        self.web_profile = None
        self.opponent_widget: OpponentAnalysisWidget | None = None
        self.placeholder: QLabel | None = None
        self.started = False
        self.viewer_url = ""
        self.current_mode = "opponents"
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
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
        self.own_log_button = QPushButton("Bizim Uçuş Logu")
        self.own_log_button.setCheckable(True)
        self.own_log_button.setChecked(False)
        self.opponent_button = QPushButton("Rakip SİHA Analizi")
        self.opponent_button.setCheckable(True)
        self.opponent_button.setChecked(True)
        self.own_log_button.clicked.connect(lambda: self._set_mode("own"))
        self.opponent_button.clicked.connect(lambda: self._set_mode("opponents"))
        toolbar_layout.addWidget(self.own_log_button)
        toolbar_layout.addWidget(self.opponent_button)
        toolbar_layout.addStretch(1)
        self.main_layout.addWidget(toolbar)

        self.stack = QStackedLayout()
        self.main_layout.addLayout(self.stack)

        self.opponent_widget = OpponentAnalysisWidget(self.logger)
        self.stack.addWidget(self.opponent_widget)
        self.stack.setCurrentWidget(self.opponent_widget)

        if QWebEngineView is None:
            return

        self.placeholder = QLabel("Ucus logu yukleniyor...")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("font-size: 16px; color: #7ea783; background-color: #090c0a;")
        self.stack.addWidget(self.placeholder)
        if self.current_mode == "own":
            self.stack.setCurrentWidget(self.placeholder)

    def activate(self):
        if self.started or QWebEngineView is None:
            self._refresh_if_visible()
            return

        if self.current_mode == "opponents":
            if self.opponent_widget is not None:
                self.stack.setCurrentWidget(self.opponent_widget)
            return

        self.started = True
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background-color: #090c0a;")
        if QWebEnginePage is not None:
            if QWebEngineProfile is not None:
                self.web_profile = QWebEngineProfile(self.web_view)
                self.web_profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
                self.web_profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
                self.web_view.setPage(LogViewerPage(self.logger, self.web_profile, self.web_view))
            else:
                self.web_view.setPage(LogViewerPage(self.logger, parent=self.web_view))
        self.web_view.loadFinished.connect(self._on_load_finished)
        self._enable_webgl_settings()

        self.stack.addWidget(self.web_view)
        self.stack.setCurrentWidget(self.placeholder)
        self._start_viewer()

    def _set_mode(self, mode: str):
        self.current_mode = mode
        self.own_log_button.setChecked(mode == "own")
        self.opponent_button.setChecked(mode == "opponents")
        if mode == "opponents":
            if self.opponent_widget is not None:
                self.stack.setCurrentWidget(self.opponent_widget)
            return
        self.activate()
        if self.web_view is not None:
            if self.viewer_url:
                self.web_view.setUrl(QUrl(self.viewer_url))
            self.stack.setCurrentWidget(self.web_view)
        elif self.placeholder is not None:
            self.stack.setCurrentWidget(self.placeholder)

    def showEvent(self, event):
        super().showEvent(event)
        self.activate()
        self._refresh_if_visible()

    def _refresh_if_visible(self):
        if self.web_view is None or not self.viewer_url or not self.isVisible():
            return
        # QtWebEngine can keep a white backing store when the tab is created while
        # hidden. Reload once after the tab is visible and laid out.
        QTimer.singleShot(250, lambda: self.web_view is not None and self.web_view.reload())

    def _enable_webgl_settings(self):
        if QWebEngineSettings is None or self.web_view is None:
            return

        profile = self.web_view.page().profile()
        if QWebEngineProfile is not None and profile is not None:
            # Keep the embedded app fresh after local rebuilds, but do not fail if
            # this Qt build ignores profile cache settings.
            try:
                profile.clearHttpCache()
            except Exception:
                pass

        settings = self.web_view.settings()
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

    def _build_missing_webengine(self):
        message = QLabel(
            "Analysis viewer needs PyQtWebEngine.\n"
            "Install it with: python -m pip install PyQtWebEngine"
        )
        message.setStyleSheet("font-size: 16px; color: #fbbc05;")
        message.setWordWrap(True)
        self.stack.addWidget(message)
        self.stack.setCurrentWidget(message)

    def _start_viewer(self):
        root = Path(__file__).resolve().parents[2]
        dist_dir = root / "third_party" / "uavlogviewer" / "dist"

        try:
            self.viewer_server = UAVLogViewerServer(dist_dir)
            self.viewer_server.start()
            self.viewer_url = self.viewer_server.url.replace("/#/", "/?embedded=1&v=offline-uavlogviewer-7#/")
            target_url = self._opponent_viewer_url() if self.current_mode == "opponents" else self.viewer_url
            QTimer.singleShot(
                150,
                lambda: self.web_view is not None and self.web_view.setUrl(QUrl(target_url)),
            )
            if self.logger:
                self.logger.success(f"Offline ucus logu baslatildi: {self.viewer_url}")
        except Exception as exc:
            if self.logger:
                self.logger.error(f"Offline ucus logu baslatilamadi: {exc}")
            self._show_start_error(str(exc))

    def _opponent_viewer_url(self) -> str:
        if not self.viewer_server:
            return ""
        return self.viewer_server.url.replace("/#/", "/?embedded=1&v=offline-opponents-4#/opponents")

    def _load_opponent_viewer(self):
        if self.opponent_widget is not None:
            self.stack.setCurrentWidget(self.opponent_widget)

    def update_referee_telemetry(self, telemetry_items):
        if self.opponent_widget is not None:
            self.opponent_widget.update_from_referee_telemetry(telemetry_items)

    def clear_referee_telemetry(self):
        if self.opponent_widget is not None:
            self.opponent_widget.clear_referee_telemetry()

    def _on_load_finished(self, ok: bool):
        if ok and self.web_view is not None:
            self._sanitize_log_viewer_branding()
            if self.current_mode == "own":
                self.stack.setCurrentWidget(self.web_view)
            QTimer.singleShot(500, self._check_viewer_health)
            return
        # QWebEngine may report false when one subresource fails, while the Vue app
        # still renders. Do not replace the viewer with an error screen here.
        if self.logger and self.web_view is not None:
            self.logger.warning(f"Ucus logu sayfa yukleme uyarisi: {self.web_view.url().toString()}")

    def _check_viewer_health(self):
        if self.web_view is None or self.current_mode != "own":
            return
        script = """
            (() => {
                const text = document.body ? document.body.innerText : '';
                const app = document.getElementById('app');
                return {
                    title: document.title,
                    hasApp: !!app,
                    appLength: app ? app.innerHTML.length : 0,
                    text: text.slice(0, 120)
                };
            })()
        """
        self.web_view.page().runJavaScript(script, self._on_health_result)

    def _on_health_result(self, result):
        if not isinstance(result, dict):
            return
        if "UAV Log Viewer" in result.get("text", ""):
            return
        if self.logger:
            self.logger.warning(f"Ucus logu health check bos gorundu: {result}")
        if self.web_view is not None and self.viewer_url:
            self.web_view.setUrl(QUrl(self.viewer_url))

    def _sanitize_log_viewer_branding(self):
        if self.web_view is None:
            return
        script = """
            (() => {
                document.title = 'Ucus Logu';
                const rewrite = () => {
                    document.querySelectorAll('h1.brand a, h1, a').forEach((node) => {
                        const text = (node.innerText || '').replace(/\\s+/g, ' ').trim();
                        if (text === 'UAV Log Viewer') {
                            node.innerHTML = '<b>Ucus</b> Logu<i class="fas fa-plane"></i>';
                        }
                    });
                };
                rewrite();
                setTimeout(rewrite, 250);
                setTimeout(rewrite, 1000);
                return true;
            })()
        """
        self.web_view.page().runJavaScript(script)

    def _show_start_error(self, message: str):
        fallback = QWidget()
        layout = QVBoxLayout(fallback)
        label = QLabel(
            "Offline ucus logu goruntuleyici baslatilamadi.\n"
            f"{message}\n\n"
            "Run npm build in third_party/uavlogviewer if dist is missing."
        )
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 15px; color: #fbbc05;")
        layout.addWidget(label)

        button = QPushButton("Ucus Logunu Online Ac")
        button.clicked.connect(lambda: webbrowser.open("https://plot.ardupilot.org/#/"))
        layout.addWidget(button)

        if self.web_view is not None:
            try:
                self.web_view.loadFinished.disconnect(self._on_load_finished)
            except TypeError:
                pass
            self.stack.removeWidget(self.web_view)
            self.web_view.deleteLater()
            self.web_view = None

        self.stack.addWidget(fallback)
        self.stack.setCurrentWidget(fallback)

    def stop(self):
        if self.viewer_server is not None:
            self.viewer_server.stop()
            self.viewer_server = None
