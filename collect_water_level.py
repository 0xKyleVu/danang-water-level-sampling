"""Lay snapshot real-time cua toan bo tram do ngap/muc nuoc tu muangap-api
(Da Nang), moi lan chay ghi 1 dong/tram vao water_level_samples.csv.

Ly do can script nay: endpoint lich su chinh thuc (/water_station/detail_report)
bi loi backend (treo vo han / 502) da xac nhan qua nhieu lan test - xem ghi chu
trong README. Day la cach duy nhat de co duoc chuoi thoi gian muc ngap that,
bang cach tu poll snapshot hien tai theo dinh ky.

Khong can API key - /v2/client/water_station/list_all la endpoint cong khai.
"""

import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API_URL = "https://muangap-api.danang.gov.vn/v2/client/water_station/list_all"
OUT_CSV = Path(__file__).resolve().parent / "water_level_samples.csv"

VN_TZ = timezone(timedelta(hours=7))

# Chi thu thap trong khung thoi gian nay (theo yeu cau: 1 tuan).
# Sau moc nay script se thoat som, khong ghi them, de tranh quen tat workflow.
COLLECTION_START = datetime(2026, 8, 25, tzinfo=timezone.utc)
COLLECTION_END = COLLECTION_START + timedelta(days=7)

STATION_TYPES = {
    "6699df2e5e72d8de60f4a15b": "Thap bao ngap",
    "6699df2e5e72d8de60f4a15e": "Tram do muc nuoc",
    "6699df2e5e72d8de60f4a160": "Thap bao lu",
    "676e251a3c3cce8b40faf69e": "Tram muc nuoc ho",
}

# Bounding box vung loi noi thanh Da Nang cu (giong quy uoc dung xuyen suot du an)
CORE_BBOX = {"lat_min": 15.95, "lat_max": 16.15, "lng_min": 108.10, "lng_max": 108.30}

CSV_COLUMNS = [
    "sampled_at_vn", "sampled_at_utc", "weekday", "hour_vn",
    "station_id", "code", "name", "station_type",
    "area", "district", "lat", "lng", "depth_m", "is_core_urban",
]


def is_core_urban(lat: float, lng: float) -> bool:
    b = CORE_BBOX
    return b["lat_min"] <= lat <= b["lat_max"] and b["lng_min"] <= lng <= b["lng_max"]


def fetch_stations(timeout: int = 20) -> list[dict]:
    resp = requests.get(API_URL, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def main():
    now_utc = datetime.now(timezone.utc)
    if now_utc > COLLECTION_END:
        print(f"Da qua moc ket thuc thu thap ({COLLECTION_END.isoformat()}), bo qua lan chay nay.")
        print("Neu van muon tiep tuc, sua COLLECTION_END trong collect_water_level.py.")
        return

    now_vn = now_utc.astimezone(VN_TZ)
    stations = fetch_stations()
    print(f"Lay mau luc {now_vn:%Y-%m-%d %H:%M} (gio VN) - {len(stations)} tram")

    rows = []
    for s in stations:
        lat, lng = s.get("latitude"), s.get("longitude")
        rows.append({
            "sampled_at_vn": now_vn.strftime("%Y-%m-%d %H:%M:%S"),
            "sampled_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "weekday": now_vn.strftime("%a"),
            "hour_vn": now_vn.hour,
            "station_id": s.get("id"),
            "code": s.get("code"),
            "name": s.get("name"),
            "station_type": STATION_TYPES.get(s.get("waterStationTypeId"), "?"),
            "area": s.get("area"),
            "district": s.get("district"),
            "lat": lat,
            "lng": lng,
            "depth_m": s.get("depth"),
            "is_core_urban": is_core_urban(lat, lng) if lat is not None and lng is not None else False,
        })

    is_new = not OUT_CSV.exists()
    with OUT_CSV.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)

    nonzero = [r for r in rows if r["depth_m"] not in (0, None) and r["station_type"] == "Thap bao ngap"]
    print(f"Da ghi {len(rows)} dong vao {OUT_CSV.name}")
    if nonzero:
        print(f"Thap bao ngap co depth != 0: {len(nonzero)}")
        for r in sorted(nonzero, key=lambda r: -abs(r["depth_m"]))[:5]:
            print(f"  {r['name']:35} {r['depth_m']:>6}m  ({r['district']})")


if __name__ == "__main__":
    main()
