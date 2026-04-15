from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt
import bcrypt
import asyncpg
import os
from livekit.api import AccessToken, VideoGrants

app = FastAPI(title="Yol Hasar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_DSN = os.getenv("DATABASE_URL", "postgresql://turna:turna@localhost:5432/yol_hasar")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "wss://turn.turna.im")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "APIJdbJEJpErro2")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "13Xn1wdGlqeY1ELkE1E3e6VG26qFBzFAWVgeOHGDUReA")
JWT_SECRET = os.getenv("JWT_SECRET", "yol-hasar-gizli-anahtar-2026-bursa-bursa")
JWT_EXP_HOURS = 8

security = HTTPBearer()

# ── DB ──────────────────────────────────────────────────
async def get_db():
    conn = await asyncpg.connect(DB_DSN)
    try:
        yield conn
    finally:
        await conn.close()

# ── JWT ─────────────────────────────────────────────────
def token_olustur(kullanici_id: int, kullanici_adi: str, rol: str) -> str:
    payload = {
        "sub": str(kullanici_id),
        "kullanici_adi": kullanici_adi,
        "rol": rol,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def token_dogrula(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token süresi dolmuş")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token")

# ── MODELLER ────────────────────────────────────────────
class LoginIstek(BaseModel):
    kullanici_adi: str
    sifre: str

class KonumIstek(BaseModel):
    lat: float
    lon: float
    plaka: str

# ── ENDPOINTLER ─────────────────────────────────────────
@app.post("/api/login")
async def login(istek: LoginIstek, db=Depends(get_db)):
    kullanici = await db.fetchrow(
        "SELECT id, kullanici_adi, sifre_hash, ad_soyad, rol FROM users WHERE kullanici_adi = $1 AND aktif = TRUE",
        istek.kullanici_adi
    )
    if not kullanici:
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı")

    if not bcrypt.checkpw(istek.sifre.encode(), kullanici["sifre_hash"].encode()):
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı")

    token = token_olustur(kullanici["id"], kullanici["kullanici_adi"], kullanici["rol"])
    return {
        "token": token,
        "kullanici_adi": kullanici["kullanici_adi"],
        "ad_soyad": kullanici["ad_soyad"],
        "rol": kullanici["rol"],
    }

@app.get("/api/me")
async def me(kullanici=Depends(token_dogrula), db=Depends(get_db)):
    row = await db.fetchrow("SELECT vehicle_id FROM users WHERE id = $1", int(kullanici['sub']))
    return {**kullanici, "vehicle_id": row['vehicle_id'] if row else None}

@app.get("/api/dashboard")
async def dashboard(kullanici=Depends(token_dogrula), db=Depends(get_db)):
    toplam = await db.fetchval("SELECT COUNT(*) FROM detections")
    kritik = await db.fetchval("SELECT COUNT(*) FROM detections WHERE durum = 'yeni' AND hasar_tipi = 3")
    tamamlandi = await db.fetchval("SELECT COUNT(*) FROM detections WHERE durum = 'tamamlandi'")
    aktif_arac = await db.fetchval("SELECT COUNT(DISTINCT vehicle_id) FROM cameras WHERE aktif = TRUE AND son_aktif > NOW() - INTERVAL '10 minutes'")
    return {
        "toplam_tespit": toplam or 0,
        "kritik_hasar": kritik or 0,
        "tamamlandi": tamamlandi or 0,
        "aktif_arac": aktif_arac or 0,
    }

@app.get("/api/detections")
async def detections(limit: int = 50, kullanici=Depends(token_dogrula), db=Depends(get_db)):
    rows = await db.fetch(
        """
        SELECT d.id, d.hasar_tipi, d.guven_skoru, d.lat, d.lon, d.durum, d.timestamp,
               v.plaka, c.isim as kamera
        FROM detections d
        LEFT JOIN vehicles v ON d.vehicle_id = v.id
        LEFT JOIN cameras c ON d.camera_id = c.id
        ORDER BY d.timestamp DESC
        LIMIT $1
        """,
        limit
    )
    hasar_adlari = ["Boyuna Çatlak", "Enine Çatlak", "Ağ Çatlağı", "Çukur"]
    return [
        {
            "id": r["id"],
            "hasar_tipi": hasar_adlari[r["hasar_tipi"]] if r["hasar_tipi"] < 4 else str(r["hasar_tipi"]),
            "guven_skoru": r["guven_skoru"],
            "lat": r["lat"],
            "lon": r["lon"],
            "durum": r["durum"],
            "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
            "plaka": r["plaka"],
            "kamera": r["kamera"],
        }
        for r in rows
    ]

@app.get("/api/vehicles")
async def vehicles(kullanici=Depends(token_dogrula), db=Depends(get_db)):
    rows = await db.fetch(
        "SELECT id, plaka, model, aktif, son_lat, son_lon, son_gorulme FROM vehicles ORDER BY plaka"
    )
    return [dict(r) for r in rows]

@app.patch("/api/detections/{detection_id}/durum")
async def durum_guncelle(detection_id: int, durum: str, kullanici=Depends(token_dogrula), db=Depends(get_db)):
    if durum not in ("yeni", "incelemede", "tamamlandi", "reddedildi"):
        raise HTTPException(status_code=400, detail="Geçersiz durum")
    await db.execute("UPDATE detections SET durum = $1 WHERE id = $2", durum, detection_id)
    return {"ok": True}

@app.post("/api/konum")
async def konum_guncelle(istek: KonumIstek, db=Depends(get_db)):
    arac = await db.fetchrow("SELECT id FROM vehicles WHERE plaka = $1", istek.plaka)
    if not arac:
        raise HTTPException(status_code=404, detail="Araç bulunamadı")
    await db.execute(
        "UPDATE vehicles SET son_lat=$1, son_lon=$2, son_gorulme=NOW() WHERE plaka=$3",
        istek.lat, istek.lon, istek.plaka
    )
    return {"ok": True}

@app.post("/api/konum/benim")
async def benim_konum(istek: KonumIstek, kullanici=Depends(token_dogrula), db=Depends(get_db)):
    row = await db.fetchrow(
        "SELECT v.plaka FROM users u JOIN vehicles v ON u.vehicle_id = v.id WHERE u.id = $1",
        int(kullanici['sub'])
    )
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcıya bağlı araç yok")
    await db.execute(
        "UPDATE vehicles SET son_lat=$1, son_lon=$2, son_gorulme=NOW() WHERE plaka=$3",
        istek.lat, istek.lon, row['plaka']
    )
    return {"ok": True, "plaka": row['plaka']}

@app.get("/api/vehicles/{vehicle_id}/livekit-token")
async def livekit_token(vehicle_id: int, kullanici=Depends(token_dogrula), db=Depends(get_db)):
    arac = await db.fetchrow("SELECT plaka FROM vehicles WHERE id = $1", vehicle_id)
    if not arac:
        raise HTTPException(status_code=404, detail="Araç bulunamadı")
    oda_adi = f"arac-{arac['plaka'].replace(' ', '-')}"
    token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(f"panel-{kullanici['kullanici_adi']}") \
        .with_name(kullanici['kullanici_adi']) \
        .with_grants(VideoGrants(room_join=True, room=oda_adi, can_publish=False, can_subscribe=True)) \
        .to_jwt()
    return {"token": token, "url": LIVEKIT_URL, "room": oda_adi}

@app.get("/api/health")
async def health():
    return {"status": "ok", "zaman": datetime.utcnow().isoformat()}