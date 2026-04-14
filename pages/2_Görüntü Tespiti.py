import os
import logging
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np
import streamlit as st

# Deep learning framework
from ultralytics import YOLO
from PIL import Image
from io import BytesIO

from sample_utils.download import download_file

st.set_page_config(
    page_title="Görüntü Tespiti",
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

    annotated_frame = results[0].plot()
    _image_pred = cv2.resize(annotated_frame, (w_ori, h_ori), interpolation = cv2.INTER_AREA)

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