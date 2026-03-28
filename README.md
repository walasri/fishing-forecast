# 🎣 Fishing Forecast Mamuju

Forecast mancing otomatis untuk perairan Mamuju, Sulawesi Barat. Menganalisis data cuaca, laut, dan astronomi untuk memberikan rekomendasi waktu terbaik mancing **ikan** dan **cumi**.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![License](https://img.shields.io/badge/license-MIT-green)

## 📍 Lokasi

| Parameter | Value |
|-----------|-------|
| Nama | Mamuju nearshore |
| Koordinat | -2.68, 118.89 |
| Timezone | Asia/Makassar (WITA / UTC+8) |

## 📊 Sumber Data

Script mengambil data dari **3 sumber** dan menggabungkannya:

| Sumber | Data |
|--------|------|
| **[BMKG](https://www.bmkg.go.id)** (Peta Maritim) | Cuaca laut, peringatan gelombang, kecepatan angin (knot), kategori gelombang |
| **[BMKG](https://www.bmkg.go.id)** (Prakiraan Cuaca) | Cuaca darat, visibilitas, angin (km/jam) |
| **[Open-Meteo](https://open-meteo.com)** (Marine API) | Tinggi gelombang, periode gelombang, arus laut, suhu permukaan laut (SST), permukaan laut |

Data digabung dengan prioritas: BMKG Marine → BMKG Land → Open-Meteo Marine.

## 🐟 Scoring Ikan

Skor dimulai dari **50 poin**, kemudian ditambah/dikurangi berdasarkan faktor:

| Faktor | Kondisi | Poin |
|--------|---------|------|
| **Angin** | ≤ 10 km/j | +18 |
| | 10–18 km/j | +10 |
| | 18–25 km/j | ±0 |
| | 25–33 km/j | -15 |
| | > 33 km/j | -30 |
| **Cuaca** | Cerah / Berawan | +10 |
| | Mendung / Kabut | +4 |
| | Hujan ringan | -8 |
| | Hujan sedang/lebat/badai | -25 |
| **Visibilitas** | ≥ 8 km | +6 |
| | < 4 km | -10 |
| **Gelombang** | < 0.5 m | +12 |
| | 0.5–1.0 m | +8 |
| | 1.0–1.5 m | ±0 |
| | 1.5–2.0 m | -12 |
| | > 2.0 m | -28 |
| **Periode Gelombang** | 4–8 detik | +4 |
| | < 3 detik | -5 |
| | > 8 detik | -2 |
| **Arus** | 0.1–0.4 m/s | +16 |
| | 0.4–0.7 m/s | +8 |
| | < 0.1 m/s | -10 |
| | > 0.7 m/s | -8 |
| **Perubahan Pasang** | Sedang berubah | +10 |
| | Datar (flat) | -8 |
| **SST Delta** | ≤ 1.0°C | +6 |
| | > 1.5°C | -6 |

**Skor Akhir (0–100):**

| Skor | Label |
|------|-------|
| 80–100 | 🔥 Sangat Bagus |
| 60–79 | ✅ Bagus |
| 40–59 | 👍 Sedang |
| 20–39 | ⚠️ Lemah |
| 0–19 | ❌ Jelek |

**Jam potensial ikan:** 05:30–07:30 (skor ≥ 60) atau 06:00–07:00 (skor < 60)

## 🦑 Scoring Cumi

Skor dimulai dari **45 poin**, dengan faktor khusus cumi:

| Faktor | Kondisi | Poin |
|--------|---------|------|
| **Waktu** | 1–5 jam setelah sunset | +22 |
| | 5–10 jam setelah sunset | +12 |
| | Siang / tengah malam | -25 |
| **Cahaya Bulan** | Gelap (≤ 25%) | +24 |
| | 25–50% | +12 |
| | 50–75% | ±0 |
| | Terang (> 75%) | -18 |
| **Angin** | ≤ 8 km/j | +16 |
| | 8–15 km/j | +8 |
| | 15–24 km/j | -4 |
| | > 24 km/j | -20 |
| **Gelombang** | < 0.4 m | +18 |
| | 0.4–0.8 m | +10 |
| | 0.8–1.2 m | ±0 |
| | > 1.2 m | -20 |
| **Arus** | 0.08–0.25 m/s | +12 |
| | 0.25–0.45 m/s | +6 |
| | < 0.08 m/s | -6 |
| | > 0.45 m/s | -10 |
| **Cuaca** | Cerah / Berawan | +8 |
| | Hujan ringan | -8 |
| | Hujan sedang/lebat | -18 |
| **Visibilitas** | < 4 km | -8 |

**Jam potensial cumi:** 19:00–23:00 (skor ≥ 60) atau 19:00–21:00 (skor < 60)

## ⛔ Keselamatan

Script otomatis menandai **"Tidak disarankan"** jika:

- Angin > 33 km/jam
- Gelombang > 2.0 m
- Cuaca hujan lebat atau badai
- BMKG mengeluarkan peringatan maritim

## 🚀 Cara Pakai

### Prasyarat
- Python 3.10+
- Tidak perlu install library tambahan (hanya stdlib)

### Jalankan
```bash
python3 fishing_forecast.py
```

### Contoh Output
```
[05:00 WITA] Fetching data...

Update Harian Mamuju (2026-03-28 05:00 WITA)
Status: Layak

Ikan: 78/100 - bagus
Cumi: 85/100 - sangat bagus

Kondisi:
- Cuaca: cerah_berawan
- Angin: 8.50 km/jam
- Gelombang: 0.65 m
- Arus: 0.18 m/s
- Bulan: 15%

Jam potensial:
- Ikan: 05:30-07:30
- Cumi: 19:00-23:00

Alasan:
- angin sekitar 8.50 km/jam
- gelombang sekitar 0.65 m
- arus sekitar 0.18 m/s
- cahaya bulan 15%

Rekomendasi:
- Ikan: casting ringan atau dasar dekat struktur
- Cumi: eging malam di area lampu/dermaga

Sumber data: BMKG dan Open-Meteo
```

## ⏰ Jadwal Cron (via OpenClaw)

| Job | Waktu (WITA) | Deskripsi |
|-----|--------------|-----------|
| Fishing Forecast Pagi | 05:00 | Forecast harian — fokus ikan |
| Fishing Report Mamuju | 05:00 | Laporan lengkap ke Telegram |
| Harga Emas Pagi | 08:00 | Cek harga emas (bonus) |
| Fishing Forecast Sore | 16:00 | Forecast sore — fokus cumi |
| Monitor Cumi Mamuju | 17:00, 19:00, 21:00, 23:00 | Monitoring cumi real-time |

## 📁 Struktur

```
fishing-forecast/
├── fishing_forecast.py   # Script utama
├── README.md             # Dokumentasi ini
```

## 🔧 Konfigurasi

Edit bagian `CONFIG` di `fishing_forecast.py` untuk lokasi lain:

```python
CONFIG = {
    "location_name": "Mamuju nearshore",
    "latitude": -2.6800,
    "longitude": 118.8860,
    "bmkg_adm4": "76.02.01.1002",           # Kode ADM4 BMKG
    "bmkg_marine_url": "https://peta-maritim.bmkg.go.id/public_api/perairan/M.05.json",
    "timezone_offset_hours": 8,
    "request_timeout_sec": 20,
}
```

## 📝 License

MIT
