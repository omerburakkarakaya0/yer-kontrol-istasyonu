import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from core.mission_manager import MissionManager
from core.communication_core_worker import CommunicationCoreStatusWorker
from core.referee_telemetry import extract_opponent_positions
from models.mission_item import MissionItemType
from ui.tabs.analysis_tab import OpponentAnalysisWidget
from ui.tabs.live_analysis_tab import AnalysisTab
from ui.main_window import MainWindow


class AnalysisIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _sample(team, lat, lon, altitude=60.0):
        return {
            "takim_numarasi": team,
            "iha_enlem": lat,
            "iha_boylam": lon,
            "iha_irtifa": altitude,
            "iha_hiz": 18.0,
            "iha_yonelme": 90.0,
        }

    def test_live_update_preserves_selected_opponent(self):
        widget = OpponentAnalysisWidget()
        widget.update_from_referee_telemetry([
            self._sample(2, 38.3200, 38.4300),
            self._sample(4, 38.3210, 38.4310),
        ])
        widget.opponent_list.setCurrentRow(1)

        widget.update_from_referee_telemetry([
            self._sample(2, 38.3201, 38.4301),
            self._sample(4, 38.3211, 38.4311),
        ])

        selected = widget.opponent_list.currentItem()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.data(Qt.UserRole), "4")

    def test_live_history_appends_and_survives_transient_empty_updates(self):
        widget = OpponentAnalysisWidget()
        first = self._sample(2, 38.3200, 38.4300)
        second = self._sample(2, 38.3205, 38.4305)

        widget.update_from_referee_telemetry([first])
        widget.update_from_referee_telemetry([])
        widget.update_from_referee_telemetry([second])
        widget.update_from_referee_telemetry([second])

        self.assertEqual(len(widget.opponents), 1)
        self.assertEqual(len(widget.opponents[0]["telemetry"]), 2)
        self.assertEqual(widget.opponents[0]["route"], [
            (38.3200, 38.4300),
            (38.3205, 38.4305),
        ])

    def test_nested_referee_payload_keeps_all_thirty_opponents(self):
        positions = [
            self._sample(team, 38.3200 + team * 0.0001, 38.4300 + team * 0.0001)
            for team in range(1, 31)
        ]
        payload = {"konumBilgileri": positions, "total": 30}
        widget = OpponentAnalysisWidget()

        widget.update_from_referee_telemetry(payload)

        self.assertEqual(len(widget.opponents), 30)
        self.assertEqual(widget.opponent_list.count(), 30)
        self.assertEqual(len(widget.analysis_payload()), 30)

    def test_team_keyed_referee_payload_keeps_all_opponents(self):
        payload = {
            "opponent_positions": {
                str(team): {
                    "iha_enlem": 38.3200 + team * 0.0001,
                    "iha_boylam": 38.4300 + team * 0.0001,
                    "iha_irtifa": 60.0,
                }
                for team in range(1, 31)
            }
        }

        positions = extract_opponent_positions(payload)

        self.assertEqual(len(positions), 30)
        self.assertEqual({str(item["takim_numarasi"]) for item in positions}, {str(i) for i in range(1, 31)})

    def test_live_3d_payload_contains_every_referee_opponent(self):
        positions = [
            self._sample(team, 38.3200 + team * 0.0001, 38.4300 + team * 0.0001)
            for team in range(1, 31)
        ]
        tab = AnalysisTab(mission_manager=MissionManager())
        tab.set_vehicle_analysis_enabled(True)
        tab.update_referee_telemetry({"rakip_iha_konumlari": positions})

        payload = tab._build_analysis_payload()

        self.assertTrue(payload["analysis_active"])
        self.assertEqual(len(payload["opponents"]), 30)

    def test_full_referee_snapshot_replaces_three_item_api_subset(self):
        status = {
            "opponent_positions": [
                self._sample(team, 38.32, 38.43) for team in (2, 3, 4)
            ]
        }
        snapshot = {
            "takimlar": {
                str(team): self._sample(
                    team,
                    38.3200 + team * 0.0001,
                    38.4300 + team * 0.0001,
                )
                for team in range(1, 31)
            }
        }

        merged = CommunicationCoreStatusWorker.merge_referee_snapshot(status, snapshot)

        self.assertEqual(len(merged["opponent_positions"]), 30)
        self.assertEqual(merged["opponent_positions_source"], "hakem_veri")

    def test_main_window_forwards_referee_status_to_analysis(self):
        status = {
            "server_time": {"saat": 10, "dakika": 28, "saniye": 46},
            "opponent_positions": [
                self._sample(team, 38.32 + team * 0.0001, 38.43)
                for team in range(1, 31)
            ],
            "hss_coordinates": [],
        }
        window = SimpleNamespace(
            analysis_tab=Mock(),
            flight_tab=Mock(),
            _update_referee_server_time=Mock(),
            _apply_referee_map_overlays=Mock(),
            _apply_referee_hss_zones=Mock(),
        )

        MainWindow._on_communication_core_status(window, status)

        window.analysis_tab.update_referee_telemetry.assert_called_once_with(status)
        window.flight_tab.update_referee_teams.assert_called_once_with(status)

    def test_main_window_disconnect_clears_analysis_tracks(self):
        window = SimpleNamespace(
            communication_core_worker=Mock(),
            analysis_tab=Mock(),
            flight_tab=Mock(),
            logger=Mock(),
            _telemetry_analysis_connected=False,
            _referee_analysis_connected=True,
            _last_referee_telemetry_push=1.0,
            _referee_telemetry_push_inflight=True,
            _referee_qr_display_enabled=True,
            _referee_hss_display_enabled=True,
            _stop_communication_core_status_worker=Mock(),
            _stop_referee_video_stream=Mock(),
            _stop_communication_core=Mock(),
            _sync_live_analysis_enabled=Mock(),
        )

        MainWindow._on_referee_disconnect_requested(window)

        window.communication_core_worker.set_referee_base_url.assert_called_once_with("")
        window.analysis_tab.clear_referee_telemetry.assert_called_once_with()
        self.assertFalse(window._referee_analysis_connected)
        window._sync_live_analysis_enabled.assert_called_once_with()

    def test_main_window_enables_3d_analysis_for_either_live_connection(self):
        analysis_tab = Mock()
        window = SimpleNamespace(
            analysis_tab=analysis_tab,
            _telemetry_analysis_connected=False,
            _referee_analysis_connected=True,
        )

        MainWindow._sync_live_analysis_enabled(window)
        analysis_tab.set_vehicle_analysis_enabled.assert_called_once_with(True)

        analysis_tab.reset_mock()
        window._referee_analysis_connected = False
        MainWindow._sync_live_analysis_enabled(window)
        analysis_tab.set_vehicle_analysis_enabled.assert_called_once_with(False)

    def test_mission_waypoints_are_exported_with_altitude(self):
        manager = MissionManager()
        manager.add_item(
            MissionItemType.WAYPOINT,
            latitude=38.3200,
            longitude=38.4300,
            altitude=45.0,
            speed=12.0,
        )
        manager.add_item(
            MissionItemType.WAYPOINT,
            latitude=38.3220,
            longitude=38.4340,
            altitude=80.0,
            speed=15.0,
        )
        tab = AnalysisTab(mission_manager=manager)

        payload = tab._mission_payload()

        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["altitude"], 45.0)
        self.assertEqual(payload[1]["speed"], 15.0)

    def test_demo_telemetry_is_blocked_until_real_vehicle_is_enabled(self):
        manager = MissionManager()
        manager.add_item(
            MissionItemType.WAYPOINT,
            latitude=38.3200,
            longitude=38.4300,
            altitude=50.0,
            speed=10.0,
        )
        tab = AnalysisTab(mission_manager=manager)
        telemetry = SimpleNamespace(
            latitude=38.321,
            longitude=38.431,
            altitude=60.0,
            speed=15.0,
            safe_yaw=90.0,
            safe_pitch=1.0,
            safe_roll=2.0,
            battery=95.0,
        )

        tab.update_own_telemetry(telemetry)
        inactive_payload = tab._build_analysis_payload()
        self.assertFalse(inactive_payload["analysis_active"])
        self.assertEqual(inactive_payload["mission"], [])
        self.assertIsNone(inactive_payload["ownship"])

        tab.set_vehicle_analysis_enabled(True)
        tab.update_own_telemetry(telemetry)
        active_payload = tab._build_analysis_payload()
        self.assertTrue(active_payload["analysis_active"])
        self.assertEqual(len(active_payload["mission"]), 1)
        self.assertEqual(len(active_payload["ownship"]["telemetry"]), 1)

        tab.set_vehicle_analysis_enabled(False)
        self.assertEqual(tab._own_track, [])


if __name__ == "__main__":
    unittest.main()
