import streamlit as st

st.set_page_config(
    page_title="Yol Hasar Tespit Sistemi",
    page_icon="🛣️",
)

st.divider()
st.title("Yol Hasar Tespit Sistemi")

st.markdown(
    """
    **Bursa Büyükşehir Belediyesi** Yol Hasar Tespit Sistemi, YOLOv8 derin öğrenme modeli kullanarak yol hasarlarını otomatik olarak tespit etmektedir.

    Bu uygulama, yol bakım süreçlerini hızlandırmak ve altyapı yönetimini kolaylaştırmak amacıyla tasarlanmıştır.

    Sistem aşağıdaki dört tür yol hasarını tespit edebilmektedir:
    - Boyuna Çatlak
    - Enine Çatlak
    - Ağ Çatlağı
    - Çukur

    Model, YOLOv8 mimarisi kullanılarak uluslararası yol hasar veri seti (CRDDC2022) üzerinde eğitilmiştir.

    Sol menüden kullanmak istediğiniz modülü seçebilirsiniz:
    - **Gerçek Zamanlı Tespit** — Kamera ile anlık analiz
    - **Görüntü Tespiti** — Fotoğraf yükleyerek analiz
    - **Video Tespiti** — Video dosyası yükleyerek analiz
"""
)

st.divider()

st.markdown(
    """
    © 2026 **Bursa Büyükşehir Belediyesi** — Tüm hakları saklıdır.
    """
)

