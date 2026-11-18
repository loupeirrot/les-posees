"""Indice provisoire (RuleV0) : règle transparente du vent, de la pluie et de la brume.

Non validée : sur 4 saisons de radar, ni cette règle ni un modèle statistique ne battent un taux fixe pour
les grives (voir docs/03). Affichée comme « indice provisoire ».
"""
import math
from datetime import datetime, timedelta, timezone

from common import PARIS

DIRS = ["nord", "nord-est", "est", "sud-est", "sud", "sud-ouest", "ouest", "nord-ouest"]
DIRS_SHORT = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
WORDS = {"good": "Ça devrait passer", "maybe": "Possible", "low": "Peu probable"}


def sector8(deg):
    return round((deg % 360) / 45) % 8


def in_arc(deg, a, b):
    return a <= deg <= b if a <= b else deg >= a or deg <= b


def force(s):
    return "calme" if s < 6 else "léger" if s < 16 else "établi" if s < 30 else "fort"


def fmt_min(m):
    m = round(m)
    return f"{m // 60} h {m % 60:02d}" if m % 60 else f"{m // 60} h"


class Hourly:
    """Accès aux heures locales (Paris) d'un point météo."""

    def __init__(self, rows, sunrise):
        self.by_utc = {r["datetime"]: r for r in rows}
        self.sunrise = sunrise  # {date iso Paris: datetime Paris}

    def at(self, day, hour, key):
        local = datetime(day.year, day.month, day.day, hour, tzinfo=PARIS)
        r = self.by_utc.get(local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return None if r is None else r[key]

    def series(self, day, h0, h1, key):
        return [v for h in range(h0, h1 + 1) if (v := self.at(day, h, key)) is not None]


def mean_dir(dirs, speeds):
    u = sum((s or 1) * math.sin(math.radians(d)) for d, s in zip(dirs, speeds))
    v = sum((s or 1) * math.cos(math.radians(d)) for d, s in zip(dirs, speeds))
    return (math.degrees(math.atan2(u, v)) + 360) % 360


def mean(a):
    return sum(a) / len(a) if a else None


def evaluate(h, category, day):
    sr = h.sunrise.get(day.isoformat())
    w10, s10 = h.at(day, 8, "wind_dir"), h.at(day, 8, "wind_speed")
    if sr is None or w10 is None:
        return None
    sr_min = sr.hour * 60 + sr.minute
    w925, s925 = h.at(day, 8, "wind_dir_925"), h.at(day, 8, "wind_speed_925")
    vis = {hh: h.at(day, hh, "visibility") for hh in range(7, 13)}
    fog = [hh for hh in range(7, 12) if vis[hh] is not None and vis[hh] < 1000]
    clear_at = next((hh for hh in range(7, 13) if vis[hh] is not None and vis[hh] >= 1000), None)
    crit = []
    if category == "palombe":
        rain = sum(h.series(day, 7, 11, "precip"))
        low = mean(h.series(day, 7, 11, "cloud_low")) or 0
        gust = max(h.series(day, 7, 11, "gusts") or [0])
        crit += [
            {"ok": in_arc(w10, 0, 150), "label": "Vent de secteur nord à sud-est", "detail": f"À 8 h : {DIRS[sector8(w10)]}, {round(s10)} km/h"},
            {"ok": rain < 0.3, "label": "Pas de pluie dans la matinée", "detail": f"{rain:.1f} mm entre 7 h et 11 h"},
            {"ok": len(fog) <= 1 and low < 80, "label": "Ciel lisible, pas de brume",
             "detail": f"Nuages bas {round(low)} % · " + ("brume à " + ", ".join(f"{x} h" for x in fog) if fog else "pas de brume")},
            {"ok": gust < 50 and s10 < 30, "label": "Pas de coup de vent", "detail": f"Rafales jusqu'à {round(gust)} km/h", "blocking": True},
        ]
        start = max(sr_min - 15, clear_at * 60 if fog and clear_at else 0)
        window = {"label": "Fenêtre probable", "start": start, "end": max(sr_min + 180, start + 90)}
    else:
        prev = day - timedelta(days=1)
        nd = h.series(prev, 19, 23, "wind_dir") + h.series(day, 0, 7, "wind_dir")
        ns = h.series(prev, 19, 23, "wind_speed") + h.series(day, 0, 7, "wind_speed")
        nr = sum(h.series(prev, 19, 23, "precip") + h.series(day, 0, 6, "precip"))
        ndir = mean_dir(nd, ns) if nd else w10
        dawn_ws = mean(h.series(day, 7, 10, "wind_speed")) or 0
        dawn_pr = sum(h.series(day, 7, 10, "precip"))
        crit += [
            {"ok": in_arc(ndir, 300, 120), "label": "Vent de nuit porteur (nord-ouest à est)",
             "detail": f"Moyenne de la nuit : {DIRS[sector8(ndir)]}, {round(mean(ns) or 0)} km/h"},
            {"ok": nr < 0.5, "label": "Nuit sèche", "detail": f"{nr:.1f} mm entre 19 h et 7 h"},
            {"ok": dawn_ws < 25 and dawn_pr < 0.3, "label": "Aube calme et sèche",
             "detail": f"Vent moyen {round(dawn_ws)} km/h, pluie {dawn_pr:.1f} mm (7 h – 10 h)"},
        ]
        window = {"label": "Posées probables", "start": sr_min - 30, "end": 10 * 60 + 30}
    main = [c for c in crit if not c.get("blocking")]
    n = sum(c["ok"] for c in main)
    level = "good" if n == len(main) else "maybe" if n == len(main) - 1 else "low"
    if any(c.get("blocking") and not c["ok"] for c in crit):
        level = "low"
    vis_min = min((v for v in vis.values() if v is not None), default=None)
    return {
        "level": level, "word": WORDS[level], "score": n, "total": len(main), "criteria": crit,
        "window": {**window, "text": f"{fmt_min(window['start'])} à {fmt_min(window['end'])}"},
        "sunrise": fmt_min(sr_min),
        "wind": {"dir": round(w10), "speed": round(s10), "dir_short": DIRS_SHORT[sector8(w10)], "dir_name": DIRS[sector8(w10)], "force": force(s10)},
        "wind_800": None if w925 is None else {"dir": round(w925), "speed": round(s925), "dir_short": DIRS_SHORT[sector8(w925)]},
        "reading": reading(category, level, w10, s10),
        "fog": {"hours": fog, "clear_at": clear_at, "min_visibility_m": None if vis_min is None else round(vis_min)} if fog else None,
        "hours": [{"h": hh, "wind_dir": h.at(day, hh, "wind_dir"), "wind_speed": h.at(day, hh, "wind_speed"),
                   "gusts": h.at(day, hh, "gusts"), "wind_dir_800": h.at(day, hh, "wind_dir_925"),
                   "wind_speed_800": h.at(day, hh, "wind_speed_925"), "visibility": h.at(day, hh, "visibility"),
                   "precip": h.at(day, hh, "precip"), "cloud_low": h.at(day, hh, "cloud_low")} for hh in range(6, 13)],
    }


def reading(category, level, d, s):
    if category == "grives":
        return {"good": "Nuit à vent porteur et sèche : bonne nuit pour une arrivée de grives. Regarde les pins et les haies dès l'aube.",
                "maybe": "Conditions moyennes cette nuit : quelques posées possibles, pas de grosse arrivée attendue.",
                "low": "Nuit défavorable (vent contraire ou pluie) : peu de grives attendues au matin."}[level]
    if s < 6:
        return "Vent quasi nul : les vols passent à leur hauteur habituelle, la dune ne les concentre pas."
    base = [
        "Vent porteur du nord : ça peut passer vite, et souvent haut.",
        "Nord-est porteur : ça peut passer haut. L'est pousse les vols vers l'océan, ils longent la dune.",
        "Vent d'est : les vols dérivent vers la côte et longent la dune.",
        "Sud-est : vent de travers, les vols se rabattent sur la côte et passent plus bas.",
        "Vent de face (sud) : les vols passent bas mais s'arrêtent ou se posent vite.",
        "Sud-ouest de face : vols bas et hésitants, souvent posés.",
        "Vent d'ouest : les vols sont repoussés vers l'intérieur, moins sur la dune.",
        "Nord-ouest : porteur mais venu de la mer, les vols restent plutôt à l'intérieur.",
    ][sector8(d)]
    return base + (" Vent fort : passage gêné." if s >= 30 else "")
