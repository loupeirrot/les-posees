"""Météo : modèle AROME 0,025° de Météo-France, données publiques (Licence Ouverte), sans clé.

Jeu de données : https://www.data.gouv.fr/datasets/65bd12d7bfd26e26804204cb (fichiers GRIB2 sur le stockage
public de Météo-France). Un nouveau run toutes les 3 h ; le collecteur ne traite que les runs nouveaux.
- SP1 (surface) : vent à 10 m (force, direction), rafales maxi de l'heure, pluie cumulée, nébulosité totale, humidité à 2 m
- SP2 : nébulosité basse
- IP1 (niveaux de pression) : vent à 925 hPa (~800 m). Le fichier fait ~500 Mo par tranche de 6 h : on lit
  seulement les en-têtes par requêtes partielles, puis les deux champs utiles par heure.
AROME ouvert ne fournit pas la visibilité : la brume est estimée par l'humidité à 2 m (voir indice.py).
"""
import math
import re
import struct
import tempfile
from datetime import date, datetime, timedelta, timezone

import eccodes

from common import PARIS, SECTORS, Blocked, get, get_bytes, iso, now_utc, run_collector

DATASET = "https://www.data.gouv.fr/api/1/datasets/65bd12d7bfd26e26804204cb/"
S3 = "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net/pnt/{run}/arome/0025/{pkg}/arome__0025__{pkg}__{block}__{run}.grib2"
POINTS = [(s["lat"], s["lon"]) for s in SECTORS.values()] + [(43.035, -1.022), (44.200, -1.230)]
BLOCKS = [(0, 6), (7, 12), (13, 18), (19, 24), (25, 30), (31, 36), (37, 42), (43, 48), (49, 51)]
SP1 = {"10si", "10wdir", "max_i10fg", "tp", "2r"}


def block_name(a, b):
    return f"{a:02d}H{b:02d}H"


def latest_run():
    js = get(DATASET, expect_json=True)
    runs = sorted({m.group(1) for r in js.get("resources", []) if (m := re.search(r"__SP1__\d+H\d+H__(\S+Z)\.grib2", r.get("title", "")))})
    if not runs:
        raise Blocked("aucun run AROME listé sur data.gouv.fr")
    return datetime.strptime(runs[-1], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def blocks_for(run, t0, t1):
    """Tranches du run couvrant les échéances de t0 à t1."""
    fh0, fh1 = max(0, int((t0 - run).total_seconds() // 3600)), int((t1 - run).total_seconds() // 3600)
    return [(a, b) for a, b in BLOCKS if b >= fh0 and a <= fh1]


def nearest(h, lat, lon):
    return eccodes.codes_grib_find_nearest(h, lat, lon)[0]["value"]


def read_surface(run, blocks):
    """{(point, heure valide): {champ: valeur}} à partir de SP1 et SP2 (fichiers téléchargés entiers)."""
    out, tp = {}, {}
    runs = run.strftime("%Y-%m-%dT%H:%M:%SZ")
    for a, b in blocks:
        for pkg in ("SP1", "SP2"):
            url = S3.format(run=runs, pkg=pkg, block=block_name(a, b))
            with tempfile.TemporaryFile() as f:
                f.write(get_bytes(url))
                f.seek(0)
                while (h := eccodes.codes_grib_new_from_file(f)) is not None:
                    try:
                        name = eccodes.codes_get(h, "shortName")
                        disc, cat, num = (eccodes.codes_get(h, k) for k in ("discipline", "parameterCategory", "parameterNumber"))
                        if name == "unknown" and (disc, cat, num) == (0, 6, 1):
                            name = "tcc"
                        if (pkg == "SP1" and name in SP1 | {"tcc"}) or (pkg == "SP2" and name == "lcc"):
                            step = eccodes.codes_get(h, "step")
                            t = run + timedelta(hours=step)
                            for p in POINTS:
                                v = nearest(h, *p)
                                if name == "tp":
                                    tp[(p, step)] = v
                                else:
                                    out.setdefault((p, t), {})[name] = v
                    finally:
                        eccodes.codes_release(h)
    # pluie de l'heure = cumul à h - cumul à h-1
    for (p, step), v in tp.items():
        prev = tp.get((p, step - 1), 0.0 if step <= 1 else None)
        if prev is not None:
            out.setdefault((p, run + timedelta(hours=step)), {})["precip"] = max(0.0, v - prev)
    return out


def header(buf):
    """(catégorie, numéro, échéance, type de niveau, valeur) depuis la section 4 d'un message GRIB2."""
    pos = 16
    while pos < len(buf) - 5:
        ln, num = struct.unpack(">IB", buf[pos:pos + 5])
        if num == 4:
            s = buf[pos:pos + ln]
            return s[9], s[10], struct.unpack(">I", s[18:22])[0], s[22], struct.unpack(">I", s[24:28])[0]
        pos += ln
    return None


def read_925(run, blocks, hours_wanted):
    """Vent à 925 hPa (u, v) aux heures voulues, par lectures partielles du paquet IP1."""
    out = {}
    runs = run.strftime("%Y-%m-%dT%H:%M:%SZ")
    for a, b in blocks:
        url = S3.format(run=runs, pkg="IP1", block=block_name(a, b))
        off, want = 0, {}
        while True:
            buf = get_bytes(url, start=off, length=1024)
            if buf[:4] != b"GRIB":
                break
            ln = struct.unpack(">Q", buf[8:16])[0]
            hd = header(buf)
            if hd and hd[0] == 2 and hd[1] in (2, 3) and hd[3] == 100 and hd[4] == 92500 and (run + timedelta(hours=hd[2])) in hours_wanted:
                want[(hd[1], hd[2])] = (off, ln)
            if hd and (hd[0], hd[1]) not in ((2, 2), (2, 3)):
                break  # u puis v sont rangés en tête du fichier : inutile d'aller plus loin
            off += ln
        for (par, step), (o, ln) in want.items():
            h = eccodes.codes_new_from_message(get_bytes(url, start=o, length=ln))
            try:
                for p in POINTS:
                    out.setdefault((p, run + timedelta(hours=step)), {})["u925" if par == 2 else "v925"] = nearest(h, *p)
            finally:
                eccodes.codes_release(h)
    return out


def sunrise_utc(d, lat, lon):
    """Lever du soleil (algorithme NOAA simplifié, à la minute près)."""
    n = (d - date(2000, 1, 1)).days + 0.0008 - lon / 360
    m = math.radians((357.5291 + 0.98560028 * n) % 360)
    c = 1.9148 * math.sin(m) + 0.02 * math.sin(2 * m) + 0.0003 * math.sin(3 * m)
    lam = math.radians((math.degrees(m) + c + 180 + 102.9372) % 360)
    jt = 2451545.0 + n + 0.0053 * math.sin(m) - 0.0069 * math.sin(2 * lam)
    dec = math.asin(math.sin(lam) * math.sin(math.radians(23.4397)))
    cos_w = (math.sin(math.radians(-0.833)) - math.sin(math.radians(lat)) * math.sin(dec)) / (math.cos(math.radians(lat)) * math.cos(dec))
    jrise = jt - math.degrees(math.acos(cos_w)) / 360
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jrise - 2451545.0)


def collect(con):
    run = latest_run()
    last = con.execute("SELECT message FROM source_status WHERE source='meteo'").fetchone()
    # fenêtre utile : de la veille 18 h à après-demain midi (heure de Paris)
    today = datetime.now(PARIS).date()
    t0 = datetime(today.year, today.month, today.day, 18, tzinfo=PARIS) - timedelta(days=1)
    t1 = datetime(today.year, today.month, today.day, 13, tzinfo=PARIS) + timedelta(days=1)
    runs = []
    if not last or f"run {iso(run)}" not in (last["message"] or ""):
        runs.append(run)
    # heures du matin d'aujourd'hui manquantes (premier lancement) : on reprend le run de 00 h UTC
    have = con.execute("SELECT COUNT(*) c FROM weather WHERE datetime BETWEEN ? AND ? AND rh2m IS NOT NULL",
                       (iso(datetime(today.year, today.month, today.day, 6, tzinfo=PARIS)), iso(datetime(today.year, today.month, today.day, 12, tzinfo=PARIS)))).fetchone()["c"]
    first = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(hours=3)
    if have == 0 and run > first:
        runs.insert(0, first)
    if not runs:
        return con.execute("SELECT rows FROM source_status WHERE source='meteo'").fetchone()["rows"] or 0, f"run {iso(run)}"
    fetched, n = iso(now_utc()), 0
    for r in runs:
        start = max(r, t0.astimezone(timezone.utc))
        blocks = blocks_for(r, start, t1.astimezone(timezone.utc))
        data = read_surface(r, blocks)
        mornings = {t for (_, t) in data if 6 <= t.astimezone(PARIS).hour <= 12}
        morning_blocks = [bk for bk in blocks if any(bk[0] <= (t - r).total_seconds() / 3600 <= bk[1] for t in mornings)]
        for k, v in read_925(r, morning_blocks, mornings).items():
            data.setdefault(k, {}).update(v)
        for ((lat, lon), t), v in data.items():
            if "10si" not in v:
                continue
            u, w = v.get("u925"), v.get("v925")
            d925 = (math.degrees(math.atan2(-u, -w)) + 360) % 360 if u is not None else None
            s925 = math.hypot(u, w) * 3.6 if u is not None else None
            con.execute(
                "INSERT OR REPLACE INTO weather (lat, lon, datetime, wind_dir, wind_speed, gusts, cloud, precip, is_forecast,"
                " cloud_low, visibility, wind_dir_925, wind_speed_925, fetched_at, rh2m) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (lat, lon, iso(t), v["10wdir"], v["10si"] * 3.6, v.get("max_i10fg", 0) * 3.6, v.get("tcc"), v.get("precip"),
                 int(t > now_utc()), v.get("lcc"), None, d925, s925, f"{fetched} (AROME {iso(r)})", v.get("2r")),
            )
            n += 1
    for lat, lon in POINTS:
        for i in range(-1, 3):
            d = today + timedelta(days=i)
            con.execute("INSERT OR REPLACE INTO daylight VALUES (?,?,?,?,?)", (lat, lon, d.isoformat(), iso(sunrise_utc(d, lat, lon)), None))
    con.commit()
    return n, f"run {iso(run)}"


if __name__ == "__main__":
    run_collector("meteo", DATASET, collect, every_minutes=55)
