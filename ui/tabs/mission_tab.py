"""
Mission planning tab.

MISSION mode adds and edits route waypoints.
FENCE mode adds and edits circular defense zones.
"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.mission_manager import MissionManager
from models.defense_zone import DefenseZone
from models.mission_item import MissionItemType
from ui.widgets.fence_table import FenceTable
from ui.widgets.map_widget import MapWidget
from ui.widgets.mission_table import MissionTable


class MissionTab(QWidget):
    mission_changed = pyqtSignal()
    mission_upload_requested = pyqtSignal(list, list)
    mission_download_requested = pyqtSignal()

    def __init__(self, mission_manager: MissionManager, shared_map_state=None, parent=None, logger=None):
        super().__init__(parent)
        self.mission_manager = mission_manager
        self.shared_map_state = shared_map_state
        self.logger = logger
        self.selected_sequence = None
        self.selected_zone_index = None
        self.plan_mode = "MISSION"

        self.altitude_spin = None
        self.speed_spin = None
        self.jump_to_spin = None
        self.jump_repeat_spin = None

        self.init_ui()

        if self.mission_manager is not None:
            self.mission_manager.mission_changed.connect(self._on_mission_changed)
            self._on_mission_changed()

        if self.shared_map_state is not None and hasattr(self.shared_map_state, "overlay_changed"):
            self.shared_map_state.overlay_changed.connect(self._refresh_fence_table)
            self._refresh_fence_table()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(10)
        self.setObjectName("cockpitPage")

        toolbar = QFrame()
        toolbar.setObjectName("missionToolbar")
        top_bar = QHBoxLayout(toolbar)
        top_bar.setContentsMargins(12, 10, 12, 10)
        top_bar.setSpacing(10)

        plan_label = QLabel("PLAN")
        plan_label.setObjectName("fieldLabel")
        top_bar.addWidget(plan_label)

        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("missionCombo")
        self.mode_combo.addItem("MISSION", "MISSION")
        self.mode_combo.addItem("FENCE", "FENCE")
        self.mode_combo.currentIndexChanged.connect(self._on_plan_mode_changed)
        top_bar.addWidget(self.mode_combo)

        self.default_fence_radius_m = 50.0
        self.default_fence_radius_spin = QDoubleSpinBox()
        self.default_fence_radius_spin.setRange(1.0, 5000.0)
        self.default_fence_radius_spin.setDecimals(1)
        self.default_fence_radius_spin.setSuffix(" m")
        self.default_fence_radius_spin.setValue(self.default_fence_radius_m)

        top_bar.addStretch()

        self.upload_mission_btn = QPushButton("Send Mission to Pixhawk")
        self.upload_mission_btn.setObjectName("toolButton")
        self.upload_mission_btn.clicked.connect(self._request_mission_upload)
        top_bar.addWidget(self.upload_mission_btn)

        self.download_mission_btn = QPushButton("Read Mission from Pixhawk")
        self.download_mission_btn.setObjectName("toolButton")
        self.download_mission_btn.clicked.connect(self._request_mission_download)
        top_bar.addWidget(self.download_mission_btn)

        main_layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Vertical)
        splitter.setObjectName("missionSplitter")

        self.map_widget = MapWidget(shared_map_state=self.shared_map_state)
        self.map_widget.setObjectName("missionMap")
        self.map_widget.waypoint_clicked.connect(self._on_item_selected)
        self.map_widget.coordinate_clicked.connect(self._add_point_from_map)
        splitter.addWidget(self.map_widget)

        bottom_panel = QWidget()
        bottom_panel.setObjectName("missionBottom")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)

        self.table_stack = QStackedWidget()
        self.table_stack.setObjectName("missionStack")

        self.mission_table = MissionTable()
        self.mission_table.item_selected.connect(self._on_item_selected)
        self.mission_table.item_remove_requested.connect(self._remove_item)
        self.mission_table.item_type_changed.connect(self._change_item_type)
        self.mission_table.item_updated.connect(self._update_item_from_table)
        self.mission_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_stack.addWidget(self.mission_table)

        self.fence_table = FenceTable()
        self.fence_table.zone_selected.connect(self._on_zone_selected)
        self.fence_table.zone_changed.connect(self._update_zone)
        self.fence_table.zone_remove_requested.connect(self._remove_zone)
        self.table_stack.addWidget(self.fence_table)

        bottom_layout.addWidget(self.table_stack, 1)

        splitter.addWidget(bottom_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)
        self._on_plan_mode_changed()

        self.setStyleSheet("""
            #cockpitPage {
                background-color: #090c0a;
                color: #e0e7dc;
            }
            QFrame#missionToolbar {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #141d16, stop:1 #090c0a);
                border: 1px solid #3b5740;
                border-radius: 8px;
            }
            QLabel#fieldLabel {
                color: #a1af9c;
                font-size: 11px;
                font-weight: 700;
            }
            QComboBox#missionCombo, QDoubleSpinBox#missionSpin, QSpinBox {
                background-color: #111712;
                color: #f0f3eb;
                border: 1px solid #2c3b2e;
                border-radius: 5px;
                padding: 8px 10px;
                min-width: 130px;
            }
            QComboBox#missionCombo:focus, QDoubleSpinBox#missionSpin:focus, QSpinBox:focus {
                border-color: #577b59;
            }
            QPushButton#toolButton {
                background-color: #111712;
                border: 1px solid #2c3b2e;
                border-radius: 5px;
                color: #f0f3eb;
                padding: 9px 16px;
                font-weight: 700;
            }
            QPushButton#toolButton:hover {
                border-color: #577b59;
                background-color: #1b2a1e;
            }
            QWidget#missionBottom, QStackedWidget#missionStack {
                background-color: transparent;
            }
            QGroupBox#bluePanel {
                background-color: rgba(5, 13, 22, 230);
                border: 1px solid #3b5740;
                border-radius: 8px;
                margin-top: 14px;
                color: #7ea783;
                font-weight: 800;
            }
            QGroupBox#bluePanel::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QSplitter::handle {
                background-color: #0e140f;
            }
        """)

    def _on_plan_mode_changed(self):
        self.plan_mode = self.mode_combo.currentData() or "MISSION"
        is_fence = self.plan_mode == "FENCE"
        self.table_stack.setCurrentIndex(1 if is_fence else 0)
        if self.logger:
            self.logger.info(f"Plan mode changed: {self.plan_mode}")

    def _get_zones(self):
        if self.shared_map_state is not None and hasattr(self.shared_map_state, "defense_zones"):
            return list(self.shared_map_state.defense_zones)
        if hasattr(self.map_widget, "_get_defense_zones"):
            return list(self.map_widget._get_defense_zones())
        return []

    def _refresh_fence_table(self):
        if hasattr(self, "fence_table"):
            self.fence_table.update_zones(self._get_zones())

    def add_defense_zone(self):
        self._add_defense_zone_at(self.map_widget.center_lat, self.map_widget.center_lon)

    def _add_defense_zone_at(self, latitude: float, longitude: float):
        radius = float(
            self.default_fence_radius_spin.value()
            if hasattr(self, "default_fence_radius_spin")
            else getattr(self, "default_fence_radius_m", 50.0)
        )
        zone = DefenseZone(
            center_lat=float(latitude),
            center_lon=float(longitude),
            radius_m=radius,
            name=f"Hava Savunma {len(self._get_zones()) + 1}",
            frame="Relative",
        )

        if self.shared_map_state is not None and hasattr(self.shared_map_state, "add_defense_zone"):
            self.shared_map_state.add_defense_zone(zone)
        else:
            self.map_widget.add_defense_zone(zone)

        self.selected_zone_index = len(self._get_zones()) - 1
        self._refresh_fence_table()
        self.fence_table.select_zone(self.selected_zone_index)
        if self.logger:
            self.logger.success(
                f"Defense zone added: lat={zone.center_lat:.6f}, lon={zone.center_lon:.6f}, radius={zone.radius_m:.1f}m"
            )

    def remove_last_zone(self):
        if self.shared_map_state is not None and hasattr(self.shared_map_state, "remove_last_defense_zone"):
            self.shared_map_state.remove_last_defense_zone()
        elif hasattr(self.map_widget, "remove_last_defense_zone"):
            self.map_widget.remove_last_defense_zone()
        self.selected_zone_index = None
        self._refresh_fence_table()

    def clear_defense_zones(self):
        if self.shared_map_state is not None and hasattr(self.shared_map_state, "clear_defense_zones"):
            self.shared_map_state.clear_defense_zones()
        elif hasattr(self.map_widget, "clear_defense_zones"):
            self.map_widget.clear_defense_zones()
        self.selected_zone_index = None
        self._refresh_fence_table()

    def _on_zone_selected(self, index: int):
        self.selected_zone_index = index

    def _update_zone(self, index: int, updates: dict):
        if self.shared_map_state is not None and hasattr(self.shared_map_state, "update_defense_zone"):
            self.shared_map_state.update_defense_zone(index, **updates)
        elif 0 <= index < len(self.map_widget.defense_zones):
            zone = self.map_widget.defense_zones[index]
            for key, value in updates.items():
                if hasattr(zone, key):
                    setattr(zone, key, value)
            self.map_widget.update()
        self._refresh_fence_table()

    def _remove_zone(self, index: int):
        if self.shared_map_state is not None and hasattr(self.shared_map_state, "remove_defense_zone"):
            self.shared_map_state.remove_defense_zone(index)
        elif 0 <= index < len(self.map_widget.defense_zones):
            self.map_widget.defense_zones.pop(index)
            self.map_widget.update()
        self.selected_zone_index = None
        self._refresh_fence_table()

    def _request_mission_upload(self):
        if self.mission_manager is None:
            return

        items = self.mission_manager.get_all_items()
        zones = [
            zone
            for zone in self._get_zones()
            if bool(getattr(zone, "is_active", True))
        ]
        if not items:
            if self.logger:
                self.logger.warning("Mission upload requested with empty list; Pixhawk mission will be cleared")

        if self.logger:
            self.logger.info(f"Mission upload requested: {len(items)} items, {len(zones)} fence zones")
        self.mission_upload_requested.emit(items, zones)

    def _request_mission_download(self):
        if self.logger:
            self.logger.info("Mission download requested")
        self.mission_download_requested.emit()

    def fit_mission_on_map(self):
        if hasattr(self.map_widget, "fit_to_waypoints"):
            self.map_widget.fit_to_waypoints()

    def _add_point_from_map(self, latitude: float, longitude: float):
        if self.plan_mode == "FENCE":
            self._add_defense_zone_at(latitude, longitude)
            return

        if self.mission_manager is None:
            return

        item = self.mission_manager.add_item(
            item_type=MissionItemType.WAYPOINT,
            latitude=latitude,
            longitude=longitude,
            altitude=50.0,
            speed=10.0,
        )

        if item:
            self.selected_sequence = item.sequence
            self._on_item_selected(item.sequence)
            if self.logger:
                self.logger.success(
                    f"Waypoint added: seq={item.sequence}, lat={latitude:.6f}, lon={longitude:.6f}"
                )

    def _change_item_type(self, sequence: int, item_type: MissionItemType):
        if self.mission_manager is None:
            return

        item = self.mission_manager.get_item(sequence)
        if not item:
            return

        updates = {"item_type": item_type}
        if item_type == MissionItemType.DO_JUMP:
            params = dict(item.parameters or {})
            params.setdefault("jump_to", 0)
            params.setdefault("repeat", 1)
            updates["parameters"] = params
            updates["latitude"] = None
            updates["longitude"] = None
            updates["altitude"] = 0.0
        elif item_type == MissionItemType.DO_LAND_START:
            updates["latitude"] = None
            updates["longitude"] = None
            updates["altitude"] = 0.0
        elif item_type in (MissionItemType.WAYPOINT, MissionItemType.TAKEOFF, MissionItemType.LAND):
            updates.setdefault("altitude", item.altitude if item.altitude is not None else 50.0)
            if item.latitude is None or item.longitude is None:
                updates["latitude"] = self.map_widget.center_lat
                updates["longitude"] = self.map_widget.center_lon

        self.mission_manager.update_item(sequence, **updates)
        if self.logger:
            self.logger.info(f"Mission item type changed: seq={sequence}, type={item_type}")

    def _update_item_from_table(self, sequence: int, updates: dict):
        if self.mission_manager is None:
            return
        if self.mission_manager.update_item(sequence, **updates) and self.logger:
            self.logger.info(f"Mission item updated from table: seq={sequence}, fields={list(updates.keys())}")

    def _on_mission_changed(self):
        if self.mission_manager is None:
            return

        items = self.mission_manager.get_all_items()
        self.mission_table.update_mission(items)
        self.map_widget.update_waypoints(self.mission_manager.get_map_items())
        self._refresh_fence_table()
        self.mission_changed.emit()

    def _on_item_selected(self, sequence: int):
        self.selected_sequence = sequence
        self.mode_combo.setCurrentIndex(0)
        self.mission_table.select_sequence(sequence)

    def _remove_item(self, sequence: int):
        if self.mission_manager is None:
            return

        if self.mission_manager.remove_item(sequence):
            self.selected_sequence = None
            if self.logger:
                self.logger.warning(f"Mission item removed: seq={sequence}")
