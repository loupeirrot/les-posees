"""Flash migration de palombe.com : signalements des observateurs (carte de France, accès public).

Endpoint utilisé par la page elle-même : /ajax/front/Migration?action=flashDay&date=AAAA-MM-JJ&where=all
Chaque clé = minutes écoulées depuis 7 h (heure de Paris) ; chaque point = [x, y, classe de taille, type]
avec type 0 = vol d'aller, autre = vol de recul (affiché en orange sur palombe.com).
La carte zoomée Sud-Ouest de la saison en cours est réservée aux abonnés : elle n'est pas utilisée.

Positions : pixels de la carte de France convertis en coordonnées (calage sur 22 villes et 36 signalements
appariés, erreur typique 3 à 5 km), puis ARRONDIES à 0,1° (~10 km). Aucun pseudo n'est lu ni stocké.
"""
from datetime import datetime, timedelta

from common import PALOMBE_COM_ENABLED, PARIS, FormatChanged, dumps, get, iso, now_utc, paris_now, run_collector

URL = "https://www.palombe.com/ajax/front/Migration"
PAGE = "https://www.palombe.com/flash/flash.php"
SOURCE = "palombe.com (Flash migration)"
GAP_MIN = 5  # un même point revu à moins de 5 min d'écart = le même signalement

# carte de France (398 x 399 px) -> carte Sud-Ouest (710 x 647 px), affine
FR_TO_SO_X = (4.029998, -0.076858, -301.454898)
FR_TO_SO_Y = (-0.101197, 4.089975, -821.630316)
# carte Sud-Ouest -> (lon, lat), polynôme de degré 2 sur [x, y, xy, x², y², 1]
SO_LON = (0.0091498475, -0.00061101, -4.117e-07, -9.025e-07, 1.2222e-06, -1.826702844)
SO_LAT = (0.0005573265, -0.0062520907, 1.973e-07, -1.3366e-06, 5.205e-07, 46.4120952684)
SIZE_CLASSES = {1: "1-10", 2: "11-50", 3: "51-100", 4: "101-300", 5: "+300"}  # classes de palombe.com (correspondance probable)


def fr_px_to_lonlat(x, y):
    xs = FR_TO_SO_X[0] * x + FR_TO_SO_X[1] * y + FR_TO_SO_X[2]
    ys = FR_TO_SO_Y[0] * x + FR_TO_SO_Y[1] * y + FR_TO_SO_Y[2]
    basis = (xs, ys, xs * ys, xs * xs, ys * ys, 1)
    return sum(a * b for a, b in zip(SO_LON, basis)), sum(a * b for a, b in zip(SO_LAT, basis))


def group(data):
    """Regroupe les minutes successives d'un même point en un seul signalement."""
    last, flashes = {}, []
    for k in sorted(data, key=int):
        m = int(k)
        for p in data[k]:
            key = tuple(p[:4])
            if key in last and m - last[key][0] <= GAP_MIN:
                last[key] = (m, last[key][1])
                flashes[last[key][1]]["last_minute"] = m
                continue
            last[key] = (m, len(flashes))
            flashes.append({"x": p[0], "y": p[1], "size": p[2], "type": p[3], "minute": m, "last_minute": m})
    return flashes


def collect_day(con, day):
    js = get(URL, params={"action": "flashDay", "date": day.isoformat(), "where": "all"}, expect_json=True,
             headers={"X-Requested-With": "XMLHttpRequest", "Referer": PAGE})
    data = js.get("data") or {}
    if not isinstance(data, dict):
        raise FormatChanged("champ data inattendu")
    start = datetime(day.year, day.month, day.day, 7, 0, tzinfo=PARIS)
    fetched, n = iso(now_utc()), 0
    for f in group(data):
        lon, lat = fr_px_to_lonlat(f["x"], f["y"])
        t = start + timedelta(minutes=f["minute"])
        con.execute(
            "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"flash:{day}:{f['minute']}:{round(lat, 1)}:{round(lon, 1)}:{f['size']}:{f['type']}", SOURCE,
             f"{PAGE}?year={day.year}", None, round(lat, 1), round(lon, 1), "Pigeon ramier", day.isoformat(),
             iso(t), None, None, "aller" if f["type"] == 0 else "recul", None, SIZE_CLASSES.get(f["size"]), None,
             dumps({"duree_affichage_min": f["last_minute"] - f["minute"] + 1, "nbobs_jour": js.get("nbobs"),
                    "nbvols_jour": js.get("nbvols")}), fetched),
        )
        n += 1
    con.commit()
    return n


def collect(con):
    today = paris_now().date()
    n = collect_day(con, today)
    # la veille, une seule fois (fenêtre glissante de 24 h)
    y = today - timedelta(days=1)
    if not con.execute("SELECT 1 FROM observations WHERE source=? AND date=? LIMIT 1", (SOURCE, y.isoformat())).fetchone():
        n += collect_day(con, y)
    return n


if __name__ == "__main__":
    run_collector("palombe_flash", PAGE, collect, enabled=PALOMBE_COM_ENABLED, every_minutes=15)
