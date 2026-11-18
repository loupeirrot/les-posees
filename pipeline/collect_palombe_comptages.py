"""Comptages journaliers des cols (Arnéguy, Banca, Sare, Urrugne), GIFS France, publiés sur palombe.com.

Chaque case contient deux nombres : le principal (aller) et un second dans <span class="little"> (retour).
Contrôlé le 18/11/2026 : la note du 27/10/2026 « RETOURS : 11 442 pal à Urrugne » correspond au petit nombre.
Les chiffres sont stockés tels quels, sans correction.

Usage : python collect_palombe_comptages.py [--backfill 2010]
"""
import sys
import time
from datetime import date, datetime, timedelta, timezone

from bs4 import BeautifulSoup

from common import PALOMBE_COM_ENABLED, FormatChanged, db, dumps, get, iso, now_utc, paris_now, run_collector

URL = "https://www.palombe.com/migration/comptages.php"
SOURCE = "palombe.com / GIFS France"
POSTES = ["Arnéguy", "Banca", "Sare", "Urrugne"]
# centre de la commune (pas l'emplacement exact du poste de comptage)
POSTES_XY = {"Arnéguy": (43.109, -1.282), "Banca": (43.126, -1.383), "Sare": (43.312, -1.580), "Urrugne": (43.363, -1.699)}
MOIS = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12}


def to_int(s):
    s = (s or "").replace("\xa0", "").replace(" ", "").strip()
    if s in ("", "-", "—"):
        return None  # case vide ou « - » sur la page : pas de comptage
    if not s.isdigit():
        raise FormatChanged(f"nombre illisible : {s!r}")
    return int(s)


def split_cell(td):
    """(nombre principal, nombre du span.little)."""
    little = td.find("span", class_="little")
    small = to_int(little.get_text()) if little else None
    if little:
        little.extract()
    return to_int(td.get_text()), small


def parse(html, year):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    table = next((t for t in tables if all(p in t.get_text() for p in POSTES)), None)
    if table is None:
        raise FormatChanged("tableau des postes introuvable")
    rows = table.find_all("tr")
    head = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]
    if [h for h in head if h in POSTES] != POSTES:
        raise FormatChanged(f"en-tête inattendu : {head}")
    sub = [c.get_text(strip=True) for c in rows[1].find_all(["td", "th"])]
    if sub[1:9] != ["Nb", "Vol"] * 4:
        raise FormatChanged(f"sous-en-tête inattendu : {sub}")
    month, out = None, []
    for tr in rows[2:]:
        cells = tr.find_all("td")
        if len(cells) == 1:
            name = cells[0].get_text(strip=True).split()[0].lower()
            month = MOIS.get(name)
            continue
        if len(cells) < 12 or month is None:
            continue
        day = to_int(cells[1].get_text())
        if day is None:
            continue
        d = date(year, month, day)
        if any(c.find("span", class_="little") is None for c in cells[2:10]):
            raise FormatChanged(f"case sans span.little le {d}")
        meteo_td = next((c for c in cells[10:] if any(k.startswith("meteo") for k in c.get("class", []))), None)
        meteo_code = next((k for k in (meteo_td.get("class", []) if meteo_td else []) if k.startswith("meteo")), None)
        note = cells[-1].get_text(" ", strip=True).replace("\xa0", " ").strip() or None
        cumul_aller, cumul_retour = split_cell(cells[10])
        for i, poste in enumerate(POSTES):
            nb_a, nb_r = split_cell(cells[2 + 2 * i])
            vol_a, vol_r = split_cell(cells[3 + 2 * i])
            for direction, nb, vol in (("aller", nb_a, vol_a), ("retour", nb_r, vol_r)):
                out.append({"date": d.isoformat(), "poste": poste, "direction": direction, "count": nb, "flights": vol,
                            "meteo_code": meteo_code, "note": note,
                            "cumul_jour": cumul_aller if direction == "aller" else cumul_retour})
    return out


def store(con, rows, year):
    url = f"{URL}?year={year}"
    fetched = iso(now_utc())
    for r in rows:
        lat, lon = POSTES_XY[r["poste"]]
        con.execute(
            "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"gifs:{r['date']}:{r['poste']}:{r['direction']}", SOURCE, url, r["poste"], lat, lon, "Pigeon ramier",
             r["date"], None, r["count"], r["flights"], r["direction"], r["meteo_code"], None, None,
             dumps({"note": r["note"], "cumul_jour_4_postes": r["cumul_jour"]}), fetched),
        )
    con.commit()
    return len(rows)


def collect_year(con, year):
    html = get(URL, params={"year": year})
    return store(con, parse(html, year), year)


def collect(con):
    now = paris_now()
    year = now.year if now.month >= 7 else now.year - 1
    return collect_year(con, year)


def due_today(con):
    """Une fois par jour, après la mise à jour du soir (18 h 30 – 19 h 30) : à partir de 20 h 30, heure de Paris."""
    row = con.execute("SELECT fetched_at FROM fetch_log WHERE source='palombe_comptages'").fetchone()
    if row is None:
        return True
    last = datetime.strptime(row["fetched_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    now = paris_now()
    threshold = now.replace(hour=20, minute=30, second=0, microsecond=0)
    if now < threshold:
        threshold -= timedelta(days=1)
    return last < threshold


if __name__ == "__main__":
    if "--backfill" in sys.argv:
        first = int(sys.argv[sys.argv.index("--backfill") + 1])
        con = db()
        for y in range(first, paris_now().year + 1):
            try:
                print(y, collect_year(con, y))
            except FormatChanged as e:
                print(y, "format :", e)
            time.sleep(3)
        con.close()
        sys.exit(0)
    con = db()
    go = due_today(con)
    con.close()
    if go:
        run_collector("palombe_comptages", URL, collect, enabled=PALOMBE_COM_ENABLED, every_minutes=0)
