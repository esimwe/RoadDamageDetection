import asyncio
import threading
import time
import requests as _requests
from pathlib import Path
from typing import List, NamedTuple

import cv2
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
from livekit.api import LiveKitAPI, AccessToken, VideoGrants
from livekit import rtc

from sample_utils.download import download_file
from sample_utils.auth import session_kontrol

API_URL = "http://127.0.0.1:8502/api"
LIVEKIT_URL = "wss://rtc.turna.im"
LIVEKIT_API_KEY = "APIJdbJEJpErro2"
LIVEKIT_API_SECRET = "13Xn1wdGlqeY1ELkE1E3e6VG26qFBzFAWVgeOHGDUReA"

st.set_page_config(
    page_title="Gerçek Zamanlı Tespit",
    page_icon="📷",
    layout="centered",
    initial_sidebar_state="expanded"
)

session_kontrol()

HERE = Path(__file__).parent
ROOT = HERE.parent

MODEL_URL = "https://github.com/oracl4/RoadDamageDetection/raw/main/models/YOLOv8_Small_RDD.pt"
MODEL_LOCAL_PATH = ROOT / "./models/YOLOv8_Small_RDD.pt"
download_file(MODEL_URL, MODEL_LOCAL_PATH, expected_size=89569358)

# Model yükle
cache_key = "sky_model_rdd"
if cache_key in st.session_state:
    net = st.session_state[cache_key]
else:
    net = YOLO(MODEL_LOCAL_PATH)
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net.to(device)
    st.session_state[cache_key] = net

CLASSES = ["Boyuna Çatlak", "Enine Çatlak", "Ağ Çatlağı", "Çukur"]
COLORS = {0: (0, 255, 0), 1: (255, 165, 0), 2: (255, 0, 0), 3: (255, 0, 255)}

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]
_pil_font = ImageFont.load_default()
for fp in FONT_PATHS:
    try:
        _pil_font = ImageFont.truetype(fp, 20)
        break
    except:
        continue

def draw_text_turkish(img_bgr, text, x, y, color):
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    bbox = draw.textbbox((x, y), text, font=_pil_font)
    draw.rectangle(bbox, fill=color)
    draw.text((x, y), text, font=_pil_font, fill=(255, 255, 255))
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def _livekit_token(room_name: str, identity: str, can_publish: bool) -> str:
    token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token.identity = identity
    token.name = identity
    token.with_grants(VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=can_publish,
        can_subscribe=True,
    ))
    return token.to_jwt()

def _agent_thread(room_name: str, vehicle_id: int, auth_token: str, score_threshold: float, stop_event: threading.Event):
    """LiveKit odasına agent olarak katıl, frame'leri SKY Modeli'nden geçir, API'ye gönder."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def process_video(track, last_frame_time_ref):
        video_stream = rtc.VideoStream(track)
        async for frame_event in video_stream:
            if stop_event.is_set():
                break
            now = time.time()
            if now - last_frame_time_ref[0] < 2.0:
                continue
            last_frame_time_ref[0] = now
            try:
                frame = frame_event.frame
                raw = np.frombuffer(frame.data, dtype=np.uint8)
                total = frame.height * frame.width
                if raw.size == total * 4:
                    arr = raw.reshape(frame.height, frame.width, 4)
                    bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                elif raw.size == total * 3 // 2:
                    arr = raw.reshape(frame.height * 3 // 2, frame.width)
                    bgr = cv2.cvtColor(arr, cv2.COLOR_YUV2BGR_I420)
                elif raw.size == total * 3:
                    arr = raw.reshape(frame.height, frame.width, 3)
                    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                else:
                    continue
                h, w = bgr.shape[:2]
                resized = cv2.resize(bgr, (640, 640), interpolation=cv2.INTER_AREA)
                results = net.predict(resized, conf=score_threshold, verbose=False)
                out = cv2.resize(resized, (w, h), interpolation=cv2.INTER_AREA)
                for result in results:
                    for box in result.boxes.cpu():
                        cls_id = int(box.cls.item())
                        score = float(box.conf.item())
                        coords = box.xyxy[0].numpy().astype(int)
                        label = CLASSES[cls_id]
                        sx, sy = w / 640, h / 640
                        x1 = int(coords[0] * sx); y1 = int(coords[1] * sy)
                        x2 = int(coords[2] * sx); y2 = int(coords[3] * sy)
                        color = COLORS.get(cls_id, (255, 255, 255))
                        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
                        out = draw_text_turkish(out, f"{label} %{int(score*100)}", x1, max(y1-26, 0), color)
                _, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 70])
                headers = {"Authorization": f"Bearer {auth_token}"}
                # Frame'i panele gönder
                _requests.post(
                    f"{API_URL}/vehicles/{vehicle_id}/frame",
                    headers=headers,
                    files={"file": ("frame.jpg", buf.tobytes(), "image/jpeg")},
                    timeout=3
                )
                # Tespitleri veritabanına kaydet
                if results:
                    tespitler = []
                    for result in results:
                        for box in result.boxes.cpu():
                            tespitler.append({
                                "hasar_tipi": int(box.cls.item()),
                                "guven_skoru": round(float(box.conf.item()), 3)
                            })
                    if tespitler:
                        _requests.post(
                            f"{API_URL}/vehicles/{vehicle_id}/detections",
                            headers={**headers, "Content-Type": "application/json"},
                            json=tespitler,
                            timeout=3
                        )
            except Exception:
                pass

    async def run():
        agent_token = _livekit_token(room_name, "sky-agent", can_publish=False)
        room = rtc.Room()
        last_frame_time_ref = [0.0]
        video_tasks = []

        @room.on("track_subscribed")
        def on_track(track, publication, participant):
            if track.kind == rtc.TrackKind.KIND_VIDEO:
                task = loop.create_task(process_video(track, last_frame_time_ref))
                video_tasks.append(task)

        import logging as _log
        _log.getLogger(__name__).info(f"[SKY-AGENT] LiveKit'e bağlanıyor: {LIVEKIT_URL} oda={room_name}")
        await room.connect(LIVEKIT_URL, agent_token)
        _log.getLogger(__name__).info(f"[SKY-AGENT] Bağlandı, track bekleniyor...")
        while not stop_event.is_set():
            await asyncio.sleep(0.5)
        for t in video_tasks:
            t.cancel()
        await room.disconnect()
        _log.getLogger(__name__).info("[SKY-AGENT] Bağlantı kapatıldı")

    try:
        loop.run_until_complete(run())
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[SKY-AGENT] hata: {e}", exc_info=True)
    finally:
        loop.close()

# --- UI ---
st.title("Yol Hasar Tespiti - Gerçek Zamanlı")
st.write("Kameranızı başlatın, SKY Modeli hasarları tespit edip panele gönderecek.")

arac = st.session_state.get("secilen_arac", {})
vehicle_id = arac.get("id")
auth_token = st.session_state.get("token", "")

score_threshold = st.slider("Güven Eşiği", min_value=0.0, max_value=1.0, value=0.5, step=0.05)

room_name = f"rdd-vehicle-{vehicle_id}"

# Tarayıcı token (yayınlayabilir)
browser_token = _livekit_token(room_name, f"arac-{vehicle_id}", can_publish=True)

col1, col2 = st.columns(2)
with col1:
    basla = st.button("▶ Kamerayı Başlat", use_container_width=True, type="primary")
with col2:
    durdur = st.button("■ Durdur", use_container_width=True)

if basla:
    if "_agent_stop" in st.session_state:
        st.session_state["_agent_stop"].set()
    stop_event = threading.Event()
    st.session_state["_agent_stop"] = stop_event
    t = threading.Thread(
        target=_agent_thread,
        args=(room_name, vehicle_id, auth_token, score_threshold, stop_event),
        daemon=True
    )
    t.start()
    st.session_state["_agent_running"] = True

if durdur:
    if "_agent_stop" in st.session_state:
        st.session_state["_agent_stop"].set()
    st.session_state["_agent_running"] = False

running = st.session_state.get("_agent_running", False)

if running:
    st.success("Kamera aktif — SKY Modeli çalışıyor")
    # LiveKit JS client ile tarayıcıdan yayın
    components.html(f"""
<!DOCTYPE html>
<html>
<head>
<script src="https://cdn.jsdelivr.net/npm/livekit-client@2/dist/livekit-client.umd.min.js"></script>
<style>
  body {{ margin:0; background:#000; }}
  video {{ width:100%; max-height:400px; border-radius:8px; }}
  #status {{ color:#0f0; font-family:monospace; padding:4px 8px; font-size:12px; }}
</style>
</head>
<body>
<div id="status">Bağlanıyor...</div>
<video id="localVideo" autoplay muted playsinline></video>
<script>
(async () => {{
  const {{ Room, RoomEvent, createLocalVideoTrack }} = LivekitClient;
  const room = new Room();
  const statusEl = document.getElementById('status');
  const videoEl = document.getElementById('localVideo');

  room.on(RoomEvent.Connected, () => {{ statusEl.textContent = '✓ LiveKit bağlı — yayın aktif'; }});
  room.on(RoomEvent.Disconnected, () => {{ statusEl.textContent = '✗ Bağlantı kesildi'; }});

  await room.connect("{LIVEKIT_URL}", "{browser_token}");

  const videoTrack = await createLocalVideoTrack({{
    facingMode: "environment",
    resolution: {{ width: 1280, height: 720 }}
  }});

  videoTrack.attach(videoEl);
  await room.localParticipant.publishTrack(videoTrack);
  statusEl.textContent = '✓ Kamera yayında — SKY Modeli analiz ediyor';
}})();
</script>
</body>
</html>
""", height=450)
else:
    st.info("Kamerayı başlatmak için '▶ Kamerayı Başlat' butonuna basın.")