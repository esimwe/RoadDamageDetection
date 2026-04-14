import logging
import queue
from pathlib import Path
from typing import List, NamedTuple

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer
from PIL import Image, ImageDraw, ImageFont

# Deep learning framework
from ultralytics import YOLO

from sample_utils.download import download_file
from sample_utils.get_STUNServer import getSTUNServer

st.set_page_config(
    page_title="Gerçek Zamanlı Tespit",
    page_icon="📷",
    layout="centered",
    initial_sidebar_state="expanded"
)

HERE = Path(__file__).parent
ROOT = HERE.parent

logger = logging.getLogger(__name__)

MODEL_URL = "https://github.com/oracl4/RoadDamageDetection/raw/main/models/YOLOv8_Small_RDD.pt"  # noqa: E501
MODEL_LOCAL_PATH = ROOT / "./models/YOLOv8_Small_RDD.pt"
download_file(MODEL_URL, MODEL_LOCAL_PATH, expected_size=89569358)

# STUN Server
STUN_STRING = "stun:" + str(getSTUNServer())
STUN_SERVER = [{"urls": [STUN_STRING]}]

# Session-specific caching
# Load the model
cache_key = "yolov8smallrdd"
if cache_key in st.session_state:
    net = st.session_state[cache_key]
else:
    net = YOLO(MODEL_LOCAL_PATH)
    net.to("mps")
    st.session_state[cache_key] = net

CLASSES = [
    "Boyuna Çatlak",
    "Enine Çatlak",
    "Ağ Çatlağı",
    "Çukur"
]

class Detection(NamedTuple):
    class_id: int
    label: str
    score: float
    box: np.ndarray

st.title("Yol Hasar Tespiti - Gerçek Zamanlı")

st.write("USB Kamera veya araç kamerası kullanarak yol hasarlarını gerçek zamanlı tespit edin. Saha ekipleri için anlık izleme amacıyla kullanılabilir. Video giriş cihazını seçin ve analizi başlatın.")

# NOTE: The callback will be called in another thread,
#       so use a queue here for thread-safety to pass the data
#       from inside to outside the callback.
# TODO: A general-purpose shared state object may be more useful.
result_queue: "queue.Queue[List[Detection]]" = queue.Queue()

COLORS = {
    0: (0, 255, 0),    # Boyuna Çatlak - yeşil
    1: (255, 165, 0),  # Enine Çatlak - turuncu
    2: (255, 0, 0),    # Ağ Çatlağı - kırmızı
    3: (255, 0, 255),  # Çukur - mor
}

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
try:
    _pil_font = ImageFont.truetype(FONT_PATH, 20)
except:
    _pil_font = ImageFont.load_default()

def draw_text_turkish(img_bgr, text, x, y, color):
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    bbox = draw.textbbox((x, y), text, font=_pil_font)
    draw.rectangle(bbox, fill=color)
    draw.text((x, y), text, font=_pil_font, fill=(255, 255, 255))
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:

    image = frame.to_ndarray(format="bgr24")
    h_ori = image.shape[0]
    w_ori = image.shape[1]
    image_resized = cv2.resize(image, (640, 640), interpolation = cv2.INTER_AREA)
    results = net.predict(image_resized, conf=score_threshold, verbose=False)

    # Orijinal boyuta geri döndür
    _image = cv2.resize(image_resized, (w_ori, h_ori), interpolation = cv2.INTER_AREA)

    detections = []
    for result in results:
        boxes = result.boxes.cpu()
        for _box in boxes:
            cls_id = int(_box.cls.item())
            score = float(_box.conf.item())
            box = _box.xyxy[0].numpy().astype(int)
            label = CLASSES[cls_id]
            detections.append(Detection(class_id=cls_id, label=label, score=score, box=box))

            # Koordinatları orijinal boyuta ölçekle
            sx = w_ori / 640
            sy = h_ori / 640
            x1 = int(box[0] * sx)
            y1 = int(box[1] * sy)
            x2 = int(box[2] * sx)
            y2 = int(box[3] * sy)

            color_bgr = COLORS.get(cls_id, (255, 255, 255))
            cv2.rectangle(_image, (x1, y1), (x2, y2), color_bgr, 2)
            text = f"{label} %{int(score*100)}"
            _image = draw_text_turkish(_image, text, x1, max(y1 - 26, 0), color_bgr)

    result_queue.put(detections)

    return av.VideoFrame.from_ndarray(_image, format="bgr24")

kamera_secim = st.radio("Kamera Seçimi", ["Arka Kamera", "Ön Kamera"], horizontal=True)
facing_mode = "environment" if kamera_secim == "Arka Kamera" else "user"

webrtc_ctx = webrtc_streamer(
    key=f"road-damage-detection-{facing_mode}",
    mode=WebRtcMode.SENDRECV,
    rtc_configuration={"iceServers": STUN_SERVER},
    video_frame_callback=video_frame_callback,
    media_stream_constraints={
        "video": {
            "facingMode": facing_mode,
            "width": {"ideal": 1280, "min": 800},
        },
        "audio": False
    },
    async_processing=True,
)

score_threshold = st.slider("Güven Eşiği", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
st.write("Hasar tespit edilemiyorsa eşik değerini düşürün, yanlış tespit varsa artırın.")

st.divider()

if st.checkbox("Tespit Tablosunu Göster", value=False):
    if webrtc_ctx.state.playing:
        labels_placeholder = st.empty()
        while True:
            result = result_queue.get()
            labels_placeholder.table(result)