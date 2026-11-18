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
INK, SAND, PINE, MUTED = "#ece5d3", "#121611", "#c8501a", "#a9ab98"  # charte « Lette et brume » : fond nuit, accent orange
LEVEL = {"good": ("#24552d", "#f4efe2"), "maybe": ("#e0a72e", "#1c1608"), "low": ("#3b403d", "#f1ece0"), None: ("#3b403d", "#f1ece0")}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def font(kind, size):
    if kind == "display":
        f = ImageFont.truetype(str(FONTS / "Archivo.ttf"), size)
        f.set_variation_by_axes([800, 62])  # axes d'Archivo : graisse, puis largeur (62 = la plus étroite)
        return f
    return ImageFont.truetype(str(FONTS / ("Atkinson-Bold.ttf" if kind == "bold" else "Atkinson-Regular.ttf")), size)


def fr_day(iso):
    d = date.fromisoformat(iso)
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"


def draw_card(w, h, sector, cat, f, day, scale=1.0):
    lvl = f["level"] if f else None
    bg, fg = LEVEL[lvl]
    im = Image.new("RGB", (w, h), SAND)
    d = ImageDraw.Draw(im)
    m = int(64 * scale)
    d.text((m, m), "LES POSÉES", font=font("display", int(48 * scale)), fill=PINE)
    d.text((m, m + int(62 * scale)), f"{'Palombe' if cat == 'palombe' else 'Grives'} · {sector} · {fr_day(day)}", font=font("body", int(34 * scale)), fill=INK)
    top = m + int(140 * scale)
    d.rounded_rectangle((m, top, w - m, h - m - int(70 * scale)), radius=int(14 * scale), fill=bg)
    word = (f["word"] if f else "Prévision indisponible").upper()
    size = int(104 * scale)
    while font("display", size).getlength(word) > w - 2 * m - int(80 * scale):
        size -= 4
    d.text((m + int(40 * scale), top + int(34 * scale)), word, font=font("display", size), fill=fg)
    if f:
        y = top + int(34 * scale) + size + int(18 * scale)
        d.text((m + int(40 * scale), y), f"{f['window']['label']} : {f['window']['text']}", font=font("bold", int(38 * scale)), fill=fg)
        d.text((m + int(40 * scale), y + int(56 * scale)), f"Vent {f['wind']['dir_name']} {f['wind']['speed']} km/h, {f['wind']['force']}", font=font("body", int(36 * scale)), fill=fg)
    d.text((m, h - m - int(40 * scale)), "Indice provisoire · prévision indicative", font=font("body", int(28 * scale)), fill=MUTED)
    return im


def icons():
    ICONS.mkdir(parents=True, exist_ok=True)
    for size, pad, name in ((192, 0.0, "icon-192.png"), (512, 0.0, "icon-512.png"), (512, 0.12, "icon-512-maskable.png")):
        im = Image.new("RGB", (size, size), "#c8501a")
        d = ImageDraw.Draw(im)
        f = font("display", int(size * (0.62 - pad)))
        text = "P"
        tw = f.getlength(text)
        bbox = f.getbbox(text)
        d.text(((size - tw) / 2, (size - (bbox[3] + bbox[1])) / 2), text, font=f, fill="#fff4ea")
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
