"""Outils partagés par les collecteurs : HTTP poli, robots.txt, base SQLite, état des sources."""
import json
import math
import os
import sqlite3
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = ROOT / os.environ.get("MIGRATION_DB", "data/migration.db")  # surcharge réservée aux tests (relative à la racine)
PARIS = ZoneInfo("Europe/Paris")

CONTACT = os.environ.get("COLLECTOR_CONTACT", "").strip()
USER_AGENT = "LesPosees-collecteur/1.0 (prevision des passages, Landes" + (f"; contact: {CONTACT})" if CONTACT else ")")

PALOMBE_COM_ENABLED = os.environ.get("PALOMBE_COM_ENABLED", "true").lower() == "true"
TREKTELLEN_ENABLED = os.environ.get("TREKTELLEN_ENABLED", "true").lower() == "true"

# Secteurs (point de référence à la commune, jamais un poste)
SECTORS = {
    "labenne": {"name": "Labenne", "lat": 43.596, "lon": -1.458},
    "capbreton": {"name": "Capbreton", "lat": 43.643, "lon": -1.440},
    "hossegor": {"name": "Hossegor", "lat": 43.665, "lon": -1.440},
    "seignosse": {"name": "Seignosse", "lat": 43.700, "lon": -1.437},
}
CENTER = (43.64, -1.45)  # Labenne–Seignosse


class FormatChanged(Exception):
    """La page d'une source ne ressemble plus à ce que le collecteur sait lire."""


class Blocked(Exception):
    """La source refuse l'accès (protection anti-robots, robots.txt) : on ne contourne pas."""


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def paris_now():
    return datetime.now(PARIS)


def haversine_km(lat1, lon1, lat2, lon2):
    r = math.radians
    a = math.sin(r(lat2 - lat1) / 2) ** 2 + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(r(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2):
    r = math.radians
    y = math.sin(r(lon2 - lon1)) * math.cos(r(lat2))
    x = math.cos(r(lat1)) * math.sin(r(lat2)) - math.sin(r(lat1)) * math.cos(r(lat2)) * math.cos(r(lon2 - lon1))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


_robots = {}
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"})


def allowed_by_robots(url):
    host = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = _session.get(host + "/robots.txt", timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        _robots[host] = rp
    return _robots[host].can_fetch(USER_AGENT, url)


def get(url, *, params=None, expect_json=False, timeout=30, retries=2, headers=None):
    """GET poli : respecte robots.txt, s'identifie, détecte les pages anti-robots sans les contourner."""
    full = requests.Request("GET", url, params=params).prepare().url
    if not allowed_by_robots(full):
        raise Blocked(f"robots.txt interdit {full}")
    last = None
    for attempt in range(retries + 1):
        try:
            r = _session.get(url, params=params, timeout=timeout, headers=headers)
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code in (403, 429, 503) and ("Just a moment" in r.text or "cf-chl" in r.text or "challenge" in r.text.lower()):
            raise Blocked(f"protection anti-robots ({r.status_code}) sur {full}")
        if r.status_code >= 500:
            last = RuntimeError(f"HTTP {r.status_code} sur {full}")
            time.sleep(2 * (attempt + 1))
            continue
        r.raise_for_status()
        if expect_json:
            return r.json()
        r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
        return r.text
    raise last


SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
  obs_key TEXT PRIMARY KEY,
  source TEXT NOT NULL, url TEXT NOT NULL, site_name TEXT,
  lat REAL, lon REAL, species TEXT, date TEXT, time TEXT,
  count INTEGER, flights INTEGER, direction TEXT, weather_note TEXT,
  size_class TEXT, dept TEXT, extra TEXT,
  fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS obs_src_date ON observations(source, date);
CREATE TABLE IF NOT EXISTS weather (
  lat REAL, lon REAL, datetime TEXT, wind_dir REAL, wind_speed REAL, gusts REAL,
  cloud REAL, precip REAL, is_forecast INTEGER,
  cloud_low REAL, visibility REAL, wind_dir_925 REAL, wind_speed_925 REAL,
  fetched_at TEXT,
  PRIMARY KEY (lat, lon, datetime)
);
CREATE TABLE IF NOT EXISTS daylight (lat REAL, lon REAL, date TEXT, sunrise TEXT, sunset TEXT, PRIMARY KEY (lat, lon, date));
CREATE TABLE IF NOT EXISTS source_status (
  source TEXT PRIMARY KEY, status TEXT, rows INTEGER, message TEXT,
  checked_at TEXT, last_ok_at TEXT, url TEXT
);
CREATE TABLE IF NOT EXISTS forecast_frozen (
  date TEXT, sector TEXT, category TEXT, payload TEXT, sha256 TEXT, frozen_at TEXT,
  PRIMARY KEY (date, sector, category)
);
CREATE TABLE IF NOT EXISTS fetch_log (source TEXT PRIMARY KEY, fetched_at TEXT);
"""


def db():
    DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def set_status(con, source, status, rows=0, message="", url=""):
    t = iso(now_utc())
    prev = con.execute("SELECT last_ok_at FROM source_status WHERE source=?", (source,)).fetchone()
    last_ok = t if status == "ok" else (prev["last_ok_at"] if prev else None)
    con.execute(
        "INSERT OR REPLACE INTO source_status VALUES (?,?,?,?,?,?,?)",
        (source, status, rows, message[:500], t, last_ok, url),
    )
    con.commit()


def due(con, source, minutes):
    """Vrai si la source n'a pas été interrogée depuis `minutes` (limite de débit)."""
    row = con.execute("SELECT fetched_at FROM fetch_log WHERE source=?", (source,)).fetchone()
    if row is None or os.environ.get("FORCE_FETCH") == "1":
        return True
    last = datetime.strptime(row["fetched_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (now_utc() - last).total_seconds() >= minutes * 60 - 30


def mark_fetched(con, source):
    con.execute("INSERT OR REPLACE INTO fetch_log VALUES (?,?)", (source, iso(now_utc())))
    con.commit()


def run_collector(name, url, fn, enabled=True, every_minutes=15):
    """Exécute un collecteur, enregistre son état, ne lève jamais (le pipeline continue)."""
    con = db()
    if not enabled:
        set_status(con, name, "coupée", 0, "Source désactivée par interrupteur", url)
        return
    if not due(con, name, every_minutes):
        return
    try:
        n = fn(con)
        mark_fetched(con, name)
        set_status(con, name, "ok" if n else "vide", n, "", url)
        print(f"[{name}] {n} lignes")
    except Blocked as e:
        mark_fetched(con, name)
        set_status(con, name, "bloquée", 0, str(e), url)
        print(f"[{name}] BLOQUÉE : {e}")
    except FormatChanged as e:
        set_status(con, name, "format", 0, str(e), url)
        print(f"[{name}] FORMAT CHANGÉ : {e}")
    except Exception as e:  # noqa: BLE001
        set_status(con, name, "erreur", 0, f"{type(e).__name__}: {e}", url)
        print(f"[{name}] ERREUR : {e}")
    finally:
        con.close()


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
