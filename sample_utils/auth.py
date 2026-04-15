import streamlit as st
import requests
import streamlit.components.v1 as components
from streamlit_cookies_manager import EncryptedCookieManager

API_URL = "http://127.0.0.1:8502/api"
COOKIE_PASSWORD = "bbb-yol-hasar-cookie-2026"

def _get_cookies():
    cookies = EncryptedCookieManager(prefix="bbb_", password=COOKIE_PASSWORD)
    if not cookies.ready():
        st.stop()
    return cookies

def session_kontrol():
    """Her sayfanın başında çağrılır. Login yoksa login ekranı gösterir, varsa devam eder."""
    import json
    cookies = _get_cookies()  # ready() false ise zaten st.stop() yapıyor

    # Cookie'den session_state'e yükle (her render'da taze oku)
    if not st.session_state.get("token"):
        raw = cookies.get("token")
        st.session_state.token = raw if raw else None
    if not st.session_state.get("kullanici"):
        raw = cookies.get("kullanici")
        try:
            st.session_state.kullanici = json.loads(raw) if raw else None
        except Exception:
            st.session_state.kullanici = None
    if not st.session_state.get("secilen_arac"):
        raw = cookies.get("secilen_arac")
        try:
            st.session_state.secilen_arac = json.loads(raw) if raw else None
        except Exception:
            st.session_state.secilen_arac = None

    # Token varsa sadece süresi dolmuşsa çıkış yaptır (her render'da API çağırma)
    if st.session_state.token and not st.session_state.get("_token_dogrulandi"):
        try:
            res = requests.get(
                f"{API_URL}/me",
                headers={"Authorization": f"Bearer {st.session_state.token}"},
                timeout=3
            )
            if res.status_code == 200:
                st.session_state._token_dogrulandi = True
            else:
                _cikis(cookies)
                return
        except Exception:
            st.session_state._token_dogrulandi = True  # API yoksa geçer

    if not st.session_state.token:
        _login_ekrani(cookies)
        st.stop()

    if not st.session_state.secilen_arac:
        _arac_secim_ekrani(cookies)
        st.stop()

def _login_ekrani(cookies):
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
                            import json
                            veri = res.json()
                            st.session_state.token = veri["token"]
                            st.session_state.kullanici = veri
                            cookies["token"] = veri["token"]
                            cookies["kullanici"] = json.dumps(veri)
                            cookies.save()
                            st.rerun()
                        else:
                            st.error("Kullanıcı adı veya şifre hatalı.")
                    except Exception:
                        st.error("Sunucuya bağlanılamadı.")

def _arac_secim_ekrani(cookies):
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
                    _cikis(cookies)
                return

            secenekler = {f"{a['plaka']} — {a['model'] or 'Bilinmiyor'}": a for a in araclar}
            secim = st.selectbox("Kullandığınız aracı seçin:", list(secenekler.keys()))

            if st.button("Devam Et", use_container_width=True):
                import json
                st.session_state.secilen_arac = secenekler[secim]
                cookies["secilen_arac"] = json.dumps(secenekler[secim])
                cookies.save()
                st.rerun()
        else:
            st.error("Araç listesi alınamadı.")
    except Exception:
        st.error("API'ye bağlanılamadı.")

    st.divider()
    if st.button("Çıkış Yap"):
        _cikis(cookies)

def _cikis(cookies=None):
    if cookies is None:
        cookies = _get_cookies()
    cookies["token"] = ""
    cookies["kullanici"] = ""
    cookies["secilen_arac"] = ""
    cookies.save()
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

def konum_takibi_baslat():
    """Araç seçimi sonrası çağrılır. Konum izni alır ve periyodik gönderir."""
    token = st.session_state.get("token", "")
    arac = st.session_state.get("secilen_arac", {})
    plaka = arac.get("plaka", "")
    if not token or not plaka:
        return
    components.html(f"""
    <script>
    (function() {{
        var TOKEN = "{token}";
        var PLAKA = "{plaka}";
        var API = "https://yol.turna.im/api/konum/benim";
        function gonder(pos) {{
            fetch(API, {{
                method: "POST",
                headers: {{"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN}},
                body: JSON.stringify({{lat: pos.coords.latitude, lon: pos.coords.longitude, plaka: PLAKA}})
            }});
        }}
        function hata(e) {{ console.warn("Konum hatası:", e.message); }}
        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(gonder, hata, {{enableHighAccuracy: true}});
            setInterval(function() {{
                navigator.geolocation.getCurrentPosition(gonder, hata, {{enableHighAccuracy: true}});
            }}, 10000);
        }}
    }})();
    </script>
    """, height=0)