from enum import Enum
from time import sleep
from datetime import datetime
from typing import Optional
import threading
import time

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel


class Scenario(str, Enum):
    normal = "normal"
    expired = "401"
    bad_request = "400"
    server_error = "500"
    delayed = "delayed"
    empty_hss = "empty_hss"
    non_empty_hss = "non_empty_hss"
    opponents = "opponents"


app = FastAPI(title="TEKNOFEST Mock Competition Server")
state = {
    "scenario": Scenario.normal,
    "token": "mock-token",
    "telemetry_count": 0,
    "camera_stream_url": "",
    "camera_frame": None,
    "camera_frame_time": 0.0,
}
camera_lock = threading.Lock()


class ScenarioRequest(BaseModel):
    scenario: Scenario


def apply_scenario():
    scenario = state["scenario"]
    if scenario == Scenario.delayed:
        sleep(2)
    if scenario == Scenario.bad_request:
        raise HTTPException(status_code=400, detail="bad request scenario")
    if scenario == Scenario.server_error:
        raise HTTPException(status_code=500, detail="server error scenario")
    if scenario == Scenario.expired:
        raise HTTPException(status_code=401, detail="login expired scenario")


def server_time():
    now = datetime.now()
    return {
        "gun": now.day,
        "saat": now.hour,
        "dakika": now.minute,
        "saniye": now.second,
        "milisaniye": int(now.microsecond / 1000),
    }


def camera_status():
    with camera_lock:
        return {
            "stream_url": state["camera_stream_url"],
            "has_frame": state["camera_frame"] is not None,
            "age_ms": int((time.time() - state["camera_frame_time"]) * 1000)
            if state["camera_frame_time"]
            else None,
        }


def panel_html():
    return """
<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Black Box Hakem Paneli</title>
  <style>
    body { margin: 0; background: #1e1e1e; color: #f5f5f5; font-family: Arial, sans-serif; }
    .page { padding: 18px; display: grid; grid-template-columns: 1.1fr 1.8fr 1.2fr; gap: 12px; }
    h1 { grid-column: 1 / -1; text-align: center; letter-spacing: 5px; margin: 0 0 4px; }
    .connect { grid-column: 1 / -1; text-align: center; font-size: 13px; }
    .card { border: 1px solid #6e6e6e; border-radius: 8px; background: #2a2a2a; padding: 10px; }
    .card h2 { font-size: 15px; margin: 0 0 8px; }
    pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 12px; }
    .camera-card { grid-column: 2 / 3; }
    .camera-frame { height: 260px; border: 1px solid #8a8a8a; border-radius: 6px; background: #050505; overflow: hidden; }
    .camera-frame img { width: 100%; height: 100%; object-fit: contain; display: block; }
    .status { color: #71ff60; font-weight: bold; }
    input { background: #202020; color: #fff; border: 1px solid #777; border-radius: 3px; padding: 4px; width: 240px; }
    button { background: #ffb000; border: 0; border-radius: 3px; padding: 5px 12px; cursor: pointer; }
  </style>
</head>
<body>
  <div class="page">
    <h1>BLACK BOX HAKEM PANELİ</h1>
    <div class="connect">
      API Bağlantısı:
      <input id="apiUrl" value="http://127.0.0.1:5000">
      <button>Bağlan</button>
      <span class="status">● Bağlı</span>
    </div>
    <section class="card"><h2>HSS VERİLERİ</h2><pre id="hss">Yükleniyor...</pre></section>
    <section class="card"><h2>HEDEF İHA TELEMETRİSİ</h2><pre id="telemetry">Telemetri bekleniyor...</pre></section>
    <section class="card"><h2>SİSTEM LOGLARI</h2><pre id="logs">Kamera akışı panel içine bağlandı.</pre></section>
    <section class="card"><h2>SUNUCU SAATİ</h2><pre id="clock">--:--:--</pre></section>
    <section class="card camera-card">
      <h2>KAMERA AKIŞI</h2>
      <div class="camera-frame">
        <img id="cameraStream" src="/api/kamera_akisi.mjpg" alt="Kamera akışı">
      </div>
    </section>
    <section class="card"><h2>DİĞER İHALAR</h2><pre>{}</pre></section>
  </div>
  <script>
    async function refreshPanel() {
      try {
        const [clock, hss, camera] = await Promise.all([
          fetch('/api/sunucusaati').then(r => r.json()),
          fetch('/api/hss_koordinatlari').then(r => r.json()),
          fetch('/api/kamera_durumu').then(r => r.json())
        ]);
        document.getElementById('clock').textContent =
          `${String(clock.saat).padStart(2, '0')}:${String(clock.dakika).padStart(2, '0')}:${String(clock.saniye).padStart(2, '0')}`;
        document.getElementById('hss').textContent = JSON.stringify(hss, null, 2);
        document.getElementById('logs').textContent =
          camera.has_frame
            ? `Kamera frame alındı. Gecikme: ${camera.age_ms} ms\\nStream URL: ${camera.stream_url || '-'}`
            : `Kamera bekleniyor...\\nStream URL: ${camera.stream_url || '-'}`;
      } catch (err) {
        document.getElementById('logs').textContent = String(err);
      }
    }
    setInterval(refreshPanel, 1000);
    refreshPanel();
  </script>
</body>
</html>
""".strip()


@app.post("/scenario")
def set_scenario(req: ScenarioRequest):
    state["scenario"] = req.scenario
    return {"ok": True, "scenario": req.scenario}


@app.get("/", response_class=HTMLResponse)
def referee_panel():
    return HTMLResponse(panel_html())


@app.post("/api/giris")
def login(payload: dict):
    username = payload.get("kadi") or payload.get("username")
    password = payload.get("sifre") or payload.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="missing credentials")
    state["scenario"] = Scenario.normal if state["scenario"] == Scenario.expired else state["scenario"]
    return {"takim_numarasi": 1, "token": state["token"], "sunucusaati": server_time()}


@app.get("/api/sunucusaati")
def get_server_time():
    apply_scenario()
    return server_time()


@app.post("/api/telemetri_gonder")
def telemetry(payload: dict, authorization: Optional[str] = Header(default=None)):
    apply_scenario()
    state["telemetry_count"] += 1
    if state["scenario"] == Scenario.opponents:
        return {
            "ok": True,
            "sunucusaati": server_time(),
            "konumBilgileri": [
                {"takim_numarasi": 2, "iha_enlem": 39.91, "iha_boylam": 32.81, "iha_irtifa": 120.0}
            ],
        }
    return {"ok": True, "count": state["telemetry_count"], "sunucusaati": server_time(), "konumBilgileri": []}


@app.post("/api/kamera_adresi")
def set_camera_address(payload: dict):
    stream_url = payload.get("stream_url") or payload.get("url") or payload.get("kamera_url") or ""
    with camera_lock:
        state["camera_stream_url"] = str(stream_url)
    return {"ok": True, "stream_url": stream_url}


@app.post("/api/video_stream")
def set_video_stream(payload: dict):
    return set_camera_address(payload)


@app.get("/api/kamera_durumu")
def get_camera_status():
    return camera_status()


@app.post("/api/kamera_gonder")
async def receive_camera_frame(request: Request):
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="empty camera frame")
    with camera_lock:
        state["camera_frame"] = bytes(data)
        state["camera_frame_time"] = time.time()
    return {"ok": True, "bytes": len(data)}


@app.get("/api/kamera_snapshot.jpg")
def camera_snapshot():
    with camera_lock:
        frame = state["camera_frame"]
    if not frame:
        raise HTTPException(status_code=503, detail="camera frame not ready")
    return Response(content=frame, media_type="image/jpeg")


@app.get("/snapshot.jpg")
def camera_snapshot_alias():
    return camera_snapshot()


@app.get("/api/kamera_akisi.mjpg")
def camera_stream():
    def generate():
        last_frame = None
        while True:
            with camera_lock:
                frame = state["camera_frame"]
            if frame and frame != last_frame:
                last_frame = frame
                yield b"--frame\r\n"
                yield b"Content-Type: image/jpeg\r\n"
                yield f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                yield frame
                yield b"\r\n"
            time.sleep(0.1)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, private", "Pragma": "no-cache"},
    )


@app.get("/video.mjpg")
def camera_stream_alias():
    return camera_stream()


@app.post("/api/kilitlenme_bilgisi")
def lock_info(payload: dict):
    apply_scenario()
    return {"ok": True}


@app.post("/api/kamikaze_bilgisi")
def kamikaze_info(payload: dict):
    apply_scenario()
    if not payload.get("qrMetni"):
        raise HTTPException(status_code=400, detail="empty qr")
    return {"ok": True}


@app.get("/api/qr_koordinati")
def qr_coordinate():
    apply_scenario()
    return {"qrEnlem": 39.925, "qrBoylam": 32.836}


@app.get("/api/hss_koordinatlari")
def hss_coordinates():
    apply_scenario()
    if state["scenario"] == Scenario.empty_hss:
        return []
    return {
        "sunucusaati": server_time(),
        "hss_koordinat_bilgileri": [
            {"id": 1, "hssEnlem": 39.93, "hssBoylam": 32.82, "hssYaricap": 80.0},
            {"id": 2, "hssEnlem": 39.94, "hssBoylam": 32.83, "hssYaricap": 120.0},
        ],
    }
