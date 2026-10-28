import sys
from pathlib import Path

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

# Telemetry
TELEMETRY_UPDATE_INTERVAL_MS = 100
TELEMETRY_RATE_HZ = 20
TELEMETRY_PERF_DEBUG = True
ALTITUDE_VOICE_ENABLED = True
USE_CPP_TELEMETRY_BACKEND = True
CPP_TELEMETRY_BRIDGE_PATH = str(BASE_DIR / "backend_cpp" / "build_nmake" / "telemetry_bridge.exe")

# Video
VIDEO_SOURCE = "udp-h264://0.0.0.0:5600"
VIDEO_FPS = 30
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480
VIDEO_UDP_H264_DECODER = "gstreamer"  # auto, ffmpeg, gstreamer
VIDEO_UDP_INPUT_FORMAT = "rtp-jpeg"  # udp, rtp, rtp-jpeg, mpegts, raw-h264
FFMPEG_BIN_DIR = ""
GSTREAMER_BIN_DIR = ""
REFEREE_VIDEO_STREAM_PORT = 8092
REFEREE_VIDEO_STREAM_FPS = 10
REFEREE_VIDEO_JPEG_QUALITY = 70
REFEREE_VIDEO_UPLOAD_PATH = "/api/kamera_gonder"

# Map
DEFAULT_LATITUDE = 38.34
DEFAULT_LONGITUDE = 38.43
DEFAULT_ZOOM = 16
MAP_MBTILES_PATH = str(BASE_DIR / "assets" / "maps" / "blackbox_ucus_alani_bing_z14_z19.mbtiles")
# Extra offline imagery used by the log-analysis viewer.  The primary map is
# still preferred wherever both sources contain a tile; analysis caches fill
# log locations outside the main flight area.
ANALYSIS_MBTILES_GLOB = "analysis_*.mbtiles"
DEFENSE_ZONES_PATH = str(BASE_DIR / "assets" / "data" / "defense_zones.json")
PARAMETER_METADATA_PATH = str(BASE_DIR / "assets" / "data" / "ParameterMetaDataBackup.xml")
PARAMETER_METADATA_URL = "https://raw.githubusercontent.com/ArduPilot/MissionPlanner/master/ParameterMetaDataBackup.xml"

# Set to 0.0 if the map aircraft points correctly. Use 180.0 if it appears reversed.
AIRCRAFT_HEADING_OFFSET_DEG = 180.0

# Mission
DEFAULT_ALTITUDE = 50.0
GUIDED_DEFAULT_ALTITUDE_M = 100.0
DEFAULT_SPEED = 10.0

# UI
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
WINDOW_TITLE = "Ground Station - Teknofest IHA"
STYLESHEET_PATH = str(BASE_DIR / "resources" / "styles.qss")

# 3D aircraft model
AIRCRAFT_MODEL_PATH = str(BASE_DIR / "assets" / "models" / "blackbox_aircraft_reduced_body_3mf.zip")
AIRCRAFT_MODEL_MAX_FACES = 0
AIRCRAFT_MODEL_RENDER_MODE = "surface"
AIRCRAFT_MODEL_OUTLINE_DETAIL_LINES = 1400
AIRCRAFT_MODEL_VIEW_SCALE = 1.38
AIRCRAFT_MODEL_MAX_FPS = 10
AIRCRAFT_MODEL_MIN_ATTITUDE_DELTA_DEG = 0.15
AIRCRAFT_MODEL_SMOOTHING_ALPHA = 0.22
AIRCRAFT_MODEL_DRAW_EDGES = False
AIRCRAFT_MODEL_USE_TELEMETRY_YAW = True
AIRCRAFT_MODEL_INPUT_PITCH_ZERO_DEG = 0.0
AIRCRAFT_MODEL_INPUT_ROLL_ZERO_DEG = 0.0
AIRCRAFT_MODEL_INPUT_YAW_FRONT_DEG = 0.0
AIRCRAFT_MODEL_NEUTRAL_PITCH_DEG = 0.0
AIRCRAFT_MODEL_NEUTRAL_ROLL_DEG = 0.0

# Fine calibration for the STL orientation. Adjust these only if the model axis
# does not visually match the Pixhawk attitude axis.
AIRCRAFT_MODEL_PITCH_SIGN = -1.0
AIRCRAFT_MODEL_ROLL_SIGN = -1.0
AIRCRAFT_MODEL_YAW_SIGN = 1.0
AIRCRAFT_MODEL_PITCH_OFFSET_DEG = 0.0
AIRCRAFT_MODEL_ROLL_OFFSET_DEG = 0.0
AIRCRAFT_MODEL_YAW_OFFSET_DEG = 180.0

# Viewer-only alignment: keeps the aircraft neutral on the depth/Z axis.
# 180 degrees shows the Pixhawk nose facing away from the operator.
AIRCRAFT_MODEL_VIEW_YAW_OFFSET_DEG = 180.0
AIRCRAFT_MODEL_VIEW_CAMERA_PITCH_DEG = -75.0

# Flight HUD attitude indicator visual calibration. These affect only the round
# HUD drawing, not telemetry values or the 3D model.
HUD_ATTITUDE_PITCH_SIGN = 1.0
HUD_ATTITUDE_ROLL_SIGN = -1.0
