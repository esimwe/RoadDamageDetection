import streamlit as st
from sample_utils.auth import session_kontrol, kullanici_bilgisi, konum_takibi_baslat

st.set_page_config(
    page_title="Yol Hasar Tespit Sistemi",
    page_icon="🛣️",
)

session_kontrol()
kullanici_bilgisi()
konum_takibi_baslat()

st.divider()
st.title("Yol Hasar Tespit Sistemi")

a = st.session_state.secilen_arac

st.markdown(
    f"""
    **Bursa Büyükşehir Belediyesi** Yol Hasar Tespit Sistemi, YOLOv8 derin öğrenme modeli kullanarak yol hasarlarını otomatik olarak tespit etmektedir.

    **Aktif Araç:** {a['plaka']}

    Sol menüden kullanmak istediğiniz modülü seçebilirsiniz:
    - **Gerçek Zamanlı Tespit** — Kamera ile anlık analiz
    - **Görüntü Tespiti** — Fotoğraf yükleyerek analiz
    - **Video Tespiti** — Video dosyası yükleyerek analiz
    """
)

st.divider()
st.caption("© 2026 Bursa Büyükşehir Belediyesi — Tüm hakları saklıdır.")