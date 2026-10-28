import time
import unittest
from types import SimpleNamespace

from PyQt5.QtCore import QCoreApplication

from backend.telemetry.manager import TelemetryManager
from backend.telemetry.mavlink_backend import MavlinkTelemetryBackend
from backend.telemetry.simulation_backend import SimulationTelemetryBackend
from core.telemetry_worker import TelemetryWorker
from models.mission_item import MissionItem, MissionItemType


class TelemetryBackendSmokeTest(unittest.TestCase):
    def test_simulation_backend_produces_data(self):
        backend = SimulationTelemetryBackend()
        backend.start()
        try:
            data = backend.read(timeout=0.1)
        finally:
            backend.stop()

        self.assertIsNotNone(data)
        self.assertTrue(data.connected)
        self.assertIsNotNone(data.latitude)
        self.assertIsNotNone(data.longitude)
        self.assertGreater(data.battery, 0)

    def test_manager_can_switch_backend(self):
        manager = TelemetryManager()
        manager.connect({"type": "Demo"})
        try:
            self.assertTrue(manager.connected)
            self.assertIsInstance(manager.backend, SimulationTelemetryBackend)
            data = manager.read(timeout=0.1)
            self.assertIsNotNone(data)
        finally:
            manager.disconnect()

        self.assertFalse(manager.connected)

    def test_udp_uses_bidirectional_python_backend_for_flight_commands(self):
        manager = TelemetryManager()

        backend = manager._create_backend({"type": "UDP", "target": "0.0.0.0:14550", "baud": ""})

        self.assertIsInstance(backend, MavlinkTelemetryBackend)

    def test_manager_can_send_mode_change(self):
        manager = TelemetryManager()
        manager.connect({"type": "Demo"})
        try:
            manager.set_mode("RTL")
            data = manager.read(timeout=0.1)
            self.assertEqual(data.mode, "RTL")
        finally:
            manager.disconnect()

    def test_mavlink_mode_change_matches_mission_planner_and_waits_for_heartbeat(self):
        command_calls = []
        set_mode_calls = []
        mav = SimpleNamespace(
            MAV_CMD_DO_SET_MODE=176,
            MAV_MODE_FLAG_CUSTOM_MODE_ENABLED=1,
            command_long_send=lambda *args: command_calls.append(args),
            set_mode_send=lambda *args: set_mode_calls.append(args),
        )
        backend = MavlinkTelemetryBackend("Serial", "COM_TEST", 57600)
        backend.master = SimpleNamespace(
            target_system=7,
            target_component=1,
            mode_mapping=lambda: {"MANUAL": 0, "AUTO": 10},
            flightmode="MANUAL",
            mav=mav,
        )
        backend._mavutil = SimpleNamespace(mavlink=mav)
        backend._send_gcs_heartbeat = lambda: None
        confirmations = []
        backend._wait_for_mode = lambda mode, timeout: confirmations.append((mode, timeout)) or True

        result = backend.set_mode("Auto")

        self.assertEqual(result["mode"], "AUTO")
        self.assertEqual(command_calls[0][2], 176)
        self.assertEqual(command_calls[0][4], 1.0)
        self.assertEqual(command_calls[0][5], 10.0)
        self.assertEqual(set_mode_calls, [(7, 1, 10), (7, 1, 10)])
        self.assertEqual(confirmations, [("AUTO", 5.0)])

    def test_mavlink_mode_change_rejects_unsupported_mode_without_transmitting(self):
        command_calls = []
        mav = SimpleNamespace(
            MAV_CMD_DO_SET_MODE=176,
            MAV_MODE_FLAG_CUSTOM_MODE_ENABLED=1,
            command_long_send=lambda *args: command_calls.append(args),
            set_mode_send=lambda *args: command_calls.append(args),
        )
        backend = MavlinkTelemetryBackend("Serial", "COM_TEST", 57600)
        backend.master = SimpleNamespace(
            target_system=7,
            target_component=1,
            mode_mapping=lambda: {"MANUAL": 0, "AUTO": 10},
            flightmode="MANUAL",
            mav=mav,
        )
        backend._mavutil = SimpleNamespace(mavlink=mav)
        backend._send_gcs_heartbeat = lambda: None

        with self.assertRaises(ValueError):
            backend.set_mode("LAND")

        self.assertEqual(command_calls, [])

    def test_mavlink_mode_wait_raises_on_pixhawk_rejection(self):
        ack = SimpleNamespace(get_type=lambda: "COMMAND_ACK", command=176, result=4)
        mav = SimpleNamespace(
            MAV_CMD_DO_SET_MODE=176,
            MAV_RESULT_ACCEPTED=0,
            MAV_RESULT_IN_PROGRESS=5,
        )
        backend = MavlinkTelemetryBackend("Serial", "COM_TEST", 57600)
        backend.master = SimpleNamespace(recv_match=lambda **_kwargs: ack, flightmode="MANUAL")
        backend._mavutil = SimpleNamespace(mavlink=mav)
        backend._apply_message = lambda _msg: None

        with self.assertRaisesRegex(RuntimeError, "COMMAND_ACK=4"):
            backend._wait_for_mode("AUTO", timeout=0.1)

    def test_simulation_guided_target_changes_mode_and_moves_to_target(self):
        manager = TelemetryManager()
        manager.connect({"type": "Demo"})
        try:
            first = manager.read(timeout=0.1)
            target_lat = first.latitude + 0.001
            target_lon = first.longitude + 0.001
            result = manager.goto_guided(target_lat, target_lon, 80.0)
            second = manager.read(timeout=0.1)
        finally:
            manager.disconnect()

        self.assertEqual(result["mode"], "GUIDED")
        self.assertEqual(second.mode, "GUIDED")
        self.assertGreater(second.latitude, first.latitude)
        self.assertGreater(second.longitude, first.longitude)

    def test_arduplane_guided_target_uses_current_two_waypoint_and_ack(self):
        calls = []
        ack = SimpleNamespace(get_type=lambda: "MISSION_ACK", type=0)
        mav = SimpleNamespace(
            MAV_FRAME_GLOBAL_RELATIVE_ALT=3,
            MAV_FRAME_GLOBAL_RELATIVE_ALT_INT=6,
            MAV_CMD_NAV_WAYPOINT=16,
            MAV_MISSION_TYPE_MISSION=0,
            MAV_MISSION_ACCEPTED=0,
            mission_item_int_send=lambda *args: calls.append(args),
        )
        backend = MavlinkTelemetryBackend("Serial", "COM_TEST", 57600)
        backend.master = SimpleNamespace(
            target_system=7,
            target_component=1,
            mode_mapping=lambda: {"GUIDED": 15},
            mav=mav,
            recv_match=lambda **_kwargs: ack,
        )
        backend._mavutil = SimpleNamespace(mavlink=mav)
        backend._vehicle_type = 1
        backend.set_mode = lambda mode: self.assertEqual(mode, "GUIDED")
        backend._wait_for_mode = lambda mode, timeout: mode == "GUIDED"

        result = backend.goto_guided(38.3201, 38.4302, 75.0)

        self.assertEqual(result["protocol"], "MISSION_ITEM_INT current=2 + MISSION_ACK")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][3], 3)
        self.assertEqual(calls[0][5], 2)
        self.assertEqual(calls[0][6], 0)
        self.assertEqual(calls[0][11], int(round(38.3201 * 1e7)))
        self.assertEqual(calls[0][12], int(round(38.4302 * 1e7)))
        self.assertEqual(calls[0][13], 75.0)

    def test_arduplane_missing_mission_ack_uses_stateless_fallbacks(self):
        mission_calls = []
        reposition_calls = []
        position_calls = []
        mav = SimpleNamespace(
            MAV_FRAME_GLOBAL_RELATIVE_ALT=3,
            MAV_FRAME_GLOBAL_RELATIVE_ALT_INT=6,
            MAV_CMD_NAV_WAYPOINT=16,
            MAV_CMD_DO_REPOSITION=192,
            MAV_MISSION_TYPE_MISSION=0,
            MAV_MISSION_ACCEPTED=0,
            mission_item_int_send=lambda *args: mission_calls.append(args),
            command_int_send=lambda *args: reposition_calls.append(args),
            set_position_target_global_int_send=lambda *args: position_calls.append(args),
        )
        backend = MavlinkTelemetryBackend("Serial", "COM_TEST", 57600)
        backend.master = SimpleNamespace(
            target_system=7,
            target_component=1,
            mode_mapping=lambda: {"GUIDED": 15},
            mav=mav,
        )
        backend._mavutil = SimpleNamespace(mavlink=mav)
        backend._vehicle_type = 1
        backend.set_mode = lambda _mode: None
        backend._wait_for_mode = lambda _mode, timeout: True
        backend._wait_for_guided_mission_ack = lambda timeout: False

        result = backend.goto_guided(38.3201, 38.4302, 75.0)

        self.assertIn("DO_REPOSITION", result["protocol"])
        self.assertEqual(len(mission_calls), 1)
        self.assertEqual(len(reposition_calls), 1)
        self.assertEqual(len(position_calls), 1)
        self.assertEqual(reposition_calls[0][3], 192)
        self.assertEqual(position_calls[0][3], 3)

    def test_copter_guided_target_uses_global_position_target(self):
        calls = []
        mav = SimpleNamespace(
            MAV_FRAME_GLOBAL_RELATIVE_ALT_INT=6,
            MAV_CMD_NAV_WAYPOINT=16,
            MAV_MISSION_TYPE_MISSION=0,
            MAV_MISSION_ACCEPTED=0,
            set_position_target_global_int_send=lambda *args: calls.append(args),
        )
        backend = MavlinkTelemetryBackend("Serial", "COM_TEST", 57600)
        backend.master = SimpleNamespace(
            target_system=7,
            target_component=1,
            mode_mapping=lambda: {"GUIDED": 4},
            mav=mav,
        )
        backend._mavutil = SimpleNamespace(mavlink=mav)
        backend._vehicle_type = 2
        backend.set_mode = lambda mode: self.assertEqual(mode, "GUIDED")
        backend._wait_for_mode = lambda mode, timeout: mode == "GUIDED"

        result = backend.goto_guided(38.3201, 38.4302, 45.0)

        self.assertEqual(result["protocol"], "SET_POSITION_TARGET_GLOBAL_INT")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][4], 3576)
        self.assertEqual(calls[0][5], int(round(38.3201 * 1e7)))
        self.assertEqual(calls[0][6], int(round(38.4302 * 1e7)))
        self.assertEqual(calls[0][7], 45.0)

    def test_manager_can_upload_mission(self):
        manager = TelemetryManager()
        manager.connect({"type": "Demo"})
        try:
            manager.upload_mission([
                MissionItem(
                    item_type=MissionItemType.WAYPOINT,
                    sequence=0,
                    latitude=38.32,
                    longitude=38.43,
                    altitude=60,
                )
            ])
        finally:
            manager.disconnect()

    def test_manager_can_write_simulation_parameters(self):
        manager = TelemetryManager()
        manager.connect({"type": "Demo"})
        try:
            result = manager.write_parameters([
                {"name": "ARSPD_USE", "value": 1.0, "type": 6}
            ])
        finally:
            manager.disconnect()

        self.assertEqual(result["failed"], [])
        self.assertEqual(result["written"][0]["name"], "ARSPD_USE")
        self.assertEqual(result["written"][0]["value"], 1.0)

    def test_mavlink_parameter_write_sends_param_set_and_verifies_echo(self):
        calls = []
        backend = MavlinkTelemetryBackend("Serial", "COM_TEST", 57600)
        backend.master = SimpleNamespace(
            target_system=7,
            target_component=1,
            mav=SimpleNamespace(param_set_send=lambda *args: calls.append(args)),
        )
        backend._mavutil = SimpleNamespace(
            mavlink=SimpleNamespace(MAV_PARAM_TYPE_REAL32=9)
        )
        backend._send_gcs_heartbeat = lambda: None
        backend._drain_mavlink_messages = lambda *_args, **_kwargs: None
        backend._wait_parameter_value = lambda name, timeout=2.0: 1.0

        result = backend.write_parameters([
            {"name": "ARSPD_USE", "value": 1.0, "type": 6}
        ])

        self.assertEqual(calls, [(7, 1, b"ARSPD_USE", 1.0, 6)])
        self.assertEqual(result["failed"], [])
        self.assertEqual(result["written"][0]["value"], 1.0)

    def test_worker_starts_and_stops(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        worker = TelemetryWorker(autostart_simulation=True)
        worker.start()
        deadline = time.time() + 1.5
        try:
            while time.time() < deadline and not worker.manager.connected:
                app.processEvents()
                time.sleep(0.02)
            self.assertTrue(worker.manager.connected)
        finally:
            worker.stop()

        self.assertFalse(worker.isRunning())

    def test_worker_can_start_truly_disconnected(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        worker = TelemetryWorker(autostart_simulation=False)
        worker.start()
        try:
            deadline = time.time() + 0.3
            while time.time() < deadline:
                app.processEvents()
                time.sleep(0.01)
            self.assertIsNone(worker.manager.backend)
            self.assertFalse(worker.connected)
        finally:
            worker.stop()

        self.assertFalse(worker.isRunning())


if __name__ == "__main__":
    unittest.main()
