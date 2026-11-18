"""Météo Open-Meteo (modèles Météo-France) pour les secteurs, le col d'Organbidexka et un point amont.

Vent au sol et à 925 hPa (~800 m), rafales, nuages, pluie, visibilité ; de la veille à J+3.
"""
from datetime import datetime, timezone

from common import SECTORS, db, get, iso, now_utc, run_collector

POINTS = [(s["lat"], s["lon"]) for s in SECTORS.values()] + [
    (43.035, -1.022),  # col d'Organbidexka
    (44.200, -1.230),  # Mimizan, amont sur la côte
]
URL = "https://api.open-meteo.com/v1/forecast"
COMMON = {
    "latitude": ",".join(str(p[0]) for p in POINTS),
    "longitude": ",".join(str(p[1]) for p in POINTS),
    "timezone": "GMT",
    "past_days": 1,
    "forecast_days": 4,
}


def collect(con):
    mf = get(URL, expect_json=True, params={
        **COMMON, "models": "meteofrance_seamless", "daily": "sunrise,sunset",
        "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m,wind_speed_925hPa,wind_direction_925hPa,"
                  "precipitation,cloud_cover,cloud_cover_low",
    })
    # Les modèles Météo-France ne fournissent pas la visibilité : modèle par défaut d'Open-Meteo.
    vis = get(URL, expect_json=True, params={**COMMON, "hourly": "visibility"})
    if not isinstance(mf, list) or len(mf) != len(POINTS):
        raise RuntimeError("réponse Open-Meteo inattendue")
    t_now, fetched, n = now_utc(), iso(now_utc()), 0
    for (lat, lon), loc, lv in zip(POINTS, mf, vis):
        h, hv = loc["hourly"], dict(zip(lv["hourly"]["time"], lv["hourly"]["visibility"]))
        for i, t in enumerate(h["time"]):
            dt = datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
            con.execute(
                "INSERT OR REPLACE INTO weather VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (lat, lon, iso(dt), h["wind_direction_10m"][i], h["wind_speed_10m"][i], h["wind_gusts_10m"][i],
                 h["cloud_cover"][i], h["precipitation"][i], int(dt > t_now), h["cloud_cover_low"][i], hv.get(t),
                 h["wind_direction_925hPa"][i], h["wind_speed_925hPa"][i], fetched),
            )
            n += 1
        d = loc["daily"]
        for i, day in enumerate(d["time"]):
            con.execute("INSERT OR REPLACE INTO daylight VALUES (?,?,?,?,?)",
                        (lat, lon, day, d["sunrise"][i] + ":00Z", d["sunset"][i] + ":00Z"))
    con.commit()
    return n


if __name__ == "__main__":
    run_collector("meteo", URL, collect, every_minutes=55)
