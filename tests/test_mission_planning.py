import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import config
from backend.telemetry.simulation_backend import SimulationTelemetryBackend
from backend.telemetry.mavlink_backend import MavlinkTelemetryBackend
from core.mission_manager import MissionManager
from core.shared_map_state import SharedMapState
from models.defense_zone import DefenseZone
from models.mission_item import MissionItemType
from ui.tabs.mission_tab import MissionTab


class MissionPlanningTest(unittest.TestCase):
    def setUp(self):
        self._old_defense_path = getattr(config, "DEFENSE_ZONES_PATH", None)
        self._tmpdir = tempfile.TemporaryDirectory()
        config.DEFENSE_ZONES_PATH = os.path.join(self._tmpdir.name, "defense_zones.json")
        self.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        if self._old_defense_path is not None:
            config.DEFENSE_ZONES_PATH = self._old_defense_path
        self._tmpdir.cleanup()

    def test_mission_and_fence_modes_add_expected_items(self):
        manager = MissionManager()
        state = SharedMapState()
        tab = MissionTab(manager, shared_map_state=state)

        tab.mode_combo.setCurrentIndex(0)
        tab._add_point_from_map(38.3311, 38.4399)
        tab._add_point_from_map(38.3322, 38.4401)

        self.assertEqual(len(manager.get_all_items()), 2)
        self.assertEqual(tab.mission_table.table.rowCount(), 2)

        tab.mode_combo.setCurrentIndex(1)
        tab.default_fence_radius_spin.setValue(80.0)
        tab._add_point_from_map(38.3314819, 38.4398693)

        self.assertEqual(len(state.defense_zones), 1)
        self.assertEqual(tab.fence_table.table.rowCount(), 1)
        self.assertAlmostEqual(state.defense_zones[0].radius_m, 80.0)

        tab._update_zone(0, {"radius_m": 50.0, "name": "Hava Savunma Test"})
        self.assertAlmostEqual(state.defense_zones[0].radius_m, 50.0)
        self.assertEqual(state.defense_zones[0].name, "Hava Savunma Test")

    def test_simulation_backend_round_trips_planned_mission(self):
        manager = MissionManager()
        manager.add_item(
            item_type=MissionItemType.WAYPOINT,
            latitude=38.3311,
            longitude=38.4399,
            altitude=50.0,
            speed=10.0,
        )
        manager.add_item(
            item_type=MissionItemType.WAYPOINT,
            latitude=38.3322,
            longitude=38.4401,
            altitude=60.0,
            speed=12.0,
        )

        backend = SimulationTelemetryBackend()
        backend.start()
        try:
            backend.upload_mission(manager.get_all_items())
            downloaded = backend.download_mission()
        finally:
            backend.stop()

        self.assertEqual(len(downloaded), 2)
        self.assertAlmostEqual(downloaded[0].latitude, 38.3311)
        self.assertAlmostEqual(downloaded[1].longitude, 38.4401)

    def test_empty_mission_upload_clears_backend_mission(self):
        manager = MissionManager()
        manager.add_item(
            item_type=MissionItemType.WAYPOINT,
            latitude=38.3311,
            longitude=38.4399,
            altitude=50.0,
            speed=10.0,
        )

        backend = SimulationTelemetryBackend()
        backend.start()
        try:
            backend.upload_mission(manager.get_all_items())
            self.assertEqual(len(backend.download_mission()), 1)
            backend.upload_mission([])
            self.assertEqual(backend.download_mission(), [])
        finally:
            backend.stop()

    def test_download_keeps_first_real_ardupilot_waypoint(self):
        backend = MavlinkTelemetryBackend("Serial", "COM7")
        backend._mavutil = SimpleNamespace(
            mavlink=SimpleNamespace(
                MAV_FRAME_GLOBAL=0,
                MAV_CMD_NAV_WAYPOINT=16,
                MAV_CMD_NAV_TAKEOFF=22,
                MAV_CMD_NAV_LAND=21,
                MAV_CMD_NAV_RETURN_TO_LAUNCH=20,
                MAV_CMD_DO_LAND_START=189,
                MAV_CMD_DO_JUMP=177,
            )
        )
        msg = SimpleNamespace(
            get_type=lambda: "MISSION_ITEM_INT",
            seq=0,
            frame=0,
            command=16,
            x=383279148,
            y=384446099,
            z=50.0,
        )

        item = backend._mavlink_message_to_mission_item(msg)

        self.assertIsNotNone(item)
        self.assertEqual(item.sequence, 0)
        self.assertAlmostEqual(item.latitude, 38.3279148)
        self.assertAlmostEqual(item.longitude, 38.4446099)

    def test_fence_zone_converts_to_mavlink_circle_exclusion(self):
        backend = MavlinkTelemetryBackend("Serial", "COM7")
        backend._mavutil = SimpleNamespace(
            mavlink=SimpleNamespace(
                MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION=5004,
                MAV_FRAME_GLOBAL_INT=5,
            )
        )
        zones = [
            DefenseZone(center_lat=38.3314819, center_lon=38.4398693, radius_m=50.0),
            DefenseZone(center_lat=38.0, center_lon=38.0, radius_m=100.0, is_active=False),
        ]

        items = backend._build_mavlink_fence_items(zones)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["command"], 5004)
        self.assertEqual(items[0]["frame"], 5)
        self.assertEqual(items[0]["param1"], 50.0)
        self.assertEqual(items[0]["x"], 383314819)
        self.assertEqual(items[0]["y"], 384398693)


if __name__ == "__main__":
    unittest.main()
