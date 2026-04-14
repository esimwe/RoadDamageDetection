import os
import logging
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np
import streamlit as st

# Deep learning framework
from ultralytics import YOLO
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

from sample_utils.download import download_file
from sample_utils.auth import session_kontrol

st.set_page_config(
    page_title="Görüntü Tespiti",
    page_icon="📷",
    layout="centered",
    initial_sidebar_state="expanded"
)

session_kontrol()

HERE = Path(__file__).parent
ROOT = HERE.parent

logger = logging.getLogger(__name__)

MODEL_URL = "https://github.com/oracl4/RoadDamageDetection/raw/main/models/YOLOv8_Small_RDD.pt"  # noqa: E501
MODEL_LOCAL_PATH = ROOT / "./models/YOLOv8_Small_RDD.pt"
download_file(MODEL_URL, MODEL_LOCAL_PATH, expected_size=89569358)

# Session-specific caching
# Load the model
cache_key = "yolov8smallrdd"
if cache_key in st.session_state:
    net = st.session_state[cache_key]
else:
    net = YOLO(MODEL_LOCAL_PATH)
    import torch
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    net.to(device)
    st.session_state[cache_key] = net

CLASSES = [
    "Boyuna Çatlak",
    "Enine Çatlak",
    "Ağ Çatlağı",
    "Çukur"
]

COLORS = {
    0: (0, 255, 0),
    1: (255, 165, 0),
    2: (255, 0, 0),
    3: (255, 0, 255),
}

FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]
_pil_font = ImageFont.load_default()
for _fp in FONT_PATHS:
    try:
        _pil_font = ImageFont.truetype(_fp, 20)
        break
    except:
        continue

def draw_detections(img_bgr, detections, w_ori, h_ori):
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    sx = w_ori / 640
    sy = h_ori / 640
    for det in detections:
        color = COLORS.get(det.class_id, (255, 255, 255))
        x1 = int(det.box[0] * sx)
        y1 = int(det.box[1] * sy)
        x2 = int(det.box[2] * sx)
        y2 = int(det.box[3] * sy)
        draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=2)
        text = f"{det.label} %{int(det.score*100)}"
        bbox = draw.textbbox((x1, max(y1 - 26, 0)), text, font=_pil_font)
        draw.rectangle(bbox, fill=color)
        draw.text((x1, max(y1 - 26, 0)), text, font=_pil_font, fill=(255, 255, 255))
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

class Detection(NamedTuple):
    class_id: int
    label: str
    score: float
    box: np.ndarray

st.title("Yol Hasar Tespiti - Görüntü")
st.write("Görüntü yükleyerek yol hasarlarını tespit edin. Fotoğraf yükleyin ve analizi başlatın. Bu bölüm tekil görüntü analizleri için kullanışlıdır.")

image_file = st.file_uploader("Upload Image", type=['png', 'jpg'])

score_threshold = st.slider("Güven Eşiği", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
st.write("Hasar tespit edilemiyorsa eşik değerini düşürün, yanlış tespit varsa artırın.")

if image_file is not None:

    # Load the image
    image = Image.open(image_file)
    
    col1, col2 = st.columns(2)

    # Perform inference
    _image = np.array(image)
    h_ori = _image.shape[0]
    w_ori = _image.shape[1]

    image_resized = cv2.resize(_image, (640, 640), interpolation = cv2.INTER_AREA)
    results = net.predict(image_resized, conf=score_threshold)
    
    # Save the results
    for result in results:
        boxes = result.boxes.cpu()
        detections = [
           Detection(
               class_id=int(_box.cls.item()),
               label=CLASSES[int(_box.cls.item())],
               score=float(_box.conf.item()),
               box=_box.xyxy[0].numpy().astype(int),
            )
            for _box in boxes
        ]

    _image_pred = draw_detections(image_resized, detections, w_ori, h_ori)

    # Original Image
    with col1:
        st.write("#### Görüntü")
        st.image(_image)
    
    # Predicted Image
    with col2:
        st.write("#### Tespit Sonuçları")
        st.image(_image_pred)

        # Download predicted image
        buffer = BytesIO()
        _downloadImages = Image.fromarray(_image_pred)
        _downloadImages.save(buffer, format="PNG")
        _downloadImagesByte = buffer.getvalue()

        downloadButton = st.download_button(
            label="Download Prediction Image",
            data=_downloadImagesByte,
            file_name="RDD_Prediction.png",
            mime="image/png"
        )