"""Trektellen : comptages standardisés (Organbidexka #2133), pigeon ramier et grives.

Accord d'utilisation reçu le 13/11/2026. Les pages de totaux sont derrière une vérification anti-robots
(Cloudflare) : le collecteur fait une requête normale et, s'il reçoit la page de vérification, marque la
source « bloquée » sans chercher à la contourner. La solution est un export ou une autorisation du
User-Agent, à demander à Trektellen. Dès que la page répond, le collecteur lit les totaux.
"""
import re

from bs4 import BeautifulSoup

from common import TREKTELLEN_ENABLED, FormatChanged, dumps, get, iso, now_utc, paris_now, run_collector

SITES = {2133: ("Col d'Organbidexka", 43.035, -1.022)}
SPECIES = {"Pigeon ramier": "Columba palumbus", "Grive musicienne": "Turdus philomelos", "Grive mauvis": "Turdus iliacus",
           "Grive draine": "Turdus viscivorus", "Grive litorne": "Turdus pilaris"}
URL = "https://www.trektellen.org/site/totals/{site}/{year}"
SOURCE = "Trektellen"


def parse_totals(html):
    """Tableau des totaux annuels : une ligne par espèce (nom français ou latin), total en dernière colonne."""
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(cells) < 2:
            continue
        for fr, la in SPECIES.items():
            if any(fr.lower() == c.lower() or la.lower() in c.lower() for c in cells):
                nums = [int(re.sub(r"\D", "", c)) for c in cells if re.fullmatch(r"[\d . ]+", c) and re.sub(r"\D", "", c)]
                if nums:
                    found[fr] = nums[-1]
    if not found and "Columba" not in html and "ramier" not in html.lower():
        raise FormatChanged("aucune espèce cible trouvée dans la page des totaux")
    return found


def collect(con):
    year = paris_now().year
    n, fetched = 0, iso(now_utc())
    for site, (name, lat, lon) in SITES.items():
        url = URL.format(site=site, year=year)
        totals = parse_totals(get(url))
        for sp, total in totals.items():
            con.execute(
                "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"trektellen:{site}:{year}:{sp}", SOURCE, url, name, lat, lon, sp, f"{year}", None, total, None,
                 None, None, None, None, dumps({"type": "total_saison"}), fetched),
            )
            n += 1
    con.commit()
    return n


if __name__ == "__main__":
    run_collector("trektellen", URL.format(site=2133, year=paris_now().year), collect,
                  enabled=TREKTELLEN_ENABLED, every_minutes=24 * 60 - 20)
