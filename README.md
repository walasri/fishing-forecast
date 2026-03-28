# 🎣 Fishing Forecast Mamuju

Forecast mancing otomatis untuk Mamuju, Sulawesi Barat.

## Fitur
- 🐟 Forecast ikan (berdasarkan tide, moon, cuaca, angin, tekanan)
- 🦑 Forecast cumi (berdasarkan malam, moon, angin, gelombang, tide)
- 🌊 Data dari Open-Meteo API + BMKG + tide-forecast.com
- 📊 Scoring system: 9-12=SANGAT BAGUS🔥, 6-8=CUKUP👍, <6=BURUK⚠️

## Usage
```bash
python3 fishing_forecast.py
```

## Cron (via OpenClaw)
- Pagi jam 05:00 WITA — forecast harian
- Sore/Malam jam 17:00, 19:00, 21:00, 23:00 WITA — monitor cumi

Dibuat untuk Mamuju nearshore (-2.68, 118.89) 🌊

