import streamlit as st
import requests

st.set_page_config(
    page_title="Yol Hasar Tespit Sistemi",
    page_icon="🛣️",
)

API_URL = "http://127.0.0.1:8502/api"

# ── SESSION STATE ────────────────────────────────────────
if "token" not in st.session_state:
    st.session_state.token = None
if "kullanici" not in st.session_state:
    st.session_state.kullanici = None
if "secilen_arac" not in st.session_state:
    st.session_state.secilen_arac = None

# ── LOGIN SAYFASI ────────────────────────────────────────
def login_sayfasi():
    st.title("🛣️ Yol Hasar Tespit Sistemi")
    st.caption("Bursa Büyükşehir Belediyesi")
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("Giriş Yap")
            kullanici_adi = st.text_input("Kullanıcı Adı")
            sifre = st.text_input("Şifre", type="password")
            giris_btn = st.form_submit_button("Giriş Yap", use_container_width=True)

            if giris_btn:
                if not kullanici_adi or not sifre:
                    st.error("Kullanıcı adı ve şifre giriniz.")
                else:
                    try:
                        res = requests.post(
                            f"{API_URL}/login",
                            json={"kullanici_adi": kullanici_adi, "sifre": sifre},
                            timeout=5
                        )
                        if res.status_code == 200:
                            veri = res.json()
                            st.session_state.token = veri["token"]
                            st.session_state.kullanici = veri
                            st.rerun()
                        else:
                            st.error("Kullanıcı adı veya şifre hatalı.")
                    except Exception:
                        st.error("Sunucuya bağlanılamadı.")

# ── ARAÇ SEÇİM SAYFASI ──────────────────────────────────
def arac_secim_sayfasi():
    k = st.session_state.kullanici
    st.title("🚌 Araç Seçimi")
    st.caption(f"Hoşgeldiniz, {k.get('ad_soyad') or k.get('kullanici_adi')}")
    st.divider()

    try:
        res = requests.get(
            f"{API_URL}/vehicles",
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            timeout=5
        )
        if res.status_code == 200:
            araclar = [a for a in res.json() if a["aktif"]]
            if not araclar:
                st.warning("Sistemde kayıtlı aktif araç bulunmuyor.")
                return

            secenekler = {f"{a['plaka']} — {a['model'] or 'Bilinmiyor'}": a for a in araclar}
            secim = st.selectbox("Kullandığınız aracı seçin:", list(secenekler.keys()))

            if st.button("Devam Et", use_container_width=True):
                st.session_state.secilen_arac = secenekler[secim]
                st.rerun()
        else:
            st.error("Araç listesi alınamadı.")
    except Exception:
        st.error("API'ye bağlanılamadı.")

    st.divider()
    if st.button("Çıkış Yap"):
        st.session_state.token = None
        st.session_state.kullanici = None
        st.session_state.secilen_arac = None
        st.rerun()

# ── ANA SAYFA ────────────────────────────────────────────
def ana_sayfa():
    k = st.session_state.kullanici
    a = st.session_state.secilen_arac

    st.title("🛣️ Yol Hasar Tespit Sistemi")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Kullanıcı: {k.get('ad_soyad') or k.get('kullanici_adi')} | Araç: {a['plaka']}")
    with col2:
        if st.button("Araç Değiştir"):
            st.session_state.secilen_arac = None
            st.rerun()
        if st.button("Çıkış"):
            st.session_state.token = None
            st.session_state.kullanici = None
            st.session_state.secilen_arac = None
            st.rerun()

    st.divider()

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

# ── ROUTER ──────────────────────────────────────────────
if not st.session_state.token:
    login_sayfasi()
elif not st.session_state.secilen_arac:
    arac_secim_sayfasi()
else:
    ana_sayfa()