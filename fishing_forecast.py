#!/usr/bin/env python3
import json
import math
import re
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# =========================
# CONFIG
# =========================
CONFIG = {
    "location_name": "Mamuju nearshore",
    "latitude": -2.6800,
    "longitude": 118.8860,
    "bmkg_adm4": "76.02.01.1002",
    "bmkg_marine_url": "https://peta-maritim.bmkg.go.id/public_api/perairan/M.05.json",
    "timezone_offset_hours": 8,
    "request_timeout_sec": 20,
}

USER_AGENT = "OpenClawFishingBot/1.0"

# =========================
# HTTP HELPERS
# =========================
def http_get_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=CONFIG["request_timeout_sec"]) as resp:
        return json.loads(resp.read().decode("utf-8"))

def safe_http_get_json(url: str) -> dict | None:
    try:
        return http_get_json(url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None

# =========================
# TIME HELPERS
# =========================
def now_local() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=CONFIG["timezone_offset_hours"])

def parse_iso_maybe(value: str) -> datetime | None:
    if not value:
        return None
    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None

def nearest_index(times: list[str], target: datetime) -> int:
    best_idx = 0
    best_diff = None
    for i, ts in enumerate(times):
        dt = parse_iso_maybe(ts)
        if not dt:
            continue
        diff = abs((dt - target.replace(tzinfo=None)).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_idx = i
    return best_idx

# =========================
# MOON HELPERS
# =========================
def moon_illumination_percent(date_local: datetime) -> float:
    year = date_local.year
    month = date_local.month
    day = date_local.day + (date_local.hour / 24.0)
    if month < 3:
        year -= 1
        month += 12
    month += 1
    c = 365.25 * year
    e = 30.6 * month
    jd = c + e + day - 694039.09
    jd /= 29.5305882
    frac = jd - math.floor(jd)
    age = frac * 29.5305882
    illumination = 50 * (1 - math.cos(2 * math.pi * age / 29.5305882))
    return max(0.0, min(100.0, illumination))

def estimate_sunset_hour() -> int:
    return 18

def hours_after_sunset(dt_local: datetime) -> float:
    sunset = dt_local.replace(hour=estimate_sunset_hour(), minute=0, second=0, microsecond=0)
    return (dt_local - sunset).total_seconds() / 3600.0

# =========================
# BMKG LAND
# =========================
def fetch_bmkg_land(adm4: str) -> dict | None:
    url = f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={adm4}"
    return safe_http_get_json(url)

def extract_bmkg_land_snapshot(payload: dict, target_local: datetime) -> dict:
    def walk(obj):
        if isinstance(obj, dict):
            if "local_datetime" in obj and "weather_desc" in obj:
                yield obj
            for v in obj.values():
                yield from walk(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from walk(item)

    candidates = list(walk(payload))
    if not candidates:
        return {"weather_desc": "tidak_tersedia", "wind_kmh": None, "visibility_km": None}

    times = [c.get("local_datetime", "") for c in candidates]
    idx = nearest_index(times, target_local)
    chosen = candidates[idx]

    return {
        "weather_desc": normalize_weather_desc(chosen.get("weather_desc")),
        "wind_kmh": to_float(chosen.get("ws")),
        "visibility_km": parse_visibility_km(chosen.get("vs_text")),
    }

# =========================
# BMKG MARINE
# =========================
def fetch_bmkg_marine(url: str) -> dict | None:
    if not url:
        return None
    return safe_http_get_json(url)

def extract_bmkg_marine_snapshot(payload: dict, target_local: datetime) -> dict:
    records = []

    def walk(obj):
        if isinstance(obj, dict):
            if "valid_from" in obj and ("wave_cat" in obj or "weather" in obj):
                records.append(obj)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload)
    if not records:
        return {"weather_desc": None, "warning_desc": None, "wave_cat": None, "wave_height_m_from_cat": None, "wind_kmh": None}

    times = [r.get("valid_from", "") for r in records]
    idx = nearest_index(times, target_local)
    r = records[idx]

    wind_min_kn = to_float(r.get("wind_speed_min"))
    wind_max_kn = to_float(r.get("wind_speed_max"))
    wind_avg_kn = None
    if wind_min_kn is not None and wind_max_kn is not None:
        wind_avg_kn = (wind_min_kn + wind_max_kn) / 2.0

    return {
        "weather_desc": normalize_weather_desc(r.get("weather")),
        "warning_desc": r.get("warning_desc"),
        "wave_cat": r.get("wave_cat"),
        "wave_desc": r.get("wave_desc"),
        "wave_height_m_from_cat": map_wave_cat_to_height(r.get("wave_cat")),
        "wind_kmh": knots_to_kmh(wind_avg_kn) if wind_avg_kn is not None else None,
    }

# =========================
# OPEN-METEO MARINE
# =========================
def fetch_openmeteo_marine(lat: float, lon: float) -> dict | None:
    hourly = ",".join([
        "wave_height", "wave_direction", "wave_period",
        "ocean_current_velocity", "ocean_current_direction",
        "sea_surface_temperature", "sea_level_height_msl",
    ])
    url = (
        f"https://marine-api.open-meteo.com/v1/marine"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly={hourly}"
        f"&forecast_days=2"
        f"&timezone=Asia%2FMakassar"
    )
    return safe_http_get_json(url)

def extract_openmeteo_snapshot(payload: dict, target_local: datetime) -> dict:
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return {"wave_height_m": None, "wave_period_s": None, "current_velocity_ms": None, "sst_c": None, "sea_level_height_msl": None, "sea_level_delta": None}

    idx = nearest_index(times, target_local)

    wave_height_m = array_at(hourly.get("wave_height"), idx)
    wave_period_s = array_at(hourly.get("wave_period"), idx)

    current_velocity = array_at(hourly.get("ocean_current_velocity"), idx)
    current_velocity_ms = kmh_to_ms(current_velocity) if current_velocity is not None else None

    sst_c = array_at(hourly.get("sea_surface_temperature"), idx)
    sea_level = array_at(hourly.get("sea_level_height_msl"), idx)

    prev_idx = max(0, idx - 2)
    prev_sea_level = array_at(hourly.get("sea_level_height_msl"), prev_idx)
    sea_level_delta = None
    if sea_level is not None and prev_sea_level is not None:
        delta = sea_level - prev_sea_level
        if abs(delta) < 0.03:
            sea_level_delta = "flat"
        else:
            sea_level_delta = "moderate_change"

    return {
        "wave_height_m": wave_height_m,
        "wave_period_s": wave_period_s,
        "current_velocity_ms": current_velocity_ms,
        "sst_c": sst_c,
        "sea_level_height_msl": sea_level,
        "sea_level_delta": sea_level_delta,
    }

# =========================
# NORMALIZERS
# =========================
def to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def array_at(arr, idx):
    if not isinstance(arr, list) or idx >= len(arr):
        return None
    return to_float(arr[idx])

def knots_to_kmh(knots: float | None) -> float | None:
    return None if knots is None else knots * 1.852

def kmh_to_ms(kmh: float | None) -> float | None:
    return None if kmh is None else kmh / 3.6

def parse_visibility_km(value: str | None) -> float | None:
    if not value:
        return None
    m = re.search(r"(\d+(\.\d+)?)", str(value))
    return float(m.group(1)) if m else None

def normalize_weather_desc(value: str | None) -> str:
    if not value:
        return "tidak_tersedia"
    s = value.strip().lower()
    mapping = {
        "cerah": "cerah", "cerah berawan": "cerah_berawan", "berawan": "berawan",
        "berawan tebal": "mendung", "mendung": "mendung", "kabut": "kabut",
        "hujan ringan": "hujan_ringan", "hujan sedang": "hujan_sedang",
        "hujan lebat": "hujan_lebat", "hujan badai": "badai", "badai": "badai",
    }
    return mapping.get(s, s.replace(" ", "_"))

def map_wave_cat_to_height(cat: str | None) -> float | None:
    if not cat:
        return None
    s = cat.strip().lower()
    mapping = {
        "tenang": 0.3, "rendah": 0.8, "sedang": 1.3, "tinggi": 2.0,
        "sangat tinggi": 3.0, "ekstrem": 4.0, "sangat ekstrem": 5.0,
    }
    return mapping.get(s)

# =========================
# SCORING
# =========================
def score_fish(wind_kmh, weather_desc, visibility_km, wave_height_m, wave_period_s,
               current_velocity_ms, sea_level_delta, sst_delta_c=None):
    score = 50
    if wind_kmh is not None:
        if wind_kmh <= 10: score += 18
        elif wind_kmh <= 18: score += 10
        elif wind_kmh <= 25: score += 0
        elif wind_kmh <= 33: score -= 15
        else: score -= 30

    score += {"cerah": 10, "cerah_berawan": 10, "berawan": 10, "mendung": 4,
              "kabut": 4, "hujan_ringan": -8, "hujan_sedang": -25, "hujan_lebat": -25, "badai": -25}.get(weather_desc, 0)

    if visibility_km is not None:
        if visibility_km >= 8: score += 6
        elif visibility_km < 4: score -= 10

    if wave_height_m is not None:
        if wave_height_m < 0.5: score += 12
        elif wave_height_m < 1.0: score += 8
        elif wave_height_m < 1.5: score += 0
        elif wave_height_m < 2.0: score -= 12
        else: score -= 28

    if wave_period_s is not None:
        if 4 <= wave_period_s <= 8: score += 4
        elif wave_period_s < 3: score -= 5
        elif wave_period_s > 8: score -= 2

    if current_velocity_ms is not None:
        if 0.1 <= current_velocity_ms <= 0.4: score += 16
        elif 0.41 <= current_velocity_ms <= 0.7: score += 8
        elif current_velocity_ms < 0.1: score -= 10
        elif current_velocity_ms > 0.7: score -= 8

    if sea_level_delta == "moderate_change": score += 10
    elif sea_level_delta == "flat": score -= 8

    if sst_delta_c is not None:
        if sst_delta_c <= 1.0: score += 6
        elif sst_delta_c > 1.5: score -= 6

    return clamp(score, 0, 100)

def score_squid(hours_after_sunset_value, moon_illumination, wind_kmh, weather_desc,
                visibility_km, wave_height_m, current_velocity_ms):
    score = 45
    if 1 <= hours_after_sunset_value <= 5: score += 22
    elif 5 < hours_after_sunset_value <= 10: score += 12
    else: score -= 25

    if moon_illumination <= 25: score += 24
    elif moon_illumination <= 50: score += 12
    elif moon_illumination <= 75: score += 0
    else: score -= 18

    if wind_kmh is not None:
        if wind_kmh <= 8: score += 16
        elif wind_kmh <= 15: score += 8
        elif wind_kmh <= 24: score -= 4
        else: score -= 20

    if wave_height_m is not None:
        if wave_height_m < 0.4: score += 18
        elif wave_height_m <= 0.8: score += 10
        elif wave_height_m <= 1.2: score += 0
        else: score -= 20

    if current_velocity_ms is not None:
        if 0.08 <= current_velocity_ms <= 0.25: score += 12
        elif 0.26 <= current_velocity_ms <= 0.45: score += 6
        elif current_velocity_ms < 0.08: score -= 6
        elif current_velocity_ms > 0.45: score -= 10

    score += {"cerah": 8, "cerah_berawan": 8, "berawan": 8, "mendung": 0,
              "hujan_ringan": -8, "hujan_sedang": -18, "hujan_lebat": -18, "badai": -18}.get(weather_desc, 0)

    if visibility_km is not None and visibility_km < 4: score -= 8
    return clamp(score, 0, 100)

def clamp(x, lo, hi):
    return max(lo, min(hi, int(round(x))))

def label(score: int) -> str:
    if score >= 80: return "sangat bagus"
    if score >= 60: return "bagus"
    if score >= 40: return "sedang"
    if score >= 20: return "lemah"
    return "jelek"

def safety_status(wind_kmh, wave_height_m, weather_desc, bmkg_warning_desc):
    warning = (bmkg_warning_desc or "").strip()
    if wind_kmh is not None and wind_kmh > 33:
        return "Tidak disarankan", "angin terlalu kencang"
    if wave_height_m is not None and wave_height_m > 2.0:
        return "Tidak disarankan", "gelombang terlalu tinggi"
    if weather_desc in {"hujan_lebat", "badai"}:
        return "Tidak disarankan", "cuaca buruk"
    if warning and warning.upper() != "NIL":
        return "Tidak disarankan", f"peringatan maritim: {warning}"
    return None, None

# =========================
# BEST TIME WINDOWS
# =========================
def best_time_windows(target_local: datetime, fish_score: int, squid_score: int):
    fish = "05:30-07:30" if fish_score >= 60 else "06:00-07:00"
    squid = "19:00-23:00" if squid_score >= 60 else "19:00-21:00"
    return fish, squid

# =========================
# REPORT
# =========================
def build_report(target_local: datetime, merged: dict, fish_score: int, squid_score: int,
                 status_override: str | None, status_reason: str | None) -> str:
    fish_label = label(fish_score)
    squid_label = label(squid_score)
    fish_time, squid_time = best_time_windows(target_local, fish_score, squid_score)

    if status_override:
        status = status_override
    else:
        top = max(fish_score, squid_score)
        if top >= 60: status = "Layak"
        elif top >= 40: status = "Kurang layak"
        else: status = "Tidak disarankan"

    reasons = []
    if merged.get("wind_kmh") is not None:
        reasons.append(f"angin sekitar {merged['wind_kmh']:.1f} km/jam")
    if merged.get("wave_height_m") is not None:
        reasons.append(f"gelombang sekitar {merged['wave_height_m']:.2f} m")
    if merged.get("current_velocity_ms") is not None:
        reasons.append(f"arus sekitar {merged['current_velocity_ms']:.2f} m/s")
    if merged.get("moon_illumination") is not None:
        reasons.append(f"cahaya bulan {merged['moon_illumination']:.0f}%")
    if status_reason:
        reasons.insert(0, status_reason)

    recs = []
    if fish_score >= 60:
        recs.append("Ikan: casting ringan atau dasar dekat struktur")
    else:
        recs.append("Ikan: pilih sesi singkat dan hindari area terlalu terbuka")
    if squid_score >= 60:
        recs.append("Cumi: eging malam di area lampu/dermaga")
    else:
        recs.append("Cumi: tunggu malam lebih gelap atau kondisi lebih tenang")

    return (
        f"Update Harian Mamuju ({target_local.strftime('%Y-%m-%d %H:%M')} WITA)\n"
        f"Status: {status}\n\n"
        f"Ikan: {fish_score}/100 - {fish_label}\n"
        f"Cumi: {squid_score}/100 - {squid_label}\n\n"
        f"Kondisi:\n"
        f"- Cuaca: {merged.get('weather_desc', 'n/a')}\n"
        f"- Angin: {format_num(merged.get('wind_kmh'), 'km/jam')}\n"
        f"- Gelombang: {format_num(merged.get('wave_height_m'), 'm')}\n"
        f"- Arus: {format_num(merged.get('current_velocity_ms'), 'm/s')}\n"
        f"- Bulan: {merged.get('moon_illumination', 0):.0f}%\n\n"
        f"Jam potensial:\n"
        f"- Ikan: {fish_time}\n"
        f"- Cumi: {squid_time}\n\n"
        f"Alasan:\n"
        + "\n".join(f"- {r}" for r in reasons[:4]) + "\n\n"
        f"Rekomendasi:\n"
        + "\n".join(f"- {r}" for r in recs) + "\n\n"
        f"Sumber data: BMKG dan Open-Meteo\n"
    )

def format_num(v, unit):
    if v is None:
        return "n/a"
    return f"{v:.2f} {unit}"

# =========================
# MERGE
# =========================
def merge_sources(land: dict, marine_bmkg: dict, marine_om: dict, target_local: datetime) -> dict:
    weather_desc = marine_bmkg.get("weather_desc") or land.get("weather_desc") or "tidak_tersedia"
    wind_kmh = first_not_none(marine_bmkg.get("wind_kmh"), land.get("wind_kmh"))
    wave_height_m = first_not_none(marine_om.get("wave_height_m"), marine_bmkg.get("wave_height_m_from_cat"))
    return {
        "weather_desc": weather_desc,
        "wind_kmh": wind_kmh,
        "visibility_km": land.get("visibility_km"),
        "wave_height_m": wave_height_m,
        "wave_period_s": marine_om.get("wave_period_s"),
        "current_velocity_ms": marine_om.get("current_velocity_ms"),
        "sst_c": marine_om.get("sst_c"),
        "sea_level_delta": marine_om.get("sea_level_delta"),
        "bmkg_warning_desc": marine_bmkg.get("warning_desc"),
        "moon_illumination": moon_illumination_percent(target_local),
    }

def first_not_none(*values):
    for v in values:
        if v is not None:
            return v
    return None

# =========================
# MAIN
# =========================
def main():
    target_local = now_local()
    print(f"[{target_local.strftime('%H:%M')} WITA] Fetching data...\n")

    bmkg_land_payload = fetch_bmkg_land(CONFIG["bmkg_adm4"])
    bmkg_marine_payload = fetch_bmkg_marine(CONFIG["bmkg_marine_url"])
    openmeteo_payload = fetch_openmeteo_marine(CONFIG["latitude"], CONFIG["longitude"])

    land = extract_bmkg_land_snapshot(bmkg_land_payload or {}, target_local)
    marine_bmkg = extract_bmkg_marine_snapshot(bmkg_marine_payload or {}, target_local)
    marine_om = extract_openmeteo_snapshot(openmeteo_payload or {}, target_local)

    merged = merge_sources(land, marine_bmkg, marine_om, target_local)

    fish = score_fish(
        merged["wind_kmh"], merged["weather_desc"], merged["visibility_km"],
        merged["wave_height_m"], merged["wave_period_s"],
        merged["current_velocity_ms"], merged["sea_level_delta"],
    )

    squid = score_squid(
        hours_after_sunset(target_local), merged["moon_illumination"],
        merged["wind_kmh"], merged["weather_desc"],
        merged["visibility_km"], merged["wave_height_m"], merged["current_velocity_ms"],
    )

    status_override, status_reason = safety_status(
        merged["wind_kmh"], merged["wave_height_m"], merged["weather_desc"], merged["bmkg_warning_desc"],
    )

    report = build_report(target_local, merged, fish, squid, status_override, status_reason)
    print(report)

if __name__ == "__main__":
    main()
