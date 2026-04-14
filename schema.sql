-- Yol Hasar Tespit Sistemi - Veritabanı Şeması
-- yol_hasar database

-- Kullanıcılar
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    kullanici_adi VARCHAR(50) UNIQUE NOT NULL,
    sifre_hash VARCHAR(255) NOT NULL,
    ad_soyad VARCHAR(100),
    rol VARCHAR(20) NOT NULL DEFAULT 'teknisyen', -- admin, mudur, teknisyen
    aktif BOOLEAN DEFAULT TRUE,
    olusturma_tarihi TIMESTAMP DEFAULT NOW()
);

-- Araçlar
CREATE TABLE vehicles (
    id SERIAL PRIMARY KEY,
    plaka VARCHAR(20) UNIQUE NOT NULL,
    model VARCHAR(100),
    yil INTEGER,
    aktif BOOLEAN DEFAULT TRUE,
    son_lat DOUBLE PRECISION,
    son_lon DOUBLE PRECISION,
    son_gorulme TIMESTAMP,
    olusturma_tarihi TIMESTAMP DEFAULT NOW()
);

-- Şoförler
CREATE TABLE drivers (
    id SERIAL PRIMARY KEY,
    ad_soyad VARCHAR(100) NOT NULL,
    sicil_no VARCHAR(50) UNIQUE NOT NULL,
    telefon VARCHAR(20),
    aktif BOOLEAN DEFAULT TRUE,
    olusturma_tarihi TIMESTAMP DEFAULT NOW()
);

-- Vardiyalar (hangi şoför hangi araçta)
CREATE TABLE vehicle_shifts (
    id SERIAL PRIMARY KEY,
    vehicle_id INTEGER REFERENCES vehicles(id),
    driver_id INTEGER REFERENCES drivers(id),
    baslangic TIMESTAMP NOT NULL,
    bitis TIMESTAMP,
    olusturma_tarihi TIMESTAMP DEFAULT NOW()
);

-- Kameralar
CREATE TABLE cameras (
    id SERIAL PRIMARY KEY,
    vehicle_id INTEGER REFERENCES vehicles(id),
    isim VARCHAR(50) NOT NULL, -- 'Ön Kamera', 'Arka Kamera' vb.
    konum VARCHAR(20) DEFAULT 'on', -- on, arka, yan_sol, yan_sag
    aktif BOOLEAN DEFAULT TRUE,
    session_id VARCHAR(100), -- aktif streamlit session
    son_aktif TIMESTAMP,
    olusturma_tarihi TIMESTAMP DEFAULT NOW()
);

-- GPS Takibi
CREATE TABLE gps_tracks (
    id SERIAL PRIMARY KEY,
    vehicle_id INTEGER REFERENCES vehicles(id),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    hiz DOUBLE PRECISION,
    yon DOUBLE PRECISION
);
CREATE INDEX idx_gps_tracks_vehicle_time ON gps_tracks(vehicle_id, timestamp DESC);

-- Tespitler
CREATE TABLE detections (
    id SERIAL PRIMARY KEY,
    vehicle_id INTEGER REFERENCES vehicles(id),
    camera_id INTEGER REFERENCES cameras(id),
    shift_id INTEGER REFERENCES vehicle_shifts(id),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    hasar_tipi SMALLINT NOT NULL, -- 0=Boyuna Çatlak, 1=Enine Çatlak, 2=Ağ Çatlağı, 3=Çukur
    guven_skoru REAL NOT NULL,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    goruntu_yolu VARCHAR(255),
    durum VARCHAR(20) DEFAULT 'yeni', -- yeni, incelemede, tamamlandi, reddedildi
    olusturma_tarihi TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_detections_vehicle_time ON detections(vehicle_id, timestamp DESC);
CREATE INDEX idx_detections_durum ON detections(durum);
CREATE INDEX idx_detections_hasar_tipi ON detections(hasar_tipi);

-- Tespit Notları (teknisyen yorumları)
CREATE TABLE detection_notes (
    id SERIAL PRIMARY KEY,
    detection_id INTEGER REFERENCES detections(id),
    user_id INTEGER REFERENCES users(id),
    not TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Raporlar
CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    baslik VARCHAR(200),
    vehicle_id INTEGER REFERENCES vehicles(id),
    baslangic TIMESTAMP,
    bitis TIMESTAMP,
    toplam_tespit INTEGER DEFAULT 0,
    boyuna_catlak INTEGER DEFAULT 0,
    enine_catlak INTEGER DEFAULT 0,
    ag_catlagi INTEGER DEFAULT 0,
    cukur INTEGER DEFAULT 0,
    olusturan INTEGER REFERENCES users(id),
    olusturma_tarihi TIMESTAMP DEFAULT NOW()
);

-- Varsayılan kullanıcılar (şifreler: bursa2026)
-- bcrypt hash of 'bursa2026'
INSERT INTO users (kullanici_adi, sifre_hash, ad_soyad, rol) VALUES
    ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGX.9YcQjfOJMNTGpWBMg8tVGXG', 'Sistem Yöneticisi', 'admin'),
    ('mudur', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGX.9YcQjfOJMNTGpWBMg8tVGXG', 'Müdür', 'mudur'),
    ('teknisyen1', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGX.9YcQjfOJMNTGpWBMg8tVGXG', 'Teknisyen 1', 'teknisyen');