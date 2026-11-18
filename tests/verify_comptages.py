"""Contrôle croisé : relit comptages.php avec une méthode indépendante (expressions régulières sur le HTML brut)
et compare, pour 3 dates, chaque nombre à celui stocké en base par le collecteur (BeautifulSoup).
Écrit le tableau dans VERIFICATION.md (section comptages).

Usage : python tests/verify_comptages.py 2026-10-27 2026-10-30 2026-11-17
"""
import html
import re
import sqlite3
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from common import USER_AGENT  # noqa: E402

POSTES = ["Arnéguy", "Banca", "Sare", "Urrugne"]
dates = sys.argv[1:]
year = dates[0][:4]
url = f"https://www.palombe.com/migration/comptages.php?year={year}"
raw = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30).text
num = lambda s: None if s.strip() in ("", "-") else int(html.unescape(s).replace("\xa0", "").replace(" ", ""))  # noqa: E731

page = {}
month = None
MOIS = {"Octobre": "10", "Novembre": "11", "Septembre": "09", "Décembre": "12"}
for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", re.sub(r"<!--.*?-->", "", raw, flags=re.S), flags=re.S):
    tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
    text = re.sub(r"<[^>]+>", "", tr).strip()
    for m, mm in MOIS.items():
        if len(tds) == 1 and text.startswith(m):
            month = mm
    if len(tds) >= 12 and month:
        day = re.sub(r"<[^>]+>", "", tds[1]).strip()
        if not day.isdigit():
            continue
        d = f"{year}-{month}-{int(day):02d}"
        cells = []
        for td in tds[2:10]:
            mm_ = re.match(r"\s*(.*?)<br\s*/?>\s*<span class=\"little\"[^>]*>(.*?)</span>", td, flags=re.S)
            cells.append((num(re.sub(r"<[^>]+>", "", mm_.group(1))), num(mm_.group(2))))
        page[d] = cells

con = sqlite3.connect(ROOT / "data" / "migration.db")
lines = ["| Date | Poste | Aller oiseaux (page / base) | Aller vols | Retour oiseaux | Retour vols | Identique |", "|---|---|---|---|---|---|---|"]
all_ok = True
for d in dates:
    cells = page[d]
    for i, poste in enumerate(POSTES):
        (nb_a, nb_r), (v_a, v_r) = cells[2 * i], cells[2 * i + 1]
        db = {r[0]: (r[1], r[2]) for r in con.execute(
            "SELECT direction, count, flights FROM observations WHERE source='palombe.com / GIFS France' AND date=? AND site_name=?", (d, poste))}
        ok = db.get("aller") == (nb_a, v_a) and db.get("retour") == (nb_r, v_r)
        all_ok &= ok
        lines.append(f"| {d} | {poste} | {nb_a} / {db['aller'][0]} | {v_a} / {db['aller'][1]} | {nb_r} / {db['retour'][0]} | {v_r} / {db['retour'][1]} | {'oui' if ok else '**NON**'} |")
table = "\n".join(lines)
print(table)
print("TOUT IDENTIQUE" if all_ok else "ÉCARTS TROUVÉS")
out = ROOT / "tests" / "verification_comptages.md"
out.write_text(f"Page relue : {url}\n\n{table}\n\nRésultat : {'tout identique' if all_ok else 'écarts trouvés'}\n", encoding="utf-8")
sys.exit(0 if all_ok else 1)
