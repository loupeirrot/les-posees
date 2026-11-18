"""Assemble public/latest.json (lu par le site) et archives.json, et fige la prévision du jour à 6 h 30.

Les chiffres des sources sont recopiés tels quels ; les calculs du site sont dans des champs « derive_* ».
"""
import hashlib
import json
import os
import shutil
from datetime import date, datetime, timedelta, timezone

from common import CENTER, PARIS, ROOT, SECTORS, bearing_deg, db, dumps, haversine_km, iso, now_utc, paris_now
from indice import DIRS_SHORT, Hourly, evaluate, sector8

SITE_DATA = ROOT / "site" / "src" / "data"
SITE_PUBLIC = ROOT / "site" / "public" / "data"
FLASH_RADIUS_KM = 150
UPSTREAM_LAT = 43.72  # au nord des secteurs
SOURCES = {
    "palombe_flash": ("Flash migration", "palombe.com", "https://www.palombe.com/flash/flash.php"),
    "palombe_comptages": ("Comptages des cols", "palombe.com / GIFS France", "https://www.palombe.com/migration/comptages.php"),
    "palombe_observations": ("Observations des chasseurs", "palombe.com", "https://www.palombe.com/migration/observations.php"),
    "trektellen": ("Comptages Organbidexka", "Trektellen", "https://www.trektellen.org/site/info/2133"),
    "meteo": ("Météo, modèle AROME", "Météo-France (données publiques)", "https://www.data.gouv.fr/datasets/65bd12d7bfd26e26804204cb"),
}
SEASON_ALERT = {  # périodes où une source vide est anormale (mois, jour)
    "palombe_flash": ((10, 1), (11, 20)), "palombe_comptages": ((10, 15), (11, 15)),
    "palombe_observations": ((10, 1), (11, 20)), "meteo": ((1, 1), (12, 31)), "trektellen": ((9, 15), (11, 15)),
}


def weather_for(con, lat, lon):
    rows = [dict(r) for r in con.execute("SELECT * FROM weather WHERE lat=? AND lon=?", (lat, lon))]
    sunrise = {}
    for r in con.execute("SELECT date, sunrise FROM daylight WHERE lat=? AND lon=?", (lat, lon)):
        t = datetime.strptime(r["sunrise"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(PARIS)
        sunrise[t.date().isoformat()] = t
    return Hourly(rows, sunrise) if rows else None


def forecasts(con, days):
    out = {}
    for key, s in SECTORS.items():
        h = weather_for(con, s["lat"], s["lon"])
        out[key] = {cat: {d.isoformat(): (evaluate(h, cat, d) if h else None) for d in days} for cat in ("palombe", "grives")}
    return out


def flash_block(con, now):
    since = iso(now - timedelta(hours=24))
    pts = []
    for r in con.execute("SELECT * FROM observations WHERE source LIKE 'palombe.com (Flash%' AND time >= ? ORDER BY time DESC", (since,)):
        dist = haversine_km(CENTER[0], CENTER[1], r["lat"], r["lon"])
        if dist <= FLASH_RADIUS_KM:
            b = bearing_deg(CENTER[0], CENTER[1], r["lat"], r["lon"])
            pts.append({"time": r["time"], "lat": r["lat"], "lon": r["lon"], "size_class": r["size_class"],
                        "direction": r["direction"], "derive_distance_km": round(dist), "derive_cap_depuis_secteurs": DIRS_SHORT[sector8(b)],
                        "url": r["url"]})
    upstream = next((p for p in pts if p["lat"] > UPSTREAM_LAT), None)
    return {"window_hours": 24, "radius_km": FLASH_RADIUS_KM, "center": {"lat": CENTER[0], "lon": CENTER[1]},
            "precision": "position arrondie à 0,1° (environ 10 km)", "points": pts, "derive_dernier_signal_amont": upstream}


def comptages_block(con, today):
    src = "palombe.com / GIFS France"
    last = con.execute("SELECT MAX(date) d FROM observations WHERE source=? AND date<=? AND count IS NOT NULL", (src, today.isoformat())).fetchone()["d"]
    if not last:
        return None
    jd = datetime.strptime(last, "%Y-%m-%d").date()
    season = jd.year

    def day(d):
        rows = con.execute("SELECT * FROM observations WHERE source=? AND date=?", (src, d.isoformat())).fetchall()
        if not rows:
            return None
        postes = {}
        for r in rows:
            p = postes.setdefault(r["site_name"], {"poste": r["site_name"]})
            p[r["direction"]] = {"oiseaux": r["count"], "vols": r["flights"]}
        extra = json.loads(rows[0]["extra"] or "{}")
        return {"date": d.isoformat(), "url": rows[0]["url"], "meteo_code": rows[0]["weather_note"], "note": extra.get("note"),
                "postes": [postes[k] for k in ("Arnéguy", "Banca", "Sare", "Urrugne") if k in postes]}

    def cumul(year, month_day):
        r = con.execute("SELECT SUM(count) s FROM observations WHERE source=? AND direction='aller' AND date BETWEEN ? AND ?",
                        (src, f"{year}-07-01", f"{year}-{month_day}")).fetchone()
        return r["s"]

    md = jd.strftime("%m-%d")
    previous = []
    for y in range(season - 15, season):
        c = cumul(y, md)
        j = con.execute("SELECT SUM(count) s FROM observations WHERE source=? AND direction='aller' AND date=?", (src, f"{y}-{md}")).fetchone()["s"]
        if c is not None:
            previous.append({"saison": y, "cumul_aller_a_date": c, "jour_aller": j})
    cur = cumul(season, md)
    avg = round(sum(p["cumul_aller_a_date"] for p in previous) / len(previous)) if previous else None
    jvals = [p["jour_aller"] for p in previous if p["jour_aller"] is not None]
    return {
        "source": src, "role": "aval", "season": season,
        "J": day(jd), "J-1": day(jd - timedelta(days=1)),
        "cumul_saison_aller_4_postes": cur,
        "derive_comparaison": {"meme_date": md, "saisons": [p["saison"] for p in previous],
                               "moyenne_cumul_aller_a_date": avg, "moyenne_jour_aller": round(sum(jvals) / len(jvals)) if jvals else None,
                               "ecart_cumul_pct": round(100 * (cur - avg) / avg) if cur is not None and avg else None},
    }


def observations_block(con, today):
    src = "palombe.com (observations)"
    out = {}
    for d in (today, today - timedelta(days=1)):
        depts = {}
        for r in con.execute("SELECT dept, flights FROM observations WHERE source=? AND date=?", (src, d.isoformat())):
            x = depts.setdefault(r["dept"], {"dept": r["dept"], "observateurs": 0, "vols": 0})
            x["observateurs"] += 1
            x["vols"] += r["flights"] or 0
        out[d.isoformat()] = sorted(depts.values(), key=lambda x: -x["vols"])
    return {"source": src, "url": "https://www.palombe.com/migration/observations.php", "par_jour": out}


def meteo_block(con, today):
    out = {}
    for key, s in SECTORS.items():
        days = []
        for i in range(4):
            d = today + timedelta(days=i)
            a = datetime(d.year, d.month, d.day, tzinfo=PARIS).astimezone(timezone.utc)
            rows = con.execute("SELECT * FROM weather WHERE lat=? AND lon=? AND datetime>=? AND datetime<?",
                               (s["lat"], s["lon"], iso(a), iso(a + timedelta(days=1)))).fetchall()
            if not rows:
                continue
            vals = lambda k: [r[k] for r in rows if r[k] is not None]  # noqa: E731
            clouds = vals("cloud")
            days.append({"date": d.isoformat(), "vent_max": max(vals("wind_speed"), default=None), "rafales_max": max(vals("gusts"), default=None),
                         "pluie_mm": round(sum(vals("precip")), 1), "nuages_moy": round(sum(clouds) / len(clouds)) if clouds else None})
        out[key] = days
    return out


def sources_block(con, today):
    rows = {r["source"]: dict(r) for r in con.execute("SELECT * FROM source_status")}
    out = []
    for key, (label, owner, url) in SOURCES.items():
        r = rows.get(key, {})
        (m1, d1), (m2, d2) = SEASON_ALERT[key]
        in_season = (m1, d1) <= (today.month, today.day) <= (m2, d2)
        out.append({"id": key, "label": label, "owner": owner, "url": url, "status": r.get("status", "jamais"),
                    "rows": r.get("rows"), "message": r.get("message"), "checked_at": r.get("checked_at"),
                    "last_ok_at": r.get("last_ok_at"), "in_season": in_season})
    return out


def freeze(con, fc, today, now_paris):
    # uniquement entre 6 h 30 et 7 h 30 : une prévision figée plus tard ne serait plus une prévision
    if not (6, 30) <= (now_paris.hour, now_paris.minute) < (7, 30):
        return
    for sector, cats in fc.items():
        for cat, days in cats.items():
            payload = days.get(today.isoformat())
            if payload is None:
                continue
            body = dumps(payload)
            con.execute("INSERT OR IGNORE INTO forecast_frozen VALUES (?,?,?,?,?,?)",
                        (today.isoformat(), sector, cat, body, hashlib.sha256(body.encode()).hexdigest(), iso(now_utc())))
    con.commit()


def archives(con):
    out = {}
    for r in con.execute("SELECT * FROM forecast_frozen ORDER BY date DESC"):
        p = json.loads(r["payload"])
        day = out.setdefault(r["date"], {"date": r["date"], "frozen_at": r["frozen_at"], "sectors": {}})
        day["sectors"].setdefault(r["sector"], {})[r["category"]] = {"level": p["level"], "word": p["word"], "window": p["window"]["text"],
                                                                    "wind": f"{p['wind']['dir_short']} {p['wind']['speed']} km/h", "sha256": r["sha256"]}
    for d, day in out.items():
        # ce qui a été vu ce jour-là (repères publics, pas une évaluation)
        n = con.execute("SELECT COUNT(*) c FROM observations WHERE source LIKE 'palombe.com (Flash%' AND date=? AND lat BETWEEN 43.2 AND 44.3 AND lon BETWEEN -1.9 AND -0.6", (d,)).fetchone()["c"]
        o = con.execute("SELECT COUNT(*) c, SUM(flights) v FROM observations WHERE source='palombe.com (observations)' AND date=? AND dept='40'", (d,)).fetchone()
        g = con.execute("SELECT SUM(count) s FROM observations WHERE source='palombe.com / GIFS France' AND date=? AND direction='aller'", (d,)).fetchone()["s"]
        day["vu"] = {"flash_sud_landes": n, "observations_landes": o["c"], "vols_landes": o["v"], "cols_aller": g}
    return sorted(out.values(), key=lambda x: x["date"], reverse=True)


def main():
    con = db()
    now, now_paris = now_utc(), paris_now()
    # PREVIEW_TODAY : aperçu local sur un relevé de test, jamais en production
    today = date.fromisoformat(os.environ["PREVIEW_TODAY"]) if os.environ.get("PREVIEW_TODAY") else now_paris.date()
    days = [today, today + timedelta(days=1)]
    fc = forecasts(con, days)
    if not os.environ.get("PREVIEW_TODAY"):
        freeze(con, fc, today, now_paris)
    srcs = sources_block(con, today)
    weather_ok = any(fc[s]["palombe"][today.isoformat()] for s in fc)
    latest = {
        "generated_at": iso(now), "timezone": "Europe/Paris", "today": today.isoformat(),
        "mode": "complet" if weather_ok else "degrade",
        "sectors": {k: {"name": v["name"], "lat": v["lat"], "lon": v["lon"]} for k, v in SECTORS.items()},
        "forecast": fc,
        "flash": flash_block(con, now),
        "comptages": comptages_block(con, today),
        "observations": observations_block(con, today),
        "meteo": meteo_block(con, today),
        "sources": srcs,
    }
    arch = archives(con)
    con.close()
    for d in (SITE_DATA, SITE_PUBLIC):
        d.mkdir(parents=True, exist_ok=True)
    (ROOT / "public").mkdir(exist_ok=True)
    text = json.dumps(latest, ensure_ascii=False, indent=1)
    (ROOT / "public" / "latest.json").write_text(text, encoding="utf-8")
    (SITE_DATA / "latest.json").write_text(text, encoding="utf-8")
    shutil.copy(ROOT / "public" / "latest.json", SITE_PUBLIC / "latest.json")
    (SITE_DATA / "archives.json").write_text(json.dumps(arch, ensure_ascii=False, indent=1), encoding="utf-8")
    print("latest.json :", latest["mode"], "·", len(latest["flash"]["points"]), "flash ·", len(arch), "jours archivés")


if __name__ == "__main__":
    main()
