import math
import os
import time
from typing import Optional

from backend.telemetry.base import TelemetryBackend, TelemetryLogCallback
from models.defense_zone import DefenseZone
from models.mission_item import MissionItem, MissionItemType
from models.telemetry import TelemetryData


class MavlinkTelemetryBackend(TelemetryBackend):
    def __init__(
        self,
        connection_type: str,
        target: str,
        baud: Optional[int] = None,
        log_callback: Optional[TelemetryLogCallback] = None,
    ):
        super().__init__(log_callback)
        self.connection_type = (connection_type or "UDP").upper()
        self.target = target or ""
        self.baud = baud
        self.master = None
        self._last_data = TelemetryData(connected=False)
        self._last_msg_time = 0.0
        self._mavutil = None
        self._last_status_text = None
        self._vehicle_type = None

    def start(self):
        try:
            os.environ.setdefault("MAVLINK20", "1")
            from pymavlink import mavutil
        except ImportError as exc:
            raise RuntimeError("pymavlink is not installed. Run: pip install pymavlink") from exc

        self._mavutil = mavutil
        connection_string = self._build_connection_string()
        self.log("INFO", f"Opening MAVLink connection: {connection_string}")

        kwargs = {"source_system": 255, "source_component": 190}
        if self.connection_type == "SERIAL" and self.baud:
            kwargs["baud"] = self.baud

        try:
            self.master = mavutil.mavlink_connection(connection_string, autoreconnect=True, **kwargs)
        except Exception as exc:
            if self.connection_type == "SERIAL":
                raise RuntimeError(
                    f"Could not open serial port {connection_string}. "
                    "Close Mission Planner or any other program using this COM port, then try again."
                ) from exc
            raise
        heartbeat = self._wait_autopilot_heartbeat(timeout=8)
        if heartbeat is None:
            raise TimeoutError("No autopilot MAVLink heartbeat received within 8 seconds")
        self.connected = True
        self._vehicle_type = int(getattr(heartbeat, "type", 0) or 0)
        self._last_msg_time = time.time()
        self.log(
            "SUCCESS",
            f"MAVLink autopilot heartbeat received: system={self.master.target_system}, "
            f"component={self.master.target_component}"
        )
        self._send_gcs_heartbeat()

    def stop(self):
        self.connected = False
        if self.master is not None:
            try:
                self.master.close()
            except Exception as exc:
                self.log("WARNING", f"MAVLink close warning: {exc}")
        self.master = None
        self.log("INFO", "MAVLink telemetry backend stopped")

    def read(self, timeout: float = 0.2) -> Optional[TelemetryData]:
        if self.master is None:
            return None

        try:
            msg = self.master.recv_match(blocking=True, timeout=timeout)
        except Exception as exc:
            self.connected = False
            self.log("ERROR", f"MAVLink read failed: {exc}")
            return self._last_data_with_connection(False)

        if msg is None:
            if time.time() - self._last_msg_time > 2.0:
                self.connected = False
                return self._last_data_with_connection(False)
            return None

        self.connected = True
        self._last_msg_time = time.time()
        self._apply_message(msg)
        return self._last_data_with_connection(True)

    def set_mode(self, mode_name: str):
        if self.master is None or self._mavutil is None:
            raise RuntimeError("MAVLink connection is not open")
        self._send_gcs_heartbeat()

        mode = self._normalize_mode(mode_name)
        mapping = self.master.mode_mapping()
        if not mapping or mode not in mapping:
            supported = ", ".join(sorted(mapping.keys())) if mapping else "unknown"
            raise ValueError(f"Unsupported flight mode '{mode_name}'. Supported modes: {supported}")

        mode_id = int(mapping[mode])
        if str(self._mode_name() or "").upper() == mode:
            self.log("INFO", f"Flight mode already active: {mode}")
            return {"mode": mode, "mode_id": mode_id, "already_active": True}

        # Match Mission Planner's compatibility sequence: the modern
        # MAV_CMD_DO_SET_MODE command followed by two legacy SET_MODE packets.
        # Success is not assumed from transmission; HEARTBEAT below is the
        # authoritative confirmation of the vehicle's actual mode.
        mav = self._mavutil.mavlink
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component or 1,
            int(getattr(mav, "MAV_CMD_DO_SET_MODE", 176)),
            0,
            float(mav.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED),
            float(mode_id),
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )
        self.master.mav.set_mode_send(
            self.master.target_system,
            mav.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id,
        )
        time.sleep(0.01)
        self.master.mav.set_mode_send(
            self.master.target_system,
            mav.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id,
        )
        self.log("INFO", f"MAVLink mode change requested: {mode} ({mode_id})")

        if not self._wait_for_mode(mode, timeout=5.0):
            raise TimeoutError(f"Pixhawk {mode} moduna geçişi HEARTBEAT ile doğrulamadı")

        self._last_data.mode = mode
        self.log("SUCCESS", f"Flight mode confirmed by Pixhawk HEARTBEAT: {mode}")
        return {"mode": mode, "mode_id": mode_id, "already_active": False}

    def goto_guided(self, latitude: float, longitude: float, altitude: float):
        if self.master is None or self._mavutil is None:
            raise RuntimeError("MAVLink connection is not open")
        latitude, longitude, altitude = self._validate_guided_target(latitude, longitude, altitude)
        mav = self._mavutil.mavlink
        mapping = self.master.mode_mapping() or {}
        if "GUIDED" not in mapping:
            raise ValueError("Autopilot GUIDED modunu desteklemiyor")

        self.set_mode("GUIDED")

        target_system = self.master.target_system
        target_component = self.master.target_component or 1
        int_frame = int(getattr(mav, "MAV_FRAME_GLOBAL_RELATIVE_ALT_INT", 6))
        guided_mode_id = int(mapping.get("GUIDED", -1))
        is_arduplane = guided_mode_id == 15 or self._vehicle_type in (1, 19, 20, 21, 22)

        if is_arduplane:
            # Mission Planner uses GLOBAL_RELATIVE_ALT (3) with current=2 for
            # Plane Guided waypoints, even when the INT message variant carries
            # integer latitude/longitude fields.
            frame = int(getattr(mav, "MAV_FRAME_GLOBAL_RELATIVE_ALT", 3))
            self._mission_item_int_send(
                target_system,
                target_component,
                0,
                frame,
                int(mav.MAV_CMD_NAV_WAYPOINT),
                2,
                0,
                0.0,
                0.0,
                0.0,
                float("nan"),
                int(round(latitude * 1e7)),
                int(round(longitude * 1e7)),
                altitude,
                self._mission_type_mission(),
            )
            ack_received = self._wait_for_guided_mission_ack(timeout=1.5)
            if ack_received:
                protocol = "MISSION_ITEM_INT current=2 + MISSION_ACK"
            else:
                # Some Plane/telemetry combinations apply the Guided waypoint
                # but do not return MISSION_ACK. Send ArduPilot's two stateless
                # Guided-position forms as compatible fallbacks; all three
                # carry the exact same target and therefore do not conflict.
                self._send_guided_reposition(latitude, longitude, altitude, frame)
                self._send_global_position_target(latitude, longitude, altitude, frame)
                protocol = "MISSION_ITEM_INT + DO_REPOSITION + SET_POSITION_TARGET_GLOBAL_INT"
        else:
            self._send_global_position_target(latitude, longitude, altitude, int_frame)
            protocol = "SET_POSITION_TARGET_GLOBAL_INT"

        self.log(
            "SUCCESS",
            f"Guided target sent via {protocol}: {latitude:.7f}, {longitude:.7f}, {altitude:.1f} m",
        )
        return {
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "mode": "GUIDED",
            "protocol": protocol,
        }

    def _send_guided_reposition(self, latitude: float, longitude: float, altitude: float, frame: int):
        mav = self._mavutil.mavlink
        command = int(getattr(mav, "MAV_CMD_DO_REPOSITION", 192))
        self.master.mav.command_int_send(
            self.master.target_system,
            self.master.target_component or 1,
            int(frame),
            command,
            0,
            0,
            -1.0,
            0.0,
            0.0,
            float("nan"),
            int(round(latitude * 1e7)),
            int(round(longitude * 1e7)),
            float(altitude),
        )

    def _send_global_position_target(self, latitude: float, longitude: float, altitude: float, frame: int):
        self.master.mav.set_position_target_global_int_send(
            0,
            self.master.target_system,
            self.master.target_component or 1,
            int(frame),
            3576,
            int(round(latitude * 1e7)),
            int(round(longitude * 1e7)),
            float(altitude),
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )

    @staticmethod
    def _validate_guided_target(latitude, longitude, altitude):
        latitude = float(latitude)
        longitude = float(longitude)
        altitude = float(altitude)
        if not math.isfinite(latitude) or not -90.0 <= latitude <= 90.0:
            raise ValueError("Geçersiz Guided enlemi")
        if not math.isfinite(longitude) or not -180.0 <= longitude <= 180.0:
            raise ValueError("Geçersiz Guided boylamı")
        if not math.isfinite(altitude) or altitude <= 0.0:
            raise ValueError("Guided irtifası 0 metreden büyük olmalı")
        return latitude, longitude, altitude

    def _wait_for_mode(self, expected_mode: str, timeout: float) -> bool:
        deadline = time.time() + timeout
        expected_mode = str(expected_mode).upper()
        while time.time() < deadline:
            msg = self.master.recv_match(
                type=["HEARTBEAT", "STATUSTEXT", "COMMAND_ACK"],
                blocking=True,
                timeout=0.4,
            )
            if msg is None:
                continue
            self._apply_message(msg)
            if msg.get_type() == "COMMAND_ACK":
                command = int(getattr(msg, "command", -1))
                result = int(getattr(msg, "result", -1))
                set_mode_command = int(getattr(self._mavutil.mavlink, "MAV_CMD_DO_SET_MODE", 176))
                accepted = int(getattr(self._mavutil.mavlink, "MAV_RESULT_ACCEPTED", 0))
                in_progress = int(getattr(self._mavutil.mavlink, "MAV_RESULT_IN_PROGRESS", 5))
                if command == set_mode_command and result not in (accepted, in_progress):
                    raise RuntimeError(f"Pixhawk mod değişimini reddetti (COMMAND_ACK={result})")
            if msg.get_type() == "HEARTBEAT" and str(self._mode_name() or "").upper() == expected_mode:
                return True
        return False

    def _wait_for_guided_mission_ack(self, timeout: float):
        deadline = time.time() + timeout
        accepted = int(getattr(self._mavutil.mavlink, "MAV_MISSION_ACCEPTED", 0))
        while time.time() < deadline:
            msg = self.master.recv_match(type=["MISSION_ACK", "STATUSTEXT"], blocking=True, timeout=0.5)
            if msg is None:
                continue
            if msg.get_type() == "STATUSTEXT":
                self._apply_message(msg)
                continue
            result = int(getattr(msg, "type", -1))
            if result != accepted:
                self.log("WARNING", f"Guided MISSION_ACK={result}; stateless target fallback kullanılacak")
                return False
            return True
        self.log("WARNING", "Guided MISSION_ACK gelmedi; stateless target fallback kullanılacak")
        return False

    def upload_mission(self, mission_items):
        if self.master is None or self._mavutil is None:
            raise RuntimeError("MAVLink connection is not open")
        self._send_gcs_heartbeat()

        mission_items = list(mission_items or [])
        if not mission_items:
            self._clear_mission()
            return

        upload_items = self._build_mavlink_mission_items(mission_items, include_home=False)
        if not upload_items:
            self._clear_mission()
            return

        target_system = self.master.target_system
        target_component = self.master.target_component or 1
        self.log("INFO", f"Uploading mission to Pixhawk: {len(upload_items)} items")

        self._mission_clear_all_send(target_system, target_component, self._mission_type_mission())
        time.sleep(0.2)
        self._drain_mavlink_messages(
            ["MISSION_ACK", "MISSION_REQUEST", "MISSION_REQUEST_INT", "STATUSTEXT"],
            duration=0.8,
        )
        self._mission_count_send(
            target_system,
            target_component,
            len(upload_items),
            self._mission_type_mission(),
        )

        sent_sequences = set()
        deadline = time.time() + max(20.0, len(upload_items) * 3.0)

        while time.time() < deadline:
            msg = self.master.recv_match(
                type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK", "STATUSTEXT"],
                blocking=True,
                timeout=1.0,
            )

            if msg is None:
                continue

            msg_type = msg.get_type()
            if msg_type == "STATUSTEXT":
                text = str(getattr(msg, "text", "")).strip().rstrip("\x00")
                if text:
                    self.log("INFO", f"Autopilot: {text}")
                continue

            if msg_type in ("MISSION_REQUEST_INT", "MISSION_REQUEST"):
                seq = int(getattr(msg, "seq", -1))
                if seq < 0 or seq >= len(upload_items):
                    raise RuntimeError(f"Autopilot requested invalid mission seq {seq}")

                item = upload_items[seq]
                self._mission_item_int_send(
                    target_system,
                    target_component,
                    seq,
                    item["frame"],
                    item["command"],
                    0,
                    1,
                    item["param1"],
                    item["param2"],
                    item["param3"],
                    item["param4"],
                    item["x"],
                    item["y"],
                    item["z"],
                    self._mission_type_mission(),
                )
                sent_sequences.add(seq)
                self.log("INFO", f"Mission item sent: seq={seq}")
                continue

            if msg_type == "MISSION_ACK":
                ack_type = int(getattr(msg, "type", -1))
                if len(sent_sequences) < len(upload_items):
                    self.log("INFO", f"Ignoring early mission ACK type={ack_type}")
                    continue
                if ack_type == self._mavutil.mavlink.MAV_MISSION_ACCEPTED:
                    self.master.mav.mission_set_current_send(target_system, target_component, 0)
                    downloaded_count = self._request_mission_count(
                        mission_type=self._mission_type_mission(),
                        timeout=6.0,
                    )
                    if downloaded_count != len(upload_items):
                        raise RuntimeError(
                            f"Mission verify failed: Pixhawk count={downloaded_count}, expected={len(upload_items)}"
                        )
                    self.log("SUCCESS", f"Mission upload complete: {len(upload_items)} items")
                    return
                raise RuntimeError(f"Mission upload rejected, ACK type={ack_type}")

        raise TimeoutError(
            f"Mission upload timed out. Sent {len(sent_sequences)}/{len(upload_items)} requested items"
        )

    def _clear_mission(self):
        target_system = self.master.target_system
        target_component = self.master.target_component or 1
        self.log("INFO", "Clearing Pixhawk mission")
        self._mission_clear_all_send(target_system, target_component, self._mission_type_mission())

        deadline = time.time() + 8.0
        ack_received = False
        while time.time() < deadline:
            msg = self.master.recv_match(type=["MISSION_ACK", "STATUSTEXT"], blocking=True, timeout=0.5)
            if msg is None:
                self._mission_clear_all_send(target_system, target_component, self._mission_type_mission())
                continue
            if msg.get_type() == "STATUSTEXT":
                text = str(getattr(msg, "text", "")).strip().rstrip("\x00")
                if text:
                    self.log("INFO", f"Autopilot: {text}")
                continue
            ack_type = int(getattr(msg, "type", -1))
            if ack_type != self._mavutil.mavlink.MAV_MISSION_ACCEPTED:
                raise RuntimeError(f"Mission clear rejected, ACK type={ack_type}")
            ack_received = True
            break

        if not ack_received:
            raise TimeoutError("Mission clear timed out waiting for ACK")

        downloaded_count = self._request_mission_count(
            mission_type=self._mission_type_mission(),
            timeout=6.0,
        )
        if downloaded_count not in (0, None):
            raise RuntimeError(f"Mission clear verify failed: Pixhawk count={downloaded_count}")
        self.log("SUCCESS", "Mission clear complete")

    def download_mission(self):
        if self.master is None or self._mavutil is None:
            raise RuntimeError("MAVLink connection is not open")

        target_system = self.master.target_system
        target_component = self.master.target_component or 1
        count = self._request_mission_count(mission_type=self._mission_type_mission(), timeout=8.0)
        if count is None:
            raise TimeoutError("Mission download failed: no MISSION_COUNT")

        self.log("INFO", f"Downloading mission from Pixhawk: {count} items")
        downloaded = []
        for seq in range(count):
            msg = self._request_mission_item_with_retry(
                target_system,
                target_component,
                seq,
                self._mission_type_mission(),
            )
            if msg is None:
                raise TimeoutError(f"Mission download timeout at seq={seq}")
            item = self._mavlink_message_to_mission_item(msg)
            if item is not None:
                downloaded.append(item)

        self.log("SUCCESS", f"Mission download complete: {len(downloaded)} usable items")
        return downloaded

    def upload_fence(self, fence_zones):
        if self.master is None or self._mavutil is None:
            raise RuntimeError("MAVLink connection is not open")
        self._send_gcs_heartbeat()

        upload_items = self._build_mavlink_fence_items(fence_zones)
        target_system = self.master.target_system
        target_component = self.master.target_component or 1
        mission_type = self._mission_type_fence()

        if not self._supports_mission_type():
            raise RuntimeError("Fence upload requires MAVLink2 mission_type support")

        if not upload_items:
            self._clear_fence()
            return

        self.log("INFO", f"Uploading fence to Pixhawk: {len(upload_items)} zones")
        self._mission_clear_all_send(target_system, target_component, mission_type)
        time.sleep(0.2)
        self._drain_mavlink_messages(
            ["MISSION_ACK", "MISSION_REQUEST", "MISSION_REQUEST_INT", "STATUSTEXT"],
            duration=0.8,
        )
        self._mission_count_send(target_system, target_component, len(upload_items), mission_type)

        sent_sequences = set()
        deadline = time.time() + max(20.0, len(upload_items) * 3.0)
        while time.time() < deadline:
            msg = self.master.recv_match(
                type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK", "STATUSTEXT"],
                blocking=True,
                timeout=1.0,
            )
            if msg is None:
                continue

            msg_type = msg.get_type()
            if msg_type == "STATUSTEXT":
                text = str(getattr(msg, "text", "")).strip().rstrip("\x00")
                if text:
                    self.log("INFO", f"Autopilot: {text}")
                continue
            if self._message_mission_type(msg, mission_type) != mission_type:
                continue

            if msg_type in ("MISSION_REQUEST_INT", "MISSION_REQUEST"):
                seq = int(getattr(msg, "seq", -1))
                if seq < 0 or seq >= len(upload_items):
                    raise RuntimeError(f"Autopilot requested invalid fence seq {seq}")
                item = upload_items[seq]
                self._mission_item_int_send(
                    target_system,
                    target_component,
                    seq,
                    item["frame"],
                    item["command"],
                    0,
                    1,
                    item["param1"],
                    item["param2"],
                    item["param3"],
                    item["param4"],
                    item["x"],
                    item["y"],
                    item["z"],
                    mission_type,
                )
                sent_sequences.add(seq)
                self.log("INFO", f"Fence item sent: seq={seq}")
                continue

            if msg_type == "MISSION_ACK":
                ack_type = int(getattr(msg, "type", -1))
                if len(sent_sequences) < len(upload_items):
                    self.log("INFO", f"Ignoring early fence ACK type={ack_type}")
                    continue
                if ack_type == self._mavutil.mavlink.MAV_MISSION_ACCEPTED:
                    downloaded_count = self._request_mission_count(mission_type=mission_type, timeout=6.0)
                    if downloaded_count != len(upload_items):
                        raise RuntimeError(
                            f"Fence verify failed: Pixhawk count={downloaded_count}, expected={len(upload_items)}"
                        )
                    self.log("SUCCESS", f"Fence upload complete: {len(upload_items)} zones")
                    return
                raise RuntimeError(f"Fence upload rejected, ACK type={ack_type}")

        raise TimeoutError(
            f"Fence upload timed out. Sent {len(sent_sequences)}/{len(upload_items)} requested items"
        )

    def _clear_fence(self):
        target_system = self.master.target_system
        target_component = self.master.target_component or 1
        mission_type = self._mission_type_fence()
        self.log("INFO", "Clearing Pixhawk fence")
        self._mission_clear_all_send(target_system, target_component, mission_type)

        deadline = time.time() + 8.0
        ack_received = False
        while time.time() < deadline:
            msg = self.master.recv_match(type=["MISSION_ACK", "STATUSTEXT"], blocking=True, timeout=0.5)
            if msg is None:
                self._mission_clear_all_send(target_system, target_component, mission_type)
                continue
            if msg.get_type() == "STATUSTEXT":
                text = str(getattr(msg, "text", "")).strip().rstrip("\x00")
                if text:
                    self.log("INFO", f"Autopilot: {text}")
                continue
            if self._message_mission_type(msg, mission_type) != mission_type:
                continue
            ack_type = int(getattr(msg, "type", -1))
            if ack_type != self._mavutil.mavlink.MAV_MISSION_ACCEPTED:
                raise RuntimeError(f"Fence clear rejected, ACK type={ack_type}")
            ack_received = True
            break

        if not ack_received:
            raise TimeoutError("Fence clear timed out waiting for ACK")

        downloaded_count = self._request_mission_count(mission_type=mission_type, timeout=6.0)
        if downloaded_count not in (0, None):
            raise RuntimeError(f"Fence clear verify failed: Pixhawk count={downloaded_count}")
        self.log("SUCCESS", "Fence clear complete")

    def download_fence(self):
        if self.master is None or self._mavutil is None:
            raise RuntimeError("MAVLink connection is not open")
        if not self._supports_mission_type():
            raise RuntimeError("Fence download requires MAVLink2 mission_type support")

        target_system = self.master.target_system
        target_component = self.master.target_component or 1
        mission_type = self._mission_type_fence()
        count = self._request_mission_count(mission_type=mission_type, timeout=8.0)
        if count is None:
            raise TimeoutError("Fence download failed: no MISSION_COUNT")

        self.log("INFO", f"Downloading fence from Pixhawk: {count} zones")
        zones = []
        for seq in range(count):
            msg = self._request_mission_item_with_retry(target_system, target_component, seq, mission_type)
            if msg is None:
                raise TimeoutError(f"Fence download timeout at seq={seq}")
            zone = self._mavlink_message_to_fence_zone(msg)
            if zone is not None:
                zones.append(zone)

        self.log("SUCCESS", f"Fence download complete: {len(zones)} zones")
        return zones

    def download_parameters(self):
        if self.master is None or self._mavutil is None:
            raise RuntimeError("MAVLink connection is not open")
        self._send_gcs_heartbeat()

        self.log("INFO", "Requesting Pixhawk parameter list")
        self._drain_mavlink_messages(["PARAM_VALUE", "STATUSTEXT"], duration=0.4)
        self.master.mav.param_request_list_send(
            self.master.target_system,
            self.master.target_component or 1,
        )

        params_by_name = {}
        expected_count = None
        deadline = time.time() + 45.0
        last_seen = time.time()

        while time.time() < deadline:
            msg = self.master.recv_match(type=["PARAM_VALUE", "STATUSTEXT"], blocking=True, timeout=0.8)
            if msg is None:
                if expected_count is not None and params_by_name and time.time() - last_seen > 2.5:
                    break
                continue

            msg_type = msg.get_type()
            if msg_type == "STATUSTEXT":
                text = str(getattr(msg, "text", "")).strip().rstrip("\x00")
                if text:
                    self.log("INFO", f"Autopilot: {text}")
                continue

            raw_id = getattr(msg, "param_id", "")
            if isinstance(raw_id, bytes):
                name = raw_id.decode("ascii", errors="ignore").rstrip("\x00")
            else:
                name = str(raw_id).rstrip("\x00")
            if not name:
                continue

            try:
                value = float(getattr(msg, "param_value", 0.0))
            except (TypeError, ValueError):
                value = 0.0

            index = int(getattr(msg, "param_index", -1))
            count = int(getattr(msg, "param_count", 0) or 0)
            ptype = int(getattr(msg, "param_type", 0) or 0)
            if count > 0:
                expected_count = count

            params_by_name[name] = {
                "name": name,
                "value": value,
                "type": ptype,
                "index": index,
                "count": count,
                "group": name.split("_", 1)[0] if "_" in name else name,
            }
            last_seen = time.time()

            if expected_count is not None and len(params_by_name) >= expected_count:
                break

        params = sorted(params_by_name.values(), key=lambda item: item["name"])
        if not params:
            raise TimeoutError("Parameter download timed out: no PARAM_VALUE received")
        self.log("SUCCESS", f"Parameter download complete: {len(params)} parameters")
        return params

    def write_parameters(self, updates):
        if self.master is None or self._mavutil is None:
            raise RuntimeError("MAVLink connection is not open")
        self._send_gcs_heartbeat()

        written = []
        failed = []
        default_type = int(getattr(self._mavutil.mavlink, "MAV_PARAM_TYPE_REAL32", 9))
        target_system = self.master.target_system
        target_component = self.master.target_component or 1

        for update in list(updates or []):
            name = str(update.get("name", "")).strip()
            try:
                value = float(update.get("value"))
                if not math.isfinite(value):
                    raise ValueError("value must be finite")
                encoded_name = name.encode("ascii")
                if not name or len(encoded_name) > 16:
                    raise ValueError("invalid MAVLink parameter name")
                param_type = int(update.get("type", default_type) or default_type)
            except (TypeError, ValueError, UnicodeEncodeError) as exc:
                failed.append({"name": name, "error": str(exc)})
                continue

            confirmed_value = None
            last_error = "Pixhawk PARAM_VALUE confirmation timed out"
            for attempt in range(3):
                self._drain_mavlink_messages(["PARAM_VALUE", "STATUSTEXT"], duration=0.08)
                self.master.mav.param_set_send(
                    target_system,
                    target_component,
                    encoded_name,
                    value,
                    param_type,
                )
                confirmed_value = self._wait_parameter_value(name, timeout=1.8)
                if confirmed_value is None:
                    last_error = f"confirmation timeout (attempt {attempt + 1}/3)"
                    continue
                tolerance = max(1e-5, abs(value) * 1e-5)
                if math.isclose(confirmed_value, value, rel_tol=1e-5, abs_tol=tolerance):
                    break
                last_error = f"Pixhawk returned {confirmed_value:g}, requested {value:g}"
                confirmed_value = None

            if confirmed_value is None:
                failed.append({"name": name, "error": last_error})
                self.log("ERROR", f"Parameter write failed: {name}: {last_error}")
                continue

            written.append({"name": name, "value": confirmed_value, "type": param_type})
            self.log("SUCCESS", f"Parameter verified: {name}={confirmed_value:g}")

        return {"written": written, "failed": failed}

    def _wait_parameter_value(self, expected_name: str, timeout: float = 2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.master.recv_match(type=["PARAM_VALUE", "STATUSTEXT"], blocking=True, timeout=0.35)
            if msg is None:
                continue
            if msg.get_type() == "STATUSTEXT":
                text = str(getattr(msg, "text", "")).strip().rstrip("\x00")
                if text:
                    self.log("INFO", f"Autopilot: {text}")
                continue
            raw_id = getattr(msg, "param_id", "")
            if isinstance(raw_id, bytes):
                name = raw_id.decode("ascii", errors="ignore").rstrip("\x00")
            else:
                name = str(raw_id).rstrip("\x00")
            if name != expected_name:
                continue
            try:
                return float(getattr(msg, "param_value"))
            except (TypeError, ValueError):
                return None
        return None

    def _request_mission_item_with_retry(self, target_system: int, target_component: int, seq: int, mission_type: int):
        for attempt in range(3):
            if attempt == 0:
                self._mission_request_int_send(target_system, target_component, seq, mission_type)
            else:
                self._mission_request_send(target_system, target_component, seq, mission_type)
            msg = self._wait_mission_item(seq, mission_type=mission_type, timeout=2.5)
            if msg is not None:
                return msg
        return None

    def _request_mission_count(self, mission_type: int, timeout: float = 6.0):
        self._drain_mavlink_messages(["MISSION_COUNT", "MISSION_ITEM", "MISSION_ITEM_INT"], duration=0.3)
        self._mission_request_list_send(
            self.master.target_system,
            self.master.target_component or 1,
            mission_type,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.master.recv_match(type=["MISSION_COUNT", "STATUSTEXT"], blocking=True, timeout=0.5)
            if msg is None:
                continue
            if msg.get_type() == "STATUSTEXT":
                text = str(getattr(msg, "text", "")).strip().rstrip("\x00")
                if text:
                    self.log("INFO", f"Autopilot: {text}")
                continue
            if self._message_mission_type(msg, mission_type) != mission_type:
                continue
            return int(getattr(msg, "count", 0))
        return None

    def _wait_mission_item(self, seq: int, mission_type: int, timeout: float = 5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.master.recv_match(
                type=["MISSION_ITEM_INT", "MISSION_ITEM", "STATUSTEXT"],
                blocking=True,
                timeout=0.5,
            )
            if msg is None:
                continue
            if msg.get_type() == "STATUSTEXT":
                text = str(getattr(msg, "text", "")).strip().rstrip("\x00")
                if text:
                    self.log("INFO", f"Autopilot: {text}")
                continue
            if self._message_mission_type(msg, mission_type) != mission_type:
                continue
            if int(getattr(msg, "seq", -1)) == seq:
                return msg
        return None

    def _drain_mavlink_messages(self, message_types, duration: float = 0.5):
        deadline = time.time() + duration
        while time.time() < deadline:
            msg = self.master.recv_match(type=message_types, blocking=True, timeout=0.1)
            if msg is None:
                continue

    def _mission_type_mission(self) -> int:
        return int(getattr(self._mavutil.mavlink, "MAV_MISSION_TYPE_MISSION", 0))

    def _mission_type_fence(self) -> int:
        return int(getattr(self._mavutil.mavlink, "MAV_MISSION_TYPE_FENCE", 1))

    def _supports_mission_type(self) -> bool:
        mav = self._mavutil.mavlink
        return str(getattr(mav, "WIRE_PROTOCOL_VERSION", "1.0")).startswith("2")

    @staticmethod
    def _message_mission_type(msg, default_mission_type: int) -> int:
        return int(getattr(msg, "mission_type", default_mission_type))

    def _mission_clear_all_send(self, target_system: int, target_component: int, mission_type: int):
        try:
            self.master.mav.mission_clear_all_send(target_system, target_component, mission_type)
        except TypeError:
            self.master.mav.mission_clear_all_send(target_system, target_component)

    def _mission_count_send(self, target_system: int, target_component: int, count: int, mission_type: int):
        try:
            self.master.mav.mission_count_send(target_system, target_component, count, mission_type)
        except TypeError:
            self.master.mav.mission_count_send(target_system, target_component, count)

    def _mission_item_int_send(
        self,
        target_system: int,
        target_component: int,
        seq: int,
        frame: int,
        command: int,
        current: int,
        autocontinue: int,
        param1: float,
        param2: float,
        param3: float,
        param4: float,
        x: int,
        y: int,
        z: float,
        mission_type: int,
    ):
        try:
            self.master.mav.mission_item_int_send(
                target_system,
                target_component,
                seq,
                frame,
                command,
                current,
                autocontinue,
                param1,
                param2,
                param3,
                param4,
                x,
                y,
                z,
                mission_type,
            )
        except TypeError:
            self.master.mav.mission_item_int_send(
                target_system,
                target_component,
                seq,
                frame,
                command,
                current,
                autocontinue,
                param1,
                param2,
                param3,
                param4,
                x,
                y,
                z,
            )

    def _mission_request_list_send(self, target_system: int, target_component: int, mission_type: int):
        try:
            self.master.mav.mission_request_list_send(target_system, target_component, mission_type)
        except TypeError:
            self.master.mav.mission_request_list_send(target_system, target_component)

    def _mission_request_int_send(self, target_system: int, target_component: int, seq: int, mission_type: int):
        try:
            self.master.mav.mission_request_int_send(target_system, target_component, seq, mission_type)
        except TypeError:
            self.master.mav.mission_request_int_send(target_system, target_component, seq)

    def _mission_request_send(self, target_system: int, target_component: int, seq: int, mission_type: int):
        try:
            self.master.mav.mission_request_send(target_system, target_component, seq, mission_type)
        except TypeError:
            self.master.mav.mission_request_send(target_system, target_component, seq)

    def _send_gcs_heartbeat(self):
        if self.master is None or self._mavutil is None:
            return
        mav = self._mavutil.mavlink
        self.master.mav.heartbeat_send(
            mav.MAV_TYPE_GCS,
            mav.MAV_AUTOPILOT_INVALID,
            0,
            0,
            mav.MAV_STATE_ACTIVE,
        )

    def _build_connection_string(self) -> str:
        if self.connection_type == "SERIAL":
            return self.target or "COM3"

        if self.connection_type == "TCP":
            target = self.target or "127.0.0.1:5760"
            return target if target.startswith("tcp:") else f"tcp:{target}"

        target = self.target or "0.0.0.0:14550"
        if target.startswith(("udp:", "udpin:", "udpout:")):
            return target
        if target.isdigit():
            target = f"0.0.0.0:{target}"
        return f"udp:{target}"

    def _last_data_with_connection(self, connected: bool) -> TelemetryData:
        data = self._last_data
        data.connected = connected
        data.timestamp = time.time()
        return data

    def _apply_message(self, msg):
        msg_type = msg.get_type()
        data = self._last_data

        if msg_type == "HEARTBEAT":
            data.mode = self._mode_name()
            data.armed = bool(getattr(msg, "base_mode", 0) & 0x80)
        elif msg_type == "GLOBAL_POSITION_INT":
            data.latitude = self._scaled(getattr(msg, "lat", None), 1e7)
            data.longitude = self._scaled(getattr(msg, "lon", None), 1e7)
            data.absolute_altitude = self._scaled(getattr(msg, "alt", None), 1000.0)
            data.relative_altitude = self._scaled(getattr(msg, "relative_alt", None), 1000.0)
            vx = self._scaled(getattr(msg, "vx", None), 100.0)
            vy = self._scaled(getattr(msg, "vy", None), 100.0)
            if vx is not None and vy is not None:
                data.ground_speed = math.sqrt(vx * vx + vy * vy)
            data.vertical_speed = self._scaled(getattr(msg, "vz", None), -100.0)
            hdg = getattr(msg, "hdg", None)
            if hdg is not None and hdg != 65535:
                data.heading = hdg / 100.0
        elif msg_type == "VFR_HUD":
            data.air_speed = self._float_or_none(getattr(msg, "airspeed", None))
            data.ground_speed = self._float_or_none(getattr(msg, "groundspeed", None))
            data.relative_altitude = self._float_or_none(getattr(msg, "alt", None))
            data.vertical_speed = self._float_or_none(getattr(msg, "climb", None))
            heading = getattr(msg, "heading", None)
            if heading is not None:
                data.heading = float(heading) % 360.0
        elif msg_type == "ATTITUDE":
            data.pitch = math.degrees(getattr(msg, "pitch", 0.0))
            data.roll = math.degrees(getattr(msg, "roll", 0.0))
            data.yaw = math.degrees(getattr(msg, "yaw", 0.0)) % 360.0
        elif msg_type == "SYS_STATUS":
            data.battery_voltage = self._scaled(getattr(msg, "voltage_battery", None), 1000.0)
            data.battery_current = self._scaled(getattr(msg, "current_battery", None), 100.0)
            remaining = getattr(msg, "battery_remaining", None)
            if remaining is not None and remaining >= 0:
                data.battery_remaining = float(remaining)
        elif msg_type == "GPS_RAW_INT":
            data.gps_fix_type = getattr(msg, "fix_type", None)
            data.satellites_visible = getattr(msg, "satellites_visible", None)
            lat = getattr(msg, "lat", None)
            lon = getattr(msg, "lon", None)
            alt = getattr(msg, "alt", None)
            if lat not in (None, 0):
                data.latitude = self._scaled(lat, 1e7)
            if lon not in (None, 0):
                data.longitude = self._scaled(lon, 1e7)
            if alt not in (None, 0):
                data.absolute_altitude = self._scaled(alt, 1000.0)
        elif msg_type == "RADIO_STATUS":
            data.signal_quality = self._radio_link_quality(msg)
        elif msg_type == "STATUSTEXT":
            text = str(getattr(msg, "text", "")).strip().rstrip("\x00")
            if text and text != self._last_status_text:
                self._last_status_text = text
                severity = int(getattr(msg, "severity", 6))
                level = "WARNING" if severity <= 4 else "INFO"
                self.log(level, f"Autopilot: {text}")
        elif msg_type == "COMMAND_ACK":
            command = getattr(msg, "command", None)
            if command == getattr(self._mavutil.mavlink, "MAV_CMD_DO_SET_MODE", 176):
                result = getattr(msg, "result", None)
                if result == self._mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    self.log("SUCCESS", "Autopilot accepted mode command")
                else:
                    self.log("WARNING", f"Autopilot mode command ACK result: {result}")

    def _mode_name(self) -> Optional[str]:
        try:
            return self.master.flightmode
        except Exception:
            return None

    def _wait_autopilot_heartbeat(self, timeout: float = 8.0):
        if self.master is None or self._mavutil is None:
            return None

        deadline = time.time() + timeout
        mav = self._mavutil.mavlink
        while time.time() < deadline:
            msg = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
            if msg is None:
                continue

            vehicle_type = int(getattr(msg, "type", -1))
            autopilot = int(getattr(msg, "autopilot", mav.MAV_AUTOPILOT_INVALID))
            if vehicle_type == mav.MAV_TYPE_GCS:
                continue
            if autopilot == mav.MAV_AUTOPILOT_INVALID:
                continue

            self.master.target_system = msg.get_srcSystem()
            self.master.target_component = msg.get_srcComponent() or 1
            self._apply_message(msg)
            return msg

        return None

    def _build_mavlink_mission_items(self, mission_items, include_home: bool = False):
        items = []
        mission_items = list(mission_items or [])
        if include_home:
            home_item = self._build_home_mavlink_item(mission_items)
            if home_item is not None:
                items.append(home_item)
        for item in mission_items:
            mav_item = self._mission_item_to_mavlink(item)
            if mav_item is not None:
                items.append(mav_item)
        return items

    def _build_mavlink_fence_items(self, fence_zones):
        mav = self._mavutil.mavlink
        command = int(getattr(mav, "MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION", 5004))
        items = []
        for zone in list(fence_zones or []):
            if not bool(getattr(zone, "is_active", True)):
                continue
            lat = getattr(zone, "center_lat", None)
            lon = getattr(zone, "center_lon", None)
            radius = float(getattr(zone, "radius_m", 0.0) or 0.0)
            if lat in (None, 0) or lon in (None, 0) or radius <= 0.0:
                continue
            frame = self._frame_id(str(getattr(zone, "frame", "Relative")), default=getattr(mav, "MAV_FRAME_GLOBAL_RELATIVE_ALT_INT", 6))
            items.append({
                "frame": frame,
                "command": command,
                "param1": radius,
                "param2": 0.0,
                "param3": 0.0,
                "param4": 0.0,
                "x": int(float(lat) * 1e7),
                "y": int(float(lon) * 1e7),
                "z": 0.0,
            })
        return items

    def _mavlink_message_to_fence_zone(self, msg):
        mav = self._mavutil.mavlink
        command = int(getattr(msg, "command", 0))
        circle_exclusion = int(getattr(mav, "MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION", 5004))
        circle_inclusion = int(getattr(mav, "MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION", 5003))
        if command not in (circle_exclusion, circle_inclusion):
            return None

        x = getattr(msg, "x", 0)
        y = getattr(msg, "y", 0)
        if msg.get_type() == "MISSION_ITEM_INT":
            lat = float(x) / 1e7 if x else None
            lon = float(y) / 1e7 if y else None
        else:
            lat = float(x) if x else None
            lon = float(y) if y else None
        radius = float(getattr(msg, "param1", 0.0) or 0.0)
        if lat is None or lon is None or radius <= 0.0:
            return None

        return DefenseZone(
            center_lat=lat,
            center_lon=lon,
            radius_m=radius,
            name=f"Hava Savunma {int(getattr(msg, 'seq', 0)) + 1}",
            is_active=True,
            frame=self._frame_name(int(getattr(msg, "frame", 0))),
        )

    def _build_home_mavlink_item(self, mission_items):
        mav = self._mavutil.mavlink
        lat = self._last_data.latitude
        lon = self._last_data.longitude
        alt = self._last_data.absolute_altitude

        if lat in (None, 0) or lon in (None, 0):
            for item in mission_items:
                lat = getattr(item, "latitude", None)
                lon = getattr(item, "longitude", None)
                if lat not in (None, 0) and lon not in (None, 0):
                    break

        if lat in (None, 0) or lon in (None, 0):
            return None

        if alt in (None, 0):
            alt = float(getattr(mission_items[0], "altitude", 50.0) if mission_items else 50.0)

        return {
            "frame": mav.MAV_FRAME_GLOBAL,
            "command": mav.MAV_CMD_NAV_WAYPOINT,
            "param1": 0.0,
            "param2": 0.0,
            "param3": 0.0,
            "param4": 0.0,
            "x": int(float(lat) * 1e7),
            "y": int(float(lon) * 1e7),
            "z": float(alt),
        }

    def _mission_item_to_mavlink(self, item):
        mav = self._mavutil.mavlink
        item_type = getattr(item, "item_type", None)
        lat = getattr(item, "latitude", None)
        lon = getattr(item, "longitude", None)
        alt = float(getattr(item, "altitude", 50.0) or 50.0)
        params = dict(getattr(item, "parameters", {}) or {})

        base = {
            "frame": mav.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            "command": mav.MAV_CMD_NAV_WAYPOINT,
            "param1": float(params.get("param1", params.get("delay", 0.0)) or 0.0),
            "param2": float(params.get("param2", params.get("acceptance_radius", 0.0)) or 0.0),
            "param3": float(params.get("param3", params.get("pass_radius", 0.0)) or 0.0),
            "param4": float(params.get("param4", params.get("yaw", 0.0)) or 0.0),
            "x": int(float(lat or 0.0) * 1e7),
            "y": int(float(lon or 0.0) * 1e7),
            "z": alt,
        }

        frame_text = str(params.get("frame", "") or "").strip().upper()
        if frame_text:
            base["frame"] = self._frame_id(frame_text, default=base["frame"])

        if item_type == MissionItemType.WAYPOINT:
            if lat is None or lon is None:
                return None
            return base

        if item_type == MissionItemType.TAKEOFF:
            if lat is None or lon is None:
                return None
            base["command"] = mav.MAV_CMD_NAV_TAKEOFF
            return base

        if item_type == MissionItemType.LAND:
            if lat is None or lon is None:
                return None
            base["command"] = mav.MAV_CMD_NAV_LAND
            base["z"] = 0.0
            return base

        if item_type == MissionItemType.RTL:
            base["command"] = mav.MAV_CMD_NAV_RETURN_TO_LAUNCH
            base["frame"] = mav.MAV_FRAME_MISSION
            base["x"] = 0
            base["y"] = 0
            base["z"] = 0.0
            return base

        if item_type == MissionItemType.DO_LAND_START:
            base["command"] = mav.MAV_CMD_DO_LAND_START
            base["frame"] = mav.MAV_FRAME_MISSION
            base["param1"] = float(params.get("param1", 0.0) or 0.0)
            base["param2"] = float(params.get("param2", 0.0) or 0.0)
            base["param3"] = float(params.get("param3", 0.0) or 0.0)
            base["param4"] = float(params.get("param4", 0.0) or 0.0)
            base["x"] = 0
            base["y"] = 0
            base["z"] = 0.0
            return base

        if item_type == MissionItemType.DO_JUMP:
            base["command"] = mav.MAV_CMD_DO_JUMP
            base["frame"] = mav.MAV_FRAME_MISSION
            base["param1"] = float(params.get("jump_to", 0))
            base["param2"] = float(params.get("repeat", 1))
            base["x"] = 0
            base["y"] = 0
            base["z"] = 0.0
            return base

        return None

    def _mavlink_message_to_mission_item(self, msg):
        mav = self._mavutil.mavlink
        seq = int(getattr(msg, "seq", 0))
        command = int(getattr(msg, "command", 0))
        frame = int(getattr(msg, "frame", 0))
        x = getattr(msg, "x", 0)
        y = getattr(msg, "y", 0)
        z = float(getattr(msg, "z", 50.0) or 50.0)

        if msg.get_type() == "MISSION_ITEM_INT":
            lat = float(x) / 1e7 if x else None
            lon = float(y) / 1e7 if y else None
        else:
            lat = float(x) if x else None
            lon = float(y) if y else None
        item_type = MissionItemType.WAYPOINT
        params = {
            "param1": float(getattr(msg, "param1", 0) or 0),
            "param2": float(getattr(msg, "param2", 0) or 0),
            "param3": float(getattr(msg, "param3", 0) or 0),
            "param4": float(getattr(msg, "param4", 0) or 0),
            "frame": self._frame_name(frame),
        }

        if command == mav.MAV_CMD_NAV_TAKEOFF:
            item_type = MissionItemType.TAKEOFF
        elif command == mav.MAV_CMD_NAV_LAND:
            item_type = MissionItemType.LAND
        elif command == mav.MAV_CMD_NAV_RETURN_TO_LAUNCH:
            return None
        elif command == mav.MAV_CMD_DO_LAND_START:
            item_type = MissionItemType.DO_LAND_START
            lat = None
            lon = None
            z = 0.0
        elif command == mav.MAV_CMD_DO_JUMP:
            item_type = MissionItemType.DO_JUMP
            lat = None
            lon = None
            z = 0.0
            params = {
                "jump_to": int(float(getattr(msg, "param1", 0) or 0)),
                "repeat": int(float(getattr(msg, "param2", 0) or 0)),
                "param1": float(getattr(msg, "param1", 0) or 0),
                "param2": float(getattr(msg, "param2", 0) or 0),
                "param3": float(getattr(msg, "param3", 0) or 0),
                "param4": float(getattr(msg, "param4", 0) or 0),
                "frame": self._frame_name(frame),
            }
        elif command != mav.MAV_CMD_NAV_WAYPOINT:
            return None

        if item_type in (MissionItemType.WAYPOINT, MissionItemType.TAKEOFF, MissionItemType.LAND):
            if lat is None or lon is None:
                return None

        return MissionItem(
            item_type=item_type,
            sequence=max(0, seq),
            latitude=lat,
            longitude=lon,
            altitude=z,
            parameters=params,
        )

    def _frame_name(self, frame: int) -> str:
        mav = self._mavutil.mavlink
        if frame in (
            getattr(mav, "MAV_FRAME_GLOBAL", -1),
            getattr(mav, "MAV_FRAME_GLOBAL_INT", -1),
        ):
            return "Global"
        if frame in (
            getattr(mav, "MAV_FRAME_GLOBAL_TERRAIN_ALT", -1),
            getattr(mav, "MAV_FRAME_GLOBAL_TERRAIN_ALT_INT", -1),
        ):
            return "Terrain"
        return "Relative"

    def _frame_id(self, frame: str, default: int = None) -> int:
        mav = self._mavutil.mavlink
        fallback = default if default is not None else getattr(mav, "MAV_FRAME_GLOBAL_RELATIVE_ALT_INT", 6)
        text = str(frame or "").strip().upper()
        if text in {"ABSOLUTE", "GLOBAL"}:
            return int(getattr(mav, "MAV_FRAME_GLOBAL_INT", getattr(mav, "MAV_FRAME_GLOBAL", fallback)))
        if text in {"TERRAIN", "GLOBAL_TERRAIN_ALT"}:
            return int(getattr(mav, "MAV_FRAME_GLOBAL_TERRAIN_ALT_INT", fallback))
        return int(getattr(mav, "MAV_FRAME_GLOBAL_RELATIVE_ALT_INT", fallback))

    @staticmethod
    def _normalize_mode(mode_name: str) -> str:
        mode = str(mode_name or "").strip().upper()
        aliases = {
            "MANUAL": "MANUAL",
            "AUTO": "AUTO",
            "GUIDED": "GUIDED",
            "RTL": "RTL",
            "FBWA": "FBWA",
            "KAMIKAZE": "GUIDED",
            "HAVA SAVUNMADAN KAÇIŞ": "GUIDED",
            "HAVA SAVUNMADAN KACIS": "GUIDED",
            "TAKIP": "GUIDED",
            "TAKİP": "GUIDED",
            "GÖREV İPTAL": "RTL",
            "GOREV IPTAL": "RTL",
            "OTONOM İN": "AUTO",
            "OTONOM IN": "AUTO",
        }
        return aliases.get(mode, mode)

    @staticmethod
    def _scaled(value, scale) -> Optional[float]:
        if value is None:
            return None
        return float(value) / float(scale)

    @staticmethod
    def _float_or_none(value) -> Optional[float]:
        return None if value is None else float(value)

    @staticmethod
    def _radio_link_quality(msg) -> Optional[float]:
        rssi = getattr(msg, "rssi", None)
        remrssi = getattr(msg, "remrssi", None)
        txbuf = getattr(msg, "txbuf", None)
        noise = getattr(msg, "noise", None)
        remnoise = getattr(msg, "remnoise", None)

        candidates = []
        if txbuf is not None and float(txbuf) > 0.0:
            candidates.append(max(0.0, min(100.0, float(txbuf))))

        def rssi_to_percent(value) -> float:
            value = float(value)
            if value <= 100.0:
                return max(0.0, min(100.0, value))
            return max(0.0, min(100.0, value / 254.0 * 100.0))

        valid_rssi = rssi is not None and float(rssi) > 1.0
        valid_remrssi = remrssi is not None and float(remrssi) > 1.0

        margins = []
        if valid_rssi and noise is not None:
            margins.append(float(rssi) - float(noise))
        if valid_remrssi and remnoise is not None:
            margins.append(float(remrssi) - float(remnoise))

        if margins:
            margin = min(margins)
            candidates.append(max(0.0, min(100.0, (margin - 6.0) / 34.0 * 100.0)))

        if valid_rssi and valid_remrssi:
            candidates.append(min(rssi_to_percent(rssi), rssi_to_percent(remrssi)))
        elif valid_rssi:
            candidates.append(rssi_to_percent(rssi))
        elif valid_remrssi:
            candidates.append(rssi_to_percent(remrssi))

        if candidates:
            return max(candidates)
        if rssi is None:
            return None
        return 0.0
