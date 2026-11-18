"""Charge le relevé Open-Meteo réel du 30/10/2026 dans une base de TEST (aperçu local du site).

Usage : MIGRATION_DB=data/preview.db python tests/load_fixture.py
puis   : MIGRATION_DB=data/preview.db PREVIEW_TODAY=2026-10-30 python pipeline/build_json.py
Jamais utilisé par le workflow de production.
"""
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from common import DATA_DIR, PARIS, SECTORS, db, iso  # noqa: E402

assert os.environ.get("MIGRATION_DB"), "définis MIGRATION_DB vers une base de test"
src = DATA_DIR / "migration.db"
if src.exists() and not Path(os.environ["MIGRATION_DB"]).exists():
    shutil.copy(src, os.environ["MIGRATION_DB"])  # reprend les vraies données palombe.com
fx = json.loads((Path(__file__).parent / "fixtures" / "openmeteo_2026-10-30.json").read_text())
con = db()
for s, loc, lv in zip(SECTORS.values(), fx["mf"], fx["vis"]):
    h, vis = loc["hourly"], dict(zip(lv["hourly"]["time"], lv["hourly"]["visibility"]))
    for i, t in enumerate(h["time"]):
        dt = datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=PARIS)
        con.execute("INSERT OR REPLACE INTO weather (lat, lon, datetime, wind_dir, wind_speed, gusts, cloud, precip, is_forecast, cloud_low, visibility, wind_dir_925, wind_speed_925, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (s["lat"], s["lon"], iso(dt), h["wind_direction_10m"][i], h["wind_speed_10m"][i], h["wind_gusts_10m"][i],
                     None, h["precipitation"][i], 0, h["cloud_cover_low"][i], vis.get(t), h["wind_direction_925hPa"][i],
                     h["wind_speed_925hPa"][i], fx["fetched"]))
    for d, sr in zip(loc["daily"]["time"], loc["daily"]["sunrise"]):
        sr_utc = datetime.strptime(sr, "%Y-%m-%dT%H:%M").replace(tzinfo=PARIS)
        con.execute("INSERT OR REPLACE INTO daylight VALUES (?,?,?,?,?)", (s["lat"], s["lon"], d, iso(sr_utc), None))
con.commit()
print("relevé de test chargé dans", os.environ["MIGRATION_DB"])
