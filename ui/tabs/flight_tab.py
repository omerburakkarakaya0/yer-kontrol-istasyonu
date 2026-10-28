"""
Flight Tab
Canlı uçuş izleme sekmesi

MİMARİ:
- Sol panel: Bağlantı ve hakem sunucusu
- Ana alan: Tam boy harita üzerinde kompakt uçuş panelleri
"""
import time

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QGroupBox, QPushButton,
    QFormLayout, QComboBox, QLineEdit, QFileDialog, QSizePolicy,
    QGridLayout, QLabel, QMessageBox, QMenu, QInputDialog, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from ui.widgets.flight_map_canvas import FlightMapCanvas
from ui.widgets.flight_logs_widget import FlightLogsWidget
from ui.widgets.teams_widget import TeamsWidget
from ui.widgets.map_widget import MapWidget
from ui.widgets.video_widget import VideoWidget
from ui.widgets.flight_hud_widget import FlightHUDWidget
from ui.widgets.aircraft_model_widget import AircraftModelWidget
from models.telemetry import TelemetryData
from ui.widgets.telemetry_icons import (
    BatteryIcon, SignalIcon, CompassIcon, SpeedGaugeIcon,
    AltitudeIcon, PitchIcon, RollIcon, GpsIcon
)
from ui.widgets.telemetry_card import TelemetryCard
import config


class FlightTab(QWidget):
    connect_requested = pyqtSignal(dict)
    disconnect_requested = pyqtSignal()
    mode_change_requested = pyqtSignal(str)
    task_mode_requested = pyqtSignal(str)
    video_source_selected = pyqtSignal(str)
    referee_connect_requested = pyqtSignal(dict)
    referee_disconnect_requested = pyqtSignal()
    referee_qr_fetch_requested = pyqtSignal()
    referee_hss_fetch_requested = pyqtSignal()
    guided_target_requested = pyqtSignal(float, float, float)

    @staticmethod
    def _angle_delta_deg(value: float, zero: float) -> float:
        return ((float(value) - float(zero) + 180.0) % 360.0) - 180.0

    def __init__(self, mission_manager, shared_map_state=None, parent=None, logger=None):
        super().__init__(parent)
        self.mission_manager = mission_manager
        self.shared_map_state = shared_map_state
        self.logger = logger

        self.last_packet_timestamp = None
        self._last_signal_state = None
        
        self.current_signal_value = 0
        self._last_altitude = float(getattr(config, "GUIDED_DEFAULT_ALTITUDE_M", 100.0))
        self._last_guided_altitude = self._last_altitude
        self._last_armed = False
        self._pending_mode = None

        self.signal_drop_timer = QTimer(self)
        self.signal_drop_timer.timeout.connect(self._drop_signal_step)  

        self.init_ui()

        if self.mission_manager is not None:
            self.mission_manager.mission_changed.connect(self._on_mission_changed)
            self._on_mission_changed()

        #self.signal_timer = QTimer(self)
        #self.signal_timer.timeout.connect(self._update_connection_signal_badge)
        #self.signal_timer.start(250)

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        # =========================================================
        # SOL PANEL: Bağlantı ve hakem sunucusu
        # =========================================================
        left_panel = QWidget()
        left_panel.setObjectName("leftRail")
        left_panel.setMinimumWidth(238)
        left_panel.setMaximumWidth(258)
        left_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        conn_group = QGroupBox("BAĞLANTI")
        self.connection_group = conn_group
        conn_group.setObjectName("bluePanel")
        conn_body = QWidget()
        conn_form = QGridLayout(conn_body)
        conn_form.setContentsMargins(9, 8, 9, 8)
        conn_form.setSpacing(6)
        conn_form.setColumnStretch(1, 1)
        for row in range(5):
            conn_form.setRowStretch(row, 1)

        self.conn_type = QComboBox()
        self.conn_type.addItems(["Serial", "UDP", "TCP"])

        self.conn_target = QComboBox()
        self.conn_target.setEditable(True)
        self.conn_target.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.conn_target.setMinimumContentsLength(6)
        self.conn_target.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.conn_target.lineEdit().setPlaceholderText("COM7")

        self.btn_refresh_ports = QPushButton("Yenile")
        self.btn_refresh_ports.setObjectName("iconButton")
        self.btn_refresh_ports.setMinimumHeight(24)
        self.btn_refresh_ports.clicked.connect(self._refresh_connection_options)

        target_row = QHBoxLayout()
        target_row.addWidget(self.conn_target, 1)
        target_row.addWidget(self.btn_refresh_ports)

        self.conn_baud = QComboBox()
        self.conn_baud.setEditable(True)
        self.conn_baud.addItems(["57600", "115200", "38400", "19200", "9600", "230400", "921600"])
        self.conn_baud.setCurrentText("57600")
        self.conn_baud.lineEdit().setPlaceholderText("57600")

        for row, title in enumerate(("Type:", "Target:", "Baud:", "Durum:")):
            label = QLabel(title)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            conn_form.addWidget(label, row, 0)
        conn_form.addWidget(self.conn_type, 0, 1)
        conn_form.addLayout(target_row, 1, 1)
        conn_form.addWidget(self.conn_baud, 2, 1)
        self.conn_type.currentTextChanged.connect(self._on_connection_type_changed)
        self._refresh_connection_options()

        self.conn_status_label = QLabel("Disconnected")
        self.conn_status_label.setObjectName("statusPill")
        self.conn_status_label.setAlignment(Qt.AlignCenter)
        self.conn_status_label.setStyleSheet(_flight_tab_referee_status_style(False))

        conn_form.addWidget(self.conn_status_label, 3, 1)

        conn_btn_row = QHBoxLayout()
        self.btn_connect = QPushButton("  Bağlan")
        self.btn_connect.setObjectName("primaryButton")
        self.btn_disconnect = QPushButton("  Bağlantıyı Kes")
        self.btn_disconnect.setObjectName("ghostButton")
        self.btn_disconnect.setEnabled(False)

        self.btn_connect.clicked.connect(self._emit_connect)
        self.btn_disconnect.clicked.connect(self._handle_disconnect)

        conn_btn_row.addWidget(self.btn_connect)
        conn_btn_row.addWidget(self.btn_disconnect)
        conn_form.addLayout(conn_btn_row, 4, 0, 1, 2)
        for control in (self.conn_type, self.conn_target, self.conn_baud,
                        self.conn_status_label, self.btn_refresh_ports,
                        self.btn_connect, self.btn_disconnect):
            control.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.connection_scroll = self._wrap_sidebar_form(conn_group, conn_body)
        conn_body.setObjectName("connectionFormBody")
        conn_body.setStyleSheet("QWidget#connectionFormBody { background: transparent; }")

        left_layout.addWidget(conn_group, 1)

        ref_group = self.create_referee_server_group()
        self.referee_group = ref_group
        ref_group.setObjectName("bluePanel")
        left_layout.addWidget(ref_group, 1)

        self.flight_logs = FlightLogsWidget(self.logger)
        left_layout.addWidget(self.flight_logs, 1)
        for panel in (conn_group, ref_group, self.flight_logs):
            panel.setMinimumHeight(0)
            panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(240)
        left_scroll.setMaximumWidth(260)
        self.left_scroll = left_scroll
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        left_scroll.setWidget(left_panel)
        main_splitter.addWidget(left_scroll)

        # =========================================================
        # SAĞ ANA ALAN
        # =========================================================
        self.map_widget = MapWidget(shared_map_state=self.shared_map_state)
        self.map_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.map_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.map_widget.customContextMenuRequested.connect(self._show_flight_map_context_menu)

        self.map_widget.setMinimumSize(0, 0)
        self.map_widget.setProperty("hideStatusOverlay", True)
        self.map_canvas = FlightMapCanvas(self.map_widget)

        self.video_widget = VideoWidget()
        self.video_widget.image_label.setMinimumSize(0, 0)
        self.video_widget.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.video_widget.image_label.setStyleSheet("background: #0b0e0c; color: #a1af9c; border: 1px solid #2c3b2e; font-size: 12px;")
        camera_group = QGroupBox("KAMERA")
        camera_group.setObjectName("bluePanel")
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.setContentsMargins(8, 20, 8, 8)
        camera_layout.addWidget(self.video_widget)
        self.camera_group = camera_group

        self.teams_widget = TeamsWidget()
        self.teams_widget.team_selected.connect(self._focus_team)

        mode_group = QGroupBox("MOD")
        mode_group.setObjectName("bluePanel")
        mode_layout = QGridLayout(mode_group)
        mode_layout.setContentsMargins(9, 14, 9, 8)
        mode_layout.setHorizontalSpacing(6)
        mode_layout.setVerticalSpacing(3)

        self.active_mode_label = QLabel("--")
        self.active_mode_label.setObjectName("activeModePill")
        self.active_mode_label.setAlignment(Qt.AlignCenter)
        self.active_mode_label.setMaximumHeight(34)
        self.active_mode_label.setMaximumWidth(240)
        self.active_mode_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.active_task_label = QLabel("--")
        self.active_task_label.setObjectName("activeTaskPill")
        self.active_task_label.setAlignment(Qt.AlignCenter)
        self.active_task_label.setMaximumHeight(34)
        self.active_task_label.setMaximumWidth(240)
        self.active_task_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.btn_mode_manual = QPushButton("Manual")
        self.btn_mode_auto = QPushButton("Auto")
        self.btn_mode_guided = QPushButton("Guided")
        self.btn_mode_empty = QPushButton("")
        self.btn_mode_empty.setEnabled(False)
        self.btn_mode_kamikaze = QPushButton("Kamikaze")
        self.btn_mode_savunma_kacis = QPushButton("Hava Savunmadan Kaçış")
        self.btn_mode_fbwa = QPushButton("FBWA")
        self.btn_mode_takip = QPushButton("Takip")
        self.btn_mode_iptal = QPushButton("Görev İptal")
        self.btn_mode_rtl = QPushButton("RTL")
        self.btn_mode_otonom_in = QPushButton("Otonom İn")
        self.btn_mode_empty.setVisible(False)

        self.flight_mode_buttons = [
            self.btn_mode_manual,
            self.btn_mode_auto,
            self.btn_mode_guided,
            self.btn_mode_rtl,
            self.btn_mode_fbwa
        ]
        self.task_mode_buttons = [
            self.btn_mode_kamikaze,
            self.btn_mode_savunma_kacis,
            self.btn_mode_takip,
            self.btn_mode_iptal,
            self.btn_mode_otonom_in
        ]
        self.mode_buttons = self.flight_mode_buttons + self.task_mode_buttons

        for b in self.flight_mode_buttons:
            b.setObjectName("modeButton")
            b.setCheckable(True)
            b.clicked.connect(self._on_mode_button)
            b.setFixedHeight(28)

        for b in self.task_mode_buttons:
            b.setObjectName("taskModeButton")
            b.setCheckable(True)
            b.clicked.connect(self._on_task_button)
            b.setFixedHeight(28)

        active_mode_caption = QLabel("Aktif Mod")
        active_mode_caption.setObjectName("fieldLabel")
        active_task_caption = QLabel("Aktif Görev")
        active_task_caption.setObjectName("fieldLabel")

        mode_layout.addWidget(active_mode_caption, 0, 0)
        mode_layout.addWidget(self.active_mode_label, 0, 1, 1, 2)
        mode_layout.addWidget(active_task_caption, 1, 0)
        mode_layout.addWidget(self.active_task_label, 1, 1, 1, 2)

        self.flight_modes_label = QLabel("UÇUŞ MODLARI")
        self.flight_modes_label.setObjectName("sectionLabel")
        mode_layout.addWidget(self.flight_modes_label, 2, 0, 1, 3)

        mode_layout.addWidget(self.btn_mode_manual, 3, 0)
        mode_layout.addWidget(self.btn_mode_auto, 3, 1)
        mode_layout.addWidget(self.btn_mode_guided, 3, 2)
        mode_layout.addWidget(self.btn_mode_rtl, 4, 0)
        mode_layout.addWidget(self.btn_mode_fbwa, 4, 1, 1, 2)

        self.mission_modes_label = QLabel("GÖREV MODLARI")
        self.mission_modes_label.setObjectName("sectionLabel")
        mode_layout.addWidget(self.mission_modes_label, 5, 0, 1, 3)

        mode_layout.addWidget(self.btn_mode_kamikaze, 6, 0)
        mode_layout.addWidget(self.btn_mode_takip, 6, 1)
        mode_layout.addWidget(self.btn_mode_otonom_in, 6, 2)
        mode_layout.addWidget(self.btn_mode_iptal, 7, 0)
        mode_layout.addWidget(self.btn_mode_savunma_kacis, 7, 1, 1, 2)
        for column in range(3):
            mode_layout.setColumnStretch(column, 1)

        self.hud_widget = FlightHUDWidget(compact=True)
        self.hud_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # =========================================================
        # TELEMETRY PANEL - ICONLU YENİ TASARIM
        # =========================================================
        telemetry_group = QGroupBox("TELEMETRİ")
        telemetry_group.setObjectName("bluePanel")
        telemetry_layout = QVBoxLayout(telemetry_group)
        telemetry_layout.setContentsMargins(8, 20, 8, 8)
        telemetry_layout.setSpacing(0)

        # ICONLAR
        self.icon_altitude = AltitudeIcon()
        self.icon_pitch = PitchIcon()
        self.icon_roll = RollIcon()
        self.icon_gps_lat = GpsIcon()
        self.icon_gps_lon = GpsIcon()

        self.icon_yaw = CompassIcon()
        self.icon_ground_speed = SpeedGaugeIcon()
        self.icon_air_speed = SpeedGaugeIcon()
        self.icon_battery = BatteryIcon()
        self.icon_signal = SignalIcon()

        # CARDLAR
        self.card_altitude = TelemetryCard("Altitude", self.icon_altitude, parent=self, compact=True)
        self.card_ground_speed = TelemetryCard("Ground Speed", self.icon_ground_speed, parent=self, compact=True)
        self.card_air_speed = TelemetryCard("Air Speed", self.icon_air_speed, parent=self, compact=True)
        self.card_battery = TelemetryCard("Battery", self.icon_battery, parent=self, compact=True)

        self.card_pitch = TelemetryCard("Pitch", self.icon_pitch, parent=self, compact=True)
        self.card_roll = TelemetryCard("Roll", self.icon_roll, parent=self, compact=True)
        self.card_yaw = TelemetryCard("Yaw", self.icon_yaw, parent=self, compact=True)

        self.card_gps_lat = TelemetryCard("GPS Lat", self.icon_gps_lat, parent=self, compact=True)
        self.card_gps_lon = TelemetryCard("GPS Lon", self.icon_gps_lon, parent=self, compact=True)
        self.card_signal = TelemetryCard("Signal", self.icon_signal, parent=self, compact=True)
        for card in (self.card_altitude, self.card_pitch, self.card_roll,
                     self.card_yaw, self.card_gps_lat, self.card_gps_lon):
            card.hide()

        self.aircraft_model_widget = AircraftModelWidget(
            getattr(config, "AIRCRAFT_MODEL_PATH", ""),
            max_faces=int(getattr(config, "AIRCRAFT_MODEL_MAX_FACES", 4500)),
        )

        self.aircraft_model_widget.setMinimumSize(130, 125)

        # The model gets the entire centre panel; live readouts are hosted by
        # the main window's persistent right rail, including on other pages.
        telemetry_layout.addWidget(self.aircraft_model_widget, 1)
        self.telemetry_readouts = QWidget(self)
        self.telemetry_readouts.setObjectName("telemetryReadouts")
        readout_layout = QVBoxLayout(self.telemetry_readouts)
        readout_layout.setContentsMargins(0, 0, 0, 0)
        readout_layout.setSpacing(8)
        for card in (self.card_battery, self.card_ground_speed, self.card_air_speed, self.card_signal):
            card.setAttribute(Qt.WA_StyledBackground, True)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            readout_layout.addWidget(card, 1)
        self.telemetry_readouts.hide()

        telemetry_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.telemetry_group = telemetry_group
        self.mode_group = mode_group
        self.map_canvas.set_panels(telemetry_group, self.hud_widget, camera_group,
                                   self.teams_widget, mode_group)
        main_splitter.addWidget(self.map_canvas)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_layout.addWidget(main_splitter)
        main_splitter.setSizes([250, 1400])
        main_splitter.setHandleWidth(6)

        self.setStyleSheet("""
            FlightTab {
                background-color: #090c0a;
                color: #e0e7dc;
            }
            QWidget#leftRail {
                background-color: transparent;
            }
            QWidget#leftRail QLabel {
                font-size: 10px;
            }
            QWidget#leftRail QGroupBox#bluePanel {
                margin-top: 0px;
                padding-top: 24px;
                font-size: 11px;
            }
            QWidget#leftRail QGroupBox#bluePanel::title {
                font-size: 11px;
                left: 12px;
                padding: 0px;
            }
            QWidget#leftRail QLineEdit, QWidget#leftRail QComboBox {
                font-size: 10px;
                padding: 4px 6px;
                min-height: 14px;
            }
            QWidget#leftRail QPushButton {
                font-size: 10px;
                padding: 4px 7px;
                min-height: 16px;
            }
            QWidget#leftRail QWidget#connectionFormBody QComboBox,
            QWidget#leftRail QWidget#connectionFormBody QPushButton {
                font-size: 11px;
            }
            QGroupBox#bluePanel {
                color: #f0f3eb;
                font-weight: 800;
                border: 1px solid #2c3b2e;
                border-radius: 10px;
                margin-top: 0px;
                padding-top: 24px;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #141d16, stop:1 #0e140f);
            }
            QGroupBox#bluePanel::title {
                subcontrol-origin: border;
                subcontrol-position: top left;
                top: 8px;
                left: 12px;
                padding: 0px;
                color: #e0e7dc;
                font-size: 12px;
            }
            QLabel#fieldLabel {
                color: #a1af9c;
                font-weight: 700;
            }
            QLabel#sectionLabel {
                color: #a1af9c;
                font-size: 11px;
                font-weight: 800;
                padding-top: 3px;
                border-top: 1px solid #2c3b2e;
            }
            QLabel#activeModePill {
                color: #b4ceac;
                background-color: #213b28;
                border: 1px solid #3b5740;
                border-radius: 8px;
                padding: 5px;
                font-weight: 800;
            }
            QLabel#activeTaskPill {
                color: #c9cfad;
                background-color: #282e20;
                border: 1px solid #596542;
                border-radius: 8px;
                padding: 5px;
                font-weight: 800;
            }
            QLineEdit, QComboBox {
                background-color: #111712;
                color: #f0f3eb;
                border: 1px solid #2c3b2e;
                border-radius: 6px;
                padding: 7px 9px;
                selection-background-color: #03631b;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #577b59;
            }
            QPushButton#primaryButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #03631b, stop:1 #124020);
                color: #f0f3eb;
                border: 1px solid #577b59;
                border-radius: 6px;
                padding: 9px 14px;
                font-weight: 700;
            }
            QPushButton#primaryButton:hover {
                background-color: #17642b;
            }
            QPushButton#ghostButton, QPushButton#railButton, QPushButton#iconButton {
                background-color: #111712;
                color: #f0f3eb;
                border: 1px solid #2c3b2e;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 650;
            }
            QPushButton#railButton {
                min-height: 34px;
                text-align: left;
            }
            QPushButton#ghostButton:hover, QPushButton#railButton:hover, QPushButton#iconButton:hover {
                border-color: #577b59;
                background-color: #1b2a1e;
            }
            QPushButton#ghostButton:disabled, QPushButton#primaryButton:disabled {
                color: #6c7968;
                border-color: #202c23;
                background-color: #111712;
            }
            QPushButton#modeButton, QPushButton#taskModeButton {
                background-color: #111712;
                color: #e0e7dc;
                border: 1px solid #2c3b2e;
                border-radius: 8px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: 700;
                min-height: 20px;
            }
            QPushButton#modeButton:hover, QPushButton#taskModeButton:hover {
                border-color: #577b59;
                background-color: #1b2a1e;
            }
            QPushButton#modeButton:checked {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #17642b, stop:1 #124020);
                border: 1px solid #577b59;
                color: #ffffff;
                font-weight: 800;
            }
            QPushButton#taskModeButton:checked {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #465435, stop:1 #27351f);
                border: 1px solid #7e8e60;
                color: #f0f0dc;
                font-weight: 800;
            }
            QLabel {
                color: #e0e7dc;
            }
            QSplitter::handle {
                background-color: #0e140f;
                border-radius: 3px;
            }
            QSplitter::handle:hover {
                background-color: #2c3b2e;
            }
        """)

    @staticmethod
    def _wrap_sidebar_form(group, body):
        """Keep equal-height cards; scroll only their contents on small screens."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumSize(0, 0)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollBar:vertical { width: 6px; }")
        body.setObjectName("sidebarFormBody")
        body.setStyleSheet("QWidget#sidebarFormBody { background: transparent; }")
        scroll.setWidget(body)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 10, 0, 2)
        layout.setSpacing(0)
        layout.addWidget(scroll)
        return scroll

    def _focus_team(self, latitude, longitude):
        self.map_widget.set_initial_view(latitude, longitude, self.map_widget.zoom)

    def update_referee_teams(self, payload):
        if self.ref_btn_disconnect.isEnabled():
            self.teams_widget.update_teams(payload, own_team=self.ref_team.text().strip())

    def update_telemetry(self, telemetry: TelemetryData):
        self.last_packet_timestamp = time.time()
        
        if hasattr(self, "signal_drop_timer") and self.signal_drop_timer.isActive():
            self.signal_drop_timer.stop()

        self.hud_widget.update_telemetry(telemetry)

        altitude = getattr(telemetry, "altitude", 0)
        self._last_armed = bool(getattr(telemetry, "armed", False))
        if altitude is not None:
            try:
                self._last_altitude = float(altitude)
            except (TypeError, ValueError):
                pass
        ground_speed = telemetry.safe_ground_speed
        air_speed = telemetry.safe_air_speed
        battery = getattr(telemetry, "battery", 0)
        pitch = getattr(telemetry, "pitch", None)
        roll = getattr(telemetry, "roll", None)
        raw_heading = (
            getattr(telemetry, "heading", None)
            or getattr(telemetry, "yaw", None)
            or getattr(telemetry, "hdg", None)
            or getattr(telemetry, "compass", None)
            or getattr(telemetry, "compass_hdg", None)
            or 0
        )

        pitch = float(pitch or 0)
        roll = float(roll or 0)
        raw_heading = float(raw_heading or 0) % 360
        map_heading = (
            raw_heading + float(getattr(config, "AIRCRAFT_HEADING_OFFSET_DEG", 0.0))
        ) % 360
        heading = raw_heading
        latitude = float(getattr(telemetry, "latitude", None) or 0)
        longitude = float(getattr(telemetry, "longitude", None) or 0)

        # TelemetryData içinde signal yoksa bağlantı durumundan yaklaşık değer üretir
        signal_state = self._get_connection_signal_state(telemetry)
        signal = 0

        signal_quality = getattr(telemetry, "signal_quality", None)
        if signal_quality is not None and float(signal_quality) > 0:
            signal = int(max(0, min(100, signal_quality)))
        elif signal_state == "good":
            signal = 100
        elif signal_state == "info":
            signal = 70
        elif signal_state == "warning":
            signal = 30

        # TEXT DEĞERLERİ
        self.card_altitude.set_value(f"{altitude:.2f} m")
        self.card_ground_speed.set_value(f"{ground_speed:.2f} m/s")
        self.card_air_speed.set_value(f"{air_speed:.2f} m/s")
        self.card_battery.set_value(f"{battery:.2f}%")

        self.card_pitch.set_value(f"{pitch:.2f}°")
        self.card_roll.set_value(f"{roll:.2f}°")
        self.card_yaw.set_value(f"{heading:.2f}°")

        self.card_gps_lat.set_value(f"{latitude:.6f}")
        self.card_gps_lon.set_value(f"{longitude:.6f}")
        self.card_signal.set_value(f"{signal}%")

        # ICON DEĞERLERİ
        self.icon_ground_speed.set_value(ground_speed)
        self.icon_air_speed.set_value(air_speed)
        self.icon_battery.set_value(battery)
        self.icon_signal.set_value(signal)
        self.icon_yaw.set_heading(heading)
        if hasattr(self, "aircraft_model_widget"):
            if bool(getattr(config, "AIRCRAFT_MODEL_USE_TELEMETRY_YAW", False)):
                model_yaw = (180.0 - heading) % 360.0
            else:
                model_yaw = 0.0
            model_pitch = pitch
            model_roll = roll
            self.aircraft_model_widget.set_heading(heading)
            self.aircraft_model_widget.set_attitude(model_pitch, model_roll, model_yaw)

        if telemetry.connected and latitude != 0 and longitude != 0:
            self.map_widget.update_current_position(
                latitude,
                longitude
            )

            if self.shared_map_state is not None and hasattr(self.shared_map_state, "set_aircraft"):
                self.shared_map_state.set_aircraft(
                    latitude,
                    longitude,
                    map_heading
                )

            self.map_widget.check_defense_zone_breach()

        self.set_active_mode(getattr(telemetry, "mode", None))

        #self._update_connection_signal_badge(telemetry)

    def _show_flight_map_context_menu(self, position):
        latitude, longitude = self.map_widget.coordinate_at(position)
        menu = QMenu(self.map_widget)
        choose_altitude = menu.addAction("Buraya Uç (GUIDED) — İrtifa Seç...")
        current_altitude = menu.addAction(f"Buraya Uç — Mevcut İrtifa ({self._last_altitude:.1f} m)")
        selected = menu.exec_(self.map_widget.mapToGlobal(position))
        if selected is None:
            return

        if selected is choose_altitude:
            altitude, ok = QInputDialog.getDouble(
                self,
                "GUIDED Hedef İrtifası",
                "Home noktasına göre irtifa (metre):",
                self._last_guided_altitude,
                1.0,
                10000.0,
                1,
            )
            if not ok:
                return
            self._last_guided_altitude = altitude
        elif selected is current_altitude:
            altitude = max(1.0, self._last_altitude)
        else:
            return

        readiness_warning = ""
        if not self._last_armed:
            readiness_warning = (
                "\n\nUYARI: Araç şu anda DISARMED. Hedef gönderilir ancak uçak; "
                "ARM edilmeden, geçerli GPS/EKF konumu olmadan ve uçuşa hazır hale gelmeden hareket etmez."
            )
        answer = QMessageBox.warning(
            self,
            "GUIDED Hedef Onayı",
            (
                "Araç GUIDED moda geçirilecek ve aşağıdaki hedefe uçacaktır:\n\n"
                f"Enlem: {latitude:.7f}\n"
                f"Boylam: {longitude:.7f}\n"
                f"İrtifa: {altitude:.1f} m (Home'a göre)\n\n"
                "Komutu göndermek istiyor musunuz?"
                f"{readiness_warning}"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.map_widget.set_guided_target(latitude, longitude, altitude, "pending")
        self.guided_target_requested.emit(latitude, longitude, altitude)

    def set_guided_target_result(self, payload: dict, accepted: bool):
        target = dict(payload or {})
        latitude = target.get("latitude")
        longitude = target.get("longitude")
        altitude = target.get("altitude")
        if latitude is None or longitude is None or altitude is None:
            current = getattr(self.map_widget, "guided_target", None)
            if not isinstance(current, dict):
                return
            latitude = current["latitude"]
            longitude = current["longitude"]
            altitude = current["altitude"]
        self.map_widget.set_guided_target(
            latitude,
            longitude,
            altitude,
            "accepted" if accepted else "rejected",
        )

    def update_video_frame(self, image):
        self.video_widget.update_frame(image)

    def _on_connection_type_changed(self, conn_type: str):
        self._refresh_connection_options()

    def _refresh_connection_options(self):
        conn_type = self.conn_type.currentText()
        current_target = self.conn_target.currentText().strip()
        self.conn_target.blockSignals(True)
        self.conn_target.clear()

        if conn_type == "Serial":
            ports = self._list_serial_ports()
            if ports:
                for device, description in ports:
                    label = device if not description else f"{device} - {description}"
                    self.conn_target.addItem(label, device)
                if current_target:
                    self._restore_combo_text(self.conn_target, current_target)
            else:
                self.conn_target.addItem("COM7")
                self.conn_target.addItem("COM3")
            self.conn_baud.setEnabled(True)
            self.btn_refresh_ports.setEnabled(True)
        elif conn_type == "UDP":
            self.conn_target.addItems(["udp:0.0.0.0:14550", "14550", "udp:127.0.0.1:14550"])
            if current_target:
                self._restore_combo_text(self.conn_target, current_target)
            self.conn_baud.setEnabled(False)
            self.btn_refresh_ports.setEnabled(False)
        elif conn_type == "TCP":
            self.conn_target.addItems(["tcp:127.0.0.1:5760", "127.0.0.1:5760"])
            if current_target:
                self._restore_combo_text(self.conn_target, current_target)
            self.conn_baud.setEnabled(False)
            self.btn_refresh_ports.setEnabled(False)
        else:
            self.conn_target.addItem("")
            self.conn_baud.setEnabled(False)
            self.btn_refresh_ports.setEnabled(False)

        self.conn_target.blockSignals(False)

    def _list_serial_ports(self):
        try:
            from serial.tools import list_ports
            return [
                (port.device, port.description)
                for port in list_ports.comports()
            ]
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Serial port list failed: {exc}")
            return []

    def _selected_target(self) -> str:
        if self.conn_type.currentText() == "Serial":
            index = self.conn_target.currentIndex()
            data = self.conn_target.itemData(index)
            if data:
                return str(data)
            return self.conn_target.currentText().split(" - ", 1)[0].strip()
        return self.conn_target.currentText().strip()

    @staticmethod
    def _restore_combo_text(combo: QComboBox, text: str):
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setEditText(text)

    def set_connection_status(self, connected: bool):
        if not connected:
            self._pending_mode = None
        for button in self.flight_mode_buttons:
            button.setEnabled(bool(connected) and self._pending_mode is None)
        if connected:
            self.conn_status_label.setText("Connected")
            self.conn_status_label.setStyleSheet(_flight_tab_referee_status_style(True))
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(True)
        else:
            self.conn_status_label.setText("Disconnected")
            self.conn_status_label.setStyleSheet(_flight_tab_referee_status_style(False))
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)

    def _emit_connect(self):
        # Keep a binary status indicator: red until the backend confirms the
        # connection, green only after a real heartbeat/data link exists.
        self.conn_status_label.setText("Disconnected")
        self.conn_status_label.setStyleSheet(_flight_tab_referee_status_style(False))
        self.btn_disconnect.setEnabled(False)
        cfg = {
            "type": self.conn_type.currentText(),
            "target": self._selected_target(),
            "baud": self.conn_baud.currentText().strip(),
        }

        if self.logger:
            self.logger.info(
                f"Connect request: type={cfg['type']}, "
                f"target={cfg['target'] or '-'}, baud={cfg['baud'] or '-'}"
            )

        self.connect_requested.emit(cfg)

    def _handle_disconnect(self):
        self.conn_status_label.setText("Bağlı değil")
        self.conn_status_label.setStyleSheet(_flight_tab_referee_status_style(False))

        if self.logger:
            self.logger.warning("Disconnect requested.")

        self.last_packet_timestamp = None

        self.current_signal_value = 100

        if hasattr(self, "card_signal"):
            self.card_signal.set_value("100%")
            self.icon_signal.set_value(100)

        self.signal_drop_timer.start(500)

        self.disconnect_requested.emit()
        
    def _drop_signal_step(self):
        if self.current_signal_value > 70:
            self.current_signal_value = 70
        elif self.current_signal_value > 30:
            self.current_signal_value = 30
        elif self.current_signal_value > 0:
            self.current_signal_value = 0
        else:
            self.signal_drop_timer.stop()
            return

        if hasattr(self, "card_signal"):
            self.card_signal.set_value(f"{self.current_signal_value}%")
            self.icon_signal.set_value(self.current_signal_value)

    def _on_mode_button(self):
        sender = self.sender()
        requested_mode = sender.text()
        sender.setChecked(False)

        if self._pending_mode is not None:
            if self.logger:
                self.logger.warning(f"Mode change already in progress: {self._pending_mode}")
            return

        answer = QMessageBox.question(
            self,
            "Mode Change Confirmation",
            f"{requested_mode} moduna gecmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            if self.logger:
                self.logger.info(f"Mode change cancelled: {requested_mode}")
            return

        if self.logger:
            self.logger.info(f"Mode change confirmed: {requested_mode}")

        self.set_mode_change_pending(requested_mode)
        self.mode_change_requested.emit(requested_mode)

    def set_mode_change_pending(self, mode_name: str):
        self._pending_mode = str(mode_name or "").upper()
        for button in self.flight_mode_buttons:
            button.setEnabled(False)
        self.active_mode_label.setText(f"{self._pending_mode}…")

    def set_mode_change_result(self, mode_name: str, success: bool):
        self._pending_mode = None
        for button in self.flight_mode_buttons:
            button.setEnabled(True)
        if success and mode_name:
            self.set_active_mode(mode_name)

    def _on_task_button(self):
        sender = self.sender()
        requested_task = sender.text()
        sender.setChecked(False)

        answer = QMessageBox.question(
            self,
            "Task Mode Confirmation",
            f"{requested_task} gorev modunu aktif etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            if self.logger:
                self.logger.info(f"Task mode cancelled: {requested_task}")
            return

        if self.logger:
            self.logger.info(f"Task mode confirmed: {requested_task}")

        self.set_active_task_mode(requested_task)
        self.task_mode_requested.emit(requested_task)

    def set_active_mode(self, mode_name: str):
        if not mode_name:
            return

        mode_text = str(mode_name).upper()
        self.active_mode_label.setText(mode_text)

        for button in self.flight_mode_buttons:
            button.setChecked(button.text().upper() == mode_text)

    def set_active_task_mode(self, task_name: str):
        if not task_name:
            return

        task_text = str(task_name).strip()
        import unicodedata
        normalized = unicodedata.normalize("NFKD", task_text.casefold())
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        is_cancel = normalized in ("gorev iptal", "cancel", "iptal")
        self.active_task_label.setText("--" if is_cancel else task_text.upper())

        for button in self.task_mode_buttons:
            button_text = unicodedata.normalize("NFKD", button.text().casefold())
            button_text = "".join(ch for ch in button_text if not unicodedata.combining(ch))
            button.setChecked((not is_cancel) and button_text == normalized)

    def _select_video_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select demo video",
            "",
            "Video Files (*.mp4 *.avi *.mkv);;All Files (*)"
        )
        if path:
            if self.logger:
                self.logger.success(f"Video selected: {path}")
            self.video_source_selected.emit(path)

    def _on_mission_changed(self):
        if self.mission_manager is None:
            return

        mission_items = self.mission_manager.get_map_items()
        self.map_widget.update_waypoints(mission_items)

    def _get_connection_signal_state(self, telemetry: TelemetryData = None):
        if telemetry is not None and not telemetry.connected:
            return "danger"

        if self.last_packet_timestamp is None:
            return "danger"

        delta = time.time() - self.last_packet_timestamp

        if delta < 0.3:
            return "good"
        elif delta < 0.8:
            return "info"
        elif delta < 1.5:
            return "warning"
        else:
            return "danger"

    def _update_connection_signal_badge(self, telemetry: TelemetryData = None):
        state = self._get_connection_signal_state(telemetry)

        if state == "good":
            self.signal_status_label.setText("▂▄▆█ Excellent")
            self.signal_status_label.setStyleSheet("""
                QLabel {
                    color: white;
                    background-color: #1f2b1f;
                    border: 1px solid #2e9d44;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-weight: bold;
                }
            """)
        elif state == "info":
            self.signal_status_label.setText("▂▄▆ Good")
            self.signal_status_label.setStyleSheet("""
                QLabel {
                    color: white;
                    background-color: #141e17;
                    border: 1px solid #577b59;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-weight: bold;
                }
            """)
        elif state == "warning":
            self.signal_status_label.setText("▂▄ Weak")
            self.signal_status_label.setStyleSheet("""
                QLabel {
                    color: white;
                    background-color: #2f2a1a;
                    border: 1px solid #d4a017;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-weight: bold;
                }
            """)
        else:
            self.signal_status_label.setText("▂ Lost")
            self.signal_status_label.setStyleSheet("""
                QLabel {
                    color: white;
                    background-color: #2d1d1d;
                    border: 1px solid #c93c3c;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-weight: bold;
                }
            """)

        if self.last_packet_timestamp is None:
            self._last_signal_state = state
            return

        if state != self._last_signal_state:
            if self.logger:
                if state == "good":
                    self.logger.success("Signal strength: EXCELLENT")
                elif state == "info":
                    self.logger.info("Signal strength: GOOD")
                elif state == "warning":
                    self.logger.warning("Signal strength: WEAK")
                else:
                    self.logger.error("Signal LOST")

            self._last_signal_state = state

    def _add_test_overlays(self):
        if self.shared_map_state is None:
            return

        center_lat = 38.32185
        center_lon = 38.43050

        # BURADA set_initial_view YOK
        self.shared_map_state.set_overlay_markers([
            {"type": "qr", "lat": center_lat, "lon": center_lon, "label": "QR Target"},
            {"type": "enemy", "lat": center_lat + 0.00445, "lon": center_lon - 0.00105, "label": "Enemy 1", "heading": 25},
            {"type": "enemy", "lat": center_lat - 0.00005, "lon": center_lon + 0.01120, "label": "Enemy 2", "heading": 110},
            {"type": "enemy", "lat": center_lat - 0.00475, "lon": center_lon + 0.00370, "label": "Enemy 3", "heading": 210},
        ])

def _flight_tab_referee_status_style(connected: bool) -> str:
    if connected:
        return """
            QLabel {
                color: #6bffa0;
                background-color: #10241a;
                border: 1px solid #2e9d44;
                border-radius: 8px;
                padding: 3px 7px;
                font-weight: 700;
            }
        """
    return """
        QLabel {
            color: #ff8585;
            background-color: #2a1519;
            border: 1px solid #c93c3c;
            border-radius: 8px;
            padding: 3px 7px;
            font-weight: 700;
        }
    """


def _flight_tab_referee_time_style(active: bool) -> str:
    if active:
        return """
            QLabel {
                color: #b4ceac;
                background-color: #213b28;
                border: 1px solid #3b5740;
                border-radius: 8px;
                padding: 3px 7px;
                font-weight: 700;
            }
        """
    return """
        QLabel {
            color: #a1af9c;
            background-color: #141e17;
            border: 1px solid #202c23;
            border-radius: 8px;
            padding: 3px 7px;
            font-weight: 700;
        }
    """


def _flight_tab_create_referee_server_group(self):
    group = QGroupBox("HAKEM SUNUCU")
    group.setObjectName("bluePanel")
    layout = QFormLayout()
    layout.setContentsMargins(9, 14, 9, 8)
    layout.setHorizontalSpacing(7)
    layout.setVerticalSpacing(4)
    layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

    self.ref_ip = QLineEdit()
    self.ref_ip.setPlaceholderText("192.168.1.100")

    self.ref_port = QLineEdit()
    self.ref_port.setPlaceholderText("5000")

    self.ref_team = QLineEdit()
    self.ref_team.setPlaceholderText("Takim No")

    self.ref_password = QLineEdit()
    self.ref_password.setPlaceholderText("Takim Sifresi")
    self.ref_password.setEchoMode(QLineEdit.Password)

    self.ref_status = QLabel("Bağlı değil")
    self.ref_status.setAlignment(Qt.AlignCenter)
    self.ref_status.setStyleSheet(_flight_tab_referee_status_style(False))

    self.ref_server_time = QLabel("--")
    self.ref_server_time.setAlignment(Qt.AlignCenter)
    self.ref_server_time.setStyleSheet(_flight_tab_referee_time_style(False))

    self.ref_btn_connect = QPushButton("Bağlan")
    self.ref_btn_connect.setObjectName("primaryButton")
    self.ref_btn_disconnect = QPushButton("Kes")
    self.ref_btn_disconnect.setObjectName("ghostButton")
    self.ref_btn_disconnect.setEnabled(False)
    self.ref_btn_connect.setMinimumHeight(24)
    self.ref_btn_disconnect.setMinimumHeight(24)
    self.ref_btn_connect.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    self.ref_btn_disconnect.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    self.btn_fetch_qr = QPushButton("QR Koordinatlarını Çek")
    self.btn_fetch_hss = QPushButton("HSS Koordinatlarını Çek")
    self.btn_fetch_qr.setObjectName("railButton")
    self.btn_fetch_hss.setObjectName("railButton")
    self.btn_fetch_qr.setMinimumHeight(24)
    self.btn_fetch_hss.setMinimumHeight(24)
    self.btn_fetch_qr.clicked.connect(self.referee_qr_fetch_requested.emit)
    self.btn_fetch_hss.clicked.connect(self.referee_hss_fetch_requested.emit)

    ref_button_row = QHBoxLayout()
    ref_button_row.setContentsMargins(0, 0, 0, 0)
    ref_button_row.setSpacing(8)
    ref_button_row.addWidget(self.ref_btn_connect)
    ref_button_row.addWidget(self.ref_btn_disconnect)

    layout.addRow("IP:", self.ref_ip)
    layout.addRow("Port:", self.ref_port)
    layout.addRow("Takim:", self.ref_team)
    layout.addRow("Sifre:", self.ref_password)
    layout.addRow("Durum:", self.ref_status)
    layout.addRow(ref_button_row)
    layout.addRow("Sunucu Saati:", self.ref_server_time)
    layout.addRow(self.btn_fetch_qr)
    layout.addRow(self.btn_fetch_hss)

    body = QWidget()
    body.setLayout(layout)
    layout.setAlignment(Qt.AlignTop)
    self.referee_scroll = self._wrap_sidebar_form(group, body)
    self.ref_btn_connect.clicked.connect(self.connect_referee)
    self.ref_btn_disconnect.clicked.connect(self.disconnect_referee)
    return group


def _flight_tab_connect_referee(self):
    ip = self.ref_ip.text().strip()
    port = self.ref_port.text().strip()
    team = self.ref_team.text().strip()
    password = self.ref_password.text().strip()

    if not ip or not port or not team or not password:
        self.set_referee_status(False, "Eksik bilgi")
        return

    self.set_referee_pending()
    self.referee_connect_requested.emit({
        "ip": ip,
        "port": port,
        "team": team,
        "password": password,
    })


def _flight_tab_disconnect_referee(self):
    self.referee_disconnect_requested.emit()


def _flight_tab_set_referee_pending(self):
    # No yellow/intermediate state: red until the health check succeeds.
    self.ref_status.setText("Bağlı değil")
    self.ref_status.setStyleSheet(_flight_tab_referee_status_style(False))
    if hasattr(self, "ref_server_time"):
        self.ref_server_time.setText("--")
        self.ref_server_time.setStyleSheet(_flight_tab_referee_time_style(False))
    self.ref_btn_connect.setEnabled(False)
    self.ref_btn_disconnect.setEnabled(False)


def _flight_tab_set_referee_status(self, connected: bool, text: str = None):
    if not connected and hasattr(self, "teams_widget"):
        self.teams_widget.clear_teams()
    self._referee_status_text = text or ("Connected" if connected else "Bağlı değil")
    self._referee_server_time_text = None
    self.ref_status.setText(text or ("Bağlı" if connected else "Bağlı değil"))
    self.ref_status.setStyleSheet(_flight_tab_referee_status_style(connected))
    if hasattr(self, "ref_server_time"):
        self.ref_server_time.setText("--")
        self.ref_server_time.setStyleSheet(_flight_tab_referee_time_style(False))
    self.ref_btn_connect.setEnabled(not connected)
    self.ref_btn_disconnect.setEnabled(connected)


def _flight_tab_set_referee_server_time(self, server_time_text: str):
    if not getattr(self, "ref_btn_disconnect", None) or not self.ref_btn_disconnect.isEnabled():
        return
    self._referee_server_time_text = server_time_text
    if hasattr(self, "ref_server_time"):
        self.ref_server_time.setText(server_time_text)
        self.ref_server_time.setStyleSheet(_flight_tab_referee_time_style(True))
    self.ref_status.setStyleSheet(_flight_tab_referee_status_style(True))


FlightTab.create_referee_server_group = _flight_tab_create_referee_server_group
FlightTab.connect_referee = _flight_tab_connect_referee
FlightTab.disconnect_referee = _flight_tab_disconnect_referee
FlightTab.set_referee_pending = _flight_tab_set_referee_pending
FlightTab.set_referee_status = _flight_tab_set_referee_status
FlightTab.set_referee_server_time = _flight_tab_set_referee_server_time
