"""Observations journalières des chasseurs sur palombe.com (vols par classe de taille, département, vent).

On garde le département, le type de poste, les vols par classe de taille, le vent et le code météo.
On NE garde PAS le pseudo, le lieu-dit, la photo ni le texte libre de l'observateur.

Usage : python collect_palombe_observations.py [--pages 20]
"""
import re
import sys
import time
from datetime import date

from bs4 import BeautifulSoup

from common import PALOMBE_COM_ENABLED, FormatChanged, db, dumps, get, iso, now_utc, paris_now, run_collector

URL = "https://www.palombe.com/migration/observations.php"
SOURCE = "palombe.com (observations)"
CLASSES = ["1-10", "11-50", "51-100", "101-300", "+300"]
MOIS = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12}


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for msg in soup.select("div.creponse"):
        g, comp, dp = msg.select_one("span.g"), msg.select_one("div.comp"), msg.select_one("span.dp")
        if not (g and comp and dp):
            continue  # message sans comptage (annonce, etc.)
        m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", g.get_text(strip=True).lower())
        if not m or m.group(2) not in MOIS:
            raise FormatChanged(f"date illisible : {g.get_text(strip=True)!r}")
        d = date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1)))
        counts = [s.get_text(strip=True) for s in comp.find_all("span")]
        if len(counts) != 5 or not all(c.isdigit() for c in counts):
            raise FormatChanged(f"comptage illisible : {counts}")
        obs_id = (comp.get("id") or "").replace("comp_", "")
        typ = msg.select_one("span.typ")
        vv = msg.select_one("div.vv")
        meteo = next((c for c in msg.find_all("div") if any(k.startswith("meteo") for k in c.get("class", []))), None)
        out.append({
            "id": obs_id, "date": d.isoformat(), "dept": dp.get_text(strip=True),
            "post_type": typ.get("title") if typ else None,
            "flights_by_class": dict(zip(CLASSES, map(int, counts))),
            "wind_strength": vv.get("title") if vv else None, "wind_from": vv.get_text(strip=True) if vv else None,
            "meteo_code": next((k for k in meteo.get("class", []) if k.startswith("meteo")), None) if meteo else None,
        })
    return out


def store(con, rows, url):
    fetched = iso(now_utc())
    for r in rows:
        flights = sum(r["flights_by_class"].values())
        con.execute(
            "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"obs:{r['id']}", SOURCE, url, None, None, None, "Pigeon ramier", r["date"], None, None, flights,
             None, r["meteo_code"], None, r["dept"],
             dumps({"vols_par_classe": r["flights_by_class"], "type_poste": r["post_type"],
                    "vent_force": r["wind_strength"], "vent_secteur": r["wind_from"]}), fetched),
        )
    con.commit()
    return len(rows)


def collect_pages(con, pages):
    year = paris_now().year
    n = 0
    for page in range(1, pages + 1):
        params = {"year": year} if page == 1 else {"year": year, "PAGE": page}
        rows = parse(get(URL, params=params))
        if not rows:
            break
        n += store(con, rows, f"{URL}?year={year}" + (f"&PAGE={page}" if page > 1 else ""))
        if page < pages:
            time.sleep(3)
    return n


def collect(con):
    return collect_pages(con, 2)


if __name__ == "__main__":
    if "--pages" in sys.argv:
        con = db()
        print(collect_pages(con, int(sys.argv[sys.argv.index("--pages") + 1])))
        con.close()
        sys.exit(0)
    run_collector("palombe_observations", URL, collect, enabled=PALOMBE_COM_ENABLED, every_minutes=60)
