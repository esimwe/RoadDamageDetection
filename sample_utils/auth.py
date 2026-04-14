import streamlit as st
import requests

API_URL = "http://127.0.0.1:8502/api"

def session_kontrol():
    """Her sayfanın başında çağrılır. Login yoksa login ekranı gösterir, varsa devam eder."""
    if "token" not in st.session_state:
        st.session_state.token = None
    if "kullanici" not in st.session_state:
        st.session_state.kullanici = None
    if "secilen_arac" not in st.session_state:
        st.session_state.secilen_arac = None

    if not st.session_state.token:
        _login_ekrani()
        st.stop()

    if not st.session_state.secilen_arac:
        _arac_secim_ekrani()
        st.stop()

def _login_ekrani():
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

def _arac_secim_ekrani():
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
                if st.button("Çıkış Yap"):
                    _cikis()
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
        _cikis()

def _cikis():
    st.session_state.token = None
    st.session_state.kullanici = None
    st.session_state.secilen_arac = None
    st.rerun()

def kullanici_bilgisi():
    """Header'da kullanıcı/araç bilgisi gösterir."""
    k = st.session_state.get("kullanici", {})
    a = st.session_state.get("secilen_arac", {})
    col1, col2 = st.columns([4, 1])
    with col1:
        st.caption(f"👤 {k.get('ad_soyad') or k.get('kullanici_adi', '')}  |  🚌 {a.get('plaka', '')}")
    with col2:
        if st.button("Çıkış"):
            _cikis()