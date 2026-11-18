"""Images de partage du jour (Open Graph 1200x630, carré 1080, story 1080x1920) et icônes de l'application.

Les liens partagés sur WhatsApp ou Facebook affichent directement le verdict du secteur.
"""
import json
from datetime import date

from PIL import Image, ImageDraw, ImageFont

from common import ROOT, SECTORS

FONTS = ROOT / "fonts"
OUT = ROOT / "site" / "public" / "og"
ICONS = ROOT / "site" / "public" / "icons"
INK, SAND, PINE, MUTED = "#121a16", "#ecede7", "#21402e", "#4c5751"
LEVEL = {"good": ("#146b3e", "#d7eedf"), "maybe": ("#865000", "#f5e5c7"), "low": ("#47515a", "#e1e5e7"), None: ("#47515a", "#e1e5e7")}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def font(kind, size):
    if kind == "display":
        f = ImageFont.truetype(str(FONTS / "Archivo.ttf"), size)
        try:
            f.set_variation_by_axes([75, 800])  # largeur étroite, graisse forte
        except Exception:  # noqa: BLE001
            pass
        return f
    return ImageFont.truetype(str(FONTS / ("Atkinson-Bold.ttf" if kind == "bold" else "Atkinson-Regular.ttf")), size)


def fr_day(iso):
    d = date.fromisoformat(iso)
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"


def draw_card(w, h, sector, cat, f, day, scale=1.0):
    lvl = f["level"] if f else None
    border, bg = LEVEL[lvl]
    im = Image.new("RGB", (w, h), SAND)
    d = ImageDraw.Draw(im)
    m = int(64 * scale)
    d.text((m, m), "Les posées", font=font("display", int(44 * scale)), fill=PINE)
    d.text((m, m + int(62 * scale)), f"{'Palombe' if cat == 'palombe' else 'Grives'} · {sector} · {fr_day(day)}", font=font("body", int(34 * scale)), fill=INK)
    top = m + int(140 * scale)
    d.rounded_rectangle((m, top, w - m, h - m - int(70 * scale)), radius=int(28 * scale), fill=bg, outline=border, width=int(6 * scale))
    word = f["word"] if f else "Prévision indisponible"
    size = int(120 * scale)
    while font("display", size).getlength(word) > w - 2 * m - int(80 * scale):
        size -= 4
    d.text((m + int(40 * scale), top + int(40 * scale)), word, font=font("display", size), fill=INK)
    if f:
        y = top + int(40 * scale) + size + int(30 * scale)
        d.text((m + int(40 * scale), y), f"{f['window']['label']} : {f['window']['text']}", font=font("bold", int(38 * scale)), fill=INK)
        d.text((m + int(40 * scale), y + int(56 * scale)), f"Vent {f['wind']['dir_name']} {f['wind']['speed']} km/h, {f['wind']['force']}", font=font("body", int(36 * scale)), fill=INK)
    d.text((m, h - m - int(40 * scale)), "Indice provisoire · prévision indicative", font=font("body", int(28 * scale)), fill=MUTED)
    return im


def icons():
    ICONS.mkdir(parents=True, exist_ok=True)
    for size, pad, name in ((192, 0.0, "icon-192.png"), (512, 0.0, "icon-512.png"), (512, 0.12, "icon-512-maskable.png")):
        im = Image.new("RGB", (size, size), PINE)
        d = ImageDraw.Draw(im)
        f = font("display", int(size * (0.62 - pad)))
        text = "P"
        tw = f.getlength(text)
        bbox = f.getbbox(text)
        d.text(((size - tw) / 2, (size - (bbox[3] + bbox[1])) / 2), text, font=f, fill="#f4f2ea")
        im.save(ICONS / name, optimize=True)


def main():
    latest = json.loads((ROOT / "public" / "latest.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    day = latest["today"]
    for key, s in SECTORS.items():
        for cat in ("palombe", "grives"):
            f = latest["forecast"][key][cat].get(day)
            draw_card(1200, 630, s["name"], cat, f, day).save(OUT / f"{key}-{cat}.png", optimize=True)
            draw_card(1080, 1080, s["name"], cat, f, day, 1.0).save(OUT / f"{key}-{cat}-carre.png", optimize=True)
            draw_card(1080, 1920, s["name"], cat, f, day, 1.25).save(OUT / f"{key}-{cat}-story.png", optimize=True)
    icons()
    print("images de partage :", len(list(OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
