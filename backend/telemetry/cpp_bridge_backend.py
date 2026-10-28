import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Optional

from backend.telemetry.base import TelemetryBackend, TelemetryLogCallback
from models.mission_item import MissionItem, MissionItemType
from models.telemetry import TelemetryData


class CppTelemetryBackend(TelemetryBackend):
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
        self.baud = baud or 57600
        exe = self._bridge_path()
        if not os.path.exists(exe):
            raise RuntimeError(f"bridge executable not found: {exe}")
        self.process = None
        self._reader = None
        self._queue = queue.Queue()
        self._event_queue = queue.Queue()
        self._stderr_queue = queue.Queue()
        self._startup_error = None
        self._last_data = TelemetryData(connected=False)
        self._last_msg_time = 0.0

    def start(self):
        exe = self._bridge_path()
        if not os.path.exists(exe):
            raise RuntimeError(f"bridge executable not found: {exe}")

        self._cleanup_stale_bridge_processes()

        args = [
            exe,
            "--type",
            self.connection_type,
            "--target",
            self.target,
            "--baud",
            str(self.baud),
        ]
        self.log("INFO", f"Starting C++ telemetry bridge: {' '.join(args)}")
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_reader.start()

        time.sleep(0.35)
        if self.process.poll() is not None:
            message = self._startup_error or self._collect_stderr_startup_error()
            raise RuntimeError(message or f"C++ telemetry bridge exited with code {self.process.returncode}")
        self.connected = True

    def stop(self):
        self.connected = False
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
                self._taskkill_process_tree(self.process.pid)
        self.process = None
        self.log("INFO", "C++ telemetry bridge stopped")

    def read(self, timeout: float = 0.2) -> Optional[TelemetryData]:
        if self.process is None:
            return None
        if self.process.poll() is not None:
            self.connected = False
            return self._last_data_with_connection(False)

        try:
            payload = self._queue.get(timeout=timeout)
        except queue.Empty:
            if time.time() - self._last_msg_time > 2.0:
                self.connected = False
                return self._last_data_with_connection(False)
            return None

        self._last_msg_time = time.time()
        self.connected = True
        self._last_data = self._telemetry_from_dict(payload)
        return self._last_data_with_connection(True)

    def set_mode(self, mode_name: str):
        mode = self._normalize_mode(mode_name)
        self._send_command(f"MODE {mode}")
        event = self._wait_event(
            {"mode_complete", "mode_failed", "command_error"},
            timeout=7.0,
        )
        if event is None:
            raise TimeoutError(f"Pixhawk {mode} moduna geçişi doğrulamadı")
        if event.get("event") != "mode_complete":
            raise RuntimeError(event.get("message") or f"Mode change failed: {mode}")
        self._last_data.mode = mode
        return {"mode": mode, "mode_id": None, "already_active": "already active" in str(event.get("message", "")).lower()}

    def goto_guided(self, latitude: float, longitude: float, altitude: float):
        latitude = float(latitude)
        longitude = float(longitude)
        altitude = float(altitude)
        if not math.isfinite(latitude) or not -90.0 <= latitude <= 90.0:
            raise ValueError("Geçersiz Guided enlemi")
        if not math.isfinite(longitude) or not -180.0 <= longitude <= 180.0:
            raise ValueError("Geçersiz Guided boylamı")
        if not math.isfinite(altitude) or altitude <= 0.0:
            raise ValueError("Guided irtifası 0 metreden büyük olmalı")

        self._send_command(f"GUIDED_TARGET|{latitude:.7f},{longitude:.7f},{altitude:.2f}")
        event = self._wait_event(
            {"guided_target_complete", "guided_target_failed", "command_error"},
            timeout=7.0,
        )
        if event is None:
            raise TimeoutError("Guided hedef Pixhawk doğrulaması zaman aşımına uğradı")
        if event.get("event") != "guided_target_complete":
            raise RuntimeError(event.get("message") or "Guided hedef reddedildi")
        self._last_data.mode = "GUIDED"
        return {
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "mode": "GUIDED",
            "protocol": event.get("protocol", "C++ MAVLink bridge"),
        }

    def upload_mission(self, mission_items):
        wire_items = self._build_mission_wire_items(mission_items, include_home=False)
        uploadable_count = len(wire_items)
        if not wire_items or uploadable_count <= 0:
            self._send_command("MISSION_CLEAR")
            event = self._wait_event(
                {"mission_clear_complete", "mission_clear_failed", "command_error"},
                timeout=12.0,
            )
            if event is None:
                raise TimeoutError("Mission clear timed out waiting for Pixhawk ACK")
            if event.get("event") != "mission_clear_complete":
                raise RuntimeError(event.get("message") or "Mission clear failed")
            return

        payload = ";".join(",".join(str(value) for value in item) for item in wire_items)
        self._send_command(f"MISSION_UPLOAD|{payload}")
        event = self._wait_event(
            {"mission_upload_complete", "mission_upload_failed", "command_error"},
            timeout=max(45.0, len(wire_items) * 6.0),
        )
        if event is None:
            raise TimeoutError("Mission upload timed out waiting for Pixhawk ACK")
        if event.get("event") != "mission_upload_complete":
            raise RuntimeError(event.get("message") or "Mission upload failed")

        downloaded = self.download_mission()
        if len(downloaded) != uploadable_count:
            raise RuntimeError(
                f"Mission verify failed: Pixhawk has {len(downloaded)} usable items, expected {uploadable_count}"
            )

    def download_mission(self):
        self._send_command("MISSION_DOWNLOAD")
        event = self._wait_event({"mission_downloaded", "command_error"}, timeout=15.0)
        if event is None:
            raise TimeoutError("Mission download timed out waiting for C++ bridge result")
        if event.get("event") == "command_error":
            raise RuntimeError(event.get("message") or "Mission download failed")
        return self._mission_items_from_wire(event.get("items") or [])

    def _read_stdout(self):
        if self.process is None or self.process.stdout is None:
            return
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                if payload.get("type") == "event":
                    self._event_queue.put(payload)
                    event_name = payload.get("event") or "event"
                    level = payload.get("level") or "INFO"
                    message = payload.get("message") or event_name
                    self.log(level, f"C++ bridge: {message}")
                else:
                    self._queue.put(payload)
            except json.JSONDecodeError:
                self.log("WARNING", f"C++ bridge sent invalid JSON: {line[:120]}")

    def _read_stderr(self):
        if self.process is None or self.process.stderr is None:
            return
        for line in self.process.stderr:
            message = line.strip()
            if message:
                self._startup_error = message
                self._stderr_queue.put(message)
                self.log("INFO", f"C++ bridge: {message}")

    def _collect_stderr_startup_error(self):
        messages = []
        while True:
            try:
                messages.append(self._stderr_queue.get_nowait())
            except queue.Empty:
                break
        return "; ".join(messages)

    def _telemetry_from_dict(self, data: dict) -> TelemetryData:
        return TelemetryData(
            timestamp=float(data.get("timestamp") or time.time()),
            connected=bool(data.get("connected", True)),
            mode=data.get("mode"),
            armed=data.get("armed"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            relative_altitude=data.get("relative_altitude"),
            absolute_altitude=data.get("absolute_altitude"),
            ground_speed=data.get("ground_speed"),
            air_speed=data.get("air_speed"),
            vertical_speed=data.get("vertical_speed"),
            pitch=data.get("pitch"),
            roll=data.get("roll"),
            yaw=data.get("yaw"),
            heading=data.get("heading"),
            battery_voltage=data.get("battery_voltage"),
            battery_current=data.get("battery_current"),
            battery_remaining=data.get("battery_remaining"),
            gps_fix_type=data.get("gps_fix_type"),
            satellites_visible=data.get("satellites_visible"),
            signal_quality=data.get("signal_quality"),
        )

    def _last_data_with_connection(self, connected: bool) -> TelemetryData:
        data = self._last_data
        data.connected = connected
        return data

    def _send_command(self, command: str):
        if self.process is None or self.process.stdin is None or self.process.poll() is not None:
            raise RuntimeError("C++ bridge is not running")
        self.process.stdin.write(command.strip() + "\n")
        self.process.stdin.flush()

    def _wait_event(self, names: set, timeout: float):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                event = self._event_queue.get(timeout=min(0.2, max(0.01, deadline - time.time())))
            except queue.Empty:
                continue
            if event.get("event") in names:
                return event
        return None

    def _build_mission_wire_items(self, mission_items, include_home: bool = False):
        mission_items = list(mission_items or [])
        wire_items = []
        if include_home:
            home = self._build_home_wire_item(mission_items)
            if home is not None:
                wire_items.append(home)
        for item in mission_items:
            wire = self._mission_item_to_wire(item)
            if wire is not None:
                wire_items.append(wire)
        return wire_items

    def _build_home_wire_item(self, mission_items):
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
        return self._wire_tuple(0, 16, 0.0, 0.0, 0.0, 0.0, lat, lon, alt)

    def _mission_item_to_wire(self, item):
        item_type = getattr(item, "item_type", None)
        lat = getattr(item, "latitude", None)
        lon = getattr(item, "longitude", None)
        alt = float(getattr(item, "altitude", 50.0) or 50.0)
        params = dict(getattr(item, "parameters", {}) or {})
        p1 = float(params.get("param1", params.get("delay", 0.0)) or 0.0)
        p2 = float(params.get("param2", params.get("acceptance_radius", 0.0)) or 0.0)
        p3 = float(params.get("param3", params.get("pass_radius", 0.0)) or 0.0)
        p4 = float(params.get("param4", params.get("yaw", 0.0)) or 0.0)
        frame = self._frame_id(params.get("frame", "Relative"))

        if item_type == MissionItemType.WAYPOINT:
            if lat is None or lon is None:
                return None
            return self._wire_tuple(frame, 16, p1, p2, p3, p4, lat, lon, alt)
        if item_type == MissionItemType.TAKEOFF:
            if lat is None or lon is None:
                return None
            return self._wire_tuple(frame, 22, p1, p2, p3, p4, lat, lon, alt)
        if item_type == MissionItemType.LAND:
            if lat is None or lon is None:
                return None
            return self._wire_tuple(frame, 21, p1, p2, p3, p4, lat, lon, 0.0)
        if item_type == MissionItemType.RTL:
            self.log("WARNING", "Skipping RTL item during Pixhawk mission upload; use RTL mode button instead")
            return None
        if item_type == MissionItemType.DO_LAND_START:
            return self._wire_tuple_raw(2, 189, p1, p2, p3, p4, 0, 0, 0.0)
        if item_type == MissionItemType.DO_JUMP:
            jump_to = float(params.get("jump_to", params.get("param1", 0)) or 0)
            repeat = float(params.get("repeat", params.get("param2", 1)) or 1)
            return self._wire_tuple_raw(2, 177, jump_to, repeat, p3, p4, 0, 0, 0.0)
        return None

    def _wire_tuple(self, frame, command, p1, p2, p3, p4, lat, lon, alt):
        return self._wire_tuple_raw(
            frame,
            command,
            p1,
            p2,
            p3,
            p4,
            int(float(lat) * 1e7),
            int(float(lon) * 1e7),
            float(alt),
        )

    @staticmethod
    def _frame_id(frame: str) -> int:
        text = str(frame or "").strip().upper()
        if text in {"ABSOLUTE", "GLOBAL"}:
            return 5
        if text in {"TERRAIN", "GLOBAL_TERRAIN_ALT"}:
            return 11
        return 6

    @staticmethod
    def _wire_tuple_raw(frame, command, p1, p2, p3, p4, x, y, z):
        return (
            int(frame),
            int(command),
            float(p1),
            float(p2),
            float(p3),
            float(p4),
            int(x),
            int(y),
            float(z),
        )

    def _mission_items_from_wire(self, raw_items):
        items = []
        rows = sorted(
            [raw for raw in (raw_items or []) if isinstance(raw, dict)],
            key=lambda item: int(item.get("seq", 0) or 0),
        )
        for index, raw in enumerate(rows):
            seq = int(raw.get("seq", index) or 0)
            command = int(raw.get("command", 0))
            frame = int(raw.get("frame", 0))
            x = int(raw.get("x", 0) or 0)
            y = int(raw.get("y", 0) or 0)
            z = float(raw.get("z", 50.0) or 50.0)

            latitude = float(x) / 1e7 if x else None
            longitude = float(y) / 1e7 if y else None
            item_type = MissionItemType.WAYPOINT
            params = {
                "param1": float(raw.get("p1", raw.get("param1", 0.0)) or 0.0),
                "param2": float(raw.get("p2", raw.get("param2", 0.0)) or 0.0),
                "param3": float(raw.get("p3", raw.get("param3", 0.0)) or 0.0),
                "param4": float(raw.get("p4", raw.get("param4", 0.0)) or 0.0),
                "frame": "Relative" if frame == 6 else "Global",
            }

            if command == 22:
                item_type = MissionItemType.TAKEOFF
            elif command == 21:
                item_type = MissionItemType.LAND
            elif command == 20:
                continue
            elif command == 189:
                item_type = MissionItemType.DO_LAND_START
                latitude = None
                longitude = None
                z = 0.0
            elif command == 177:
                item_type = MissionItemType.DO_JUMP
                latitude = None
                longitude = None
                z = 0.0
                params["jump_to"] = int(params["param1"])
                params["repeat"] = int(params["param2"])
            elif command != 16:
                continue

            if item_type in (MissionItemType.WAYPOINT, MissionItemType.TAKEOFF, MissionItemType.LAND) and (
                latitude is None or longitude is None
            ):
                continue

            items.append(MissionItem(
                item_type=item_type,
                sequence=max(0, seq),
                latitude=latitude,
                longitude=longitude,
                altitude=z,
                parameters=params,
            ))
        return items

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
    def _bridge_path() -> str:
        candidates = []
        try:
            import config
            candidates.append(str(getattr(config, "CPP_TELEMETRY_BRIDGE_PATH")))
        except Exception:
            pass
        candidates.extend([
            os.path.abspath(os.path.join("backend_cpp", "build_nmake", "telemetry_bridge.exe")),
            os.path.abspath(os.path.join("backend_cpp", "build", "telemetry_bridge.exe")),
            os.path.abspath(os.path.join("backend_cpp", "build", "Release", "telemetry_bridge.exe")),
        ])
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return candidates[0]

    def _cleanup_stale_bridge_processes(self):
        if not sys.platform.startswith("win"):
            return
        subprocess.run(
            ["taskkill", "/F", "/IM", "telemetry_bridge.exe", "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    @staticmethod
    def _taskkill_process_tree(pid):
        if not sys.platform.startswith("win") or not pid:
            return
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid), "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
