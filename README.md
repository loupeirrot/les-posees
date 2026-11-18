# Les posées

Prévision des passages de palombes et de grives sur la dune landaise (Labenne, Capbreton, Hossegor, Seignosse), avec les signalements Flash et les comptages des cols. Site statique publié sur GitHub Pages, mis à jour toutes les 15 minutes par GitHub Actions.

## Comment ça marche
```
GitHub Actions (toutes les 15 min du 15/09 au 30/11, une fois par jour sinon)
  pipeline/collect_*.py  →  data/migration.db (SQLite, gardée sur la branche data)
  pipeline/build_json.py →  public/latest.json + site/src/data/*.json  (gel de la prévision à 6 h 30)
  pipeline/validate.py   →  contrôle de latest.json contre schema.json
  pipeline/og.py         →  images de partage du jour
  pipeline/alerts.py     →  issue GitHub si une source tombe en pleine saison
  site/ (Astro)          →  pages statiques  →  GitHub Pages
```

## Sources
| Source | Collecteur | Rythme | Remarque |
|---|---|---|---|
| palombe.com, Flash migration (carte de France, publique) | `collect_palombe_flash.py` | 15 min | positions arrondies à 0,1°, aucun pseudo |
| palombe.com, observations | `collect_palombe_observations.py` | 1 h | département et vols par classe ; ni pseudo, ni lieu-dit, ni texte |
| palombe.com, comptages des cols (GIFS France) | `collect_palombe_comptages.py` | 1 fois par jour après 20 h 30 | chiffres bruts, saisons 2011 à 2026 |
| Trektellen (Organbidexka) | `collect_trektellen.py` | 1 fois par jour | bloqué par la protection anti-robots : export à demander |
| Open-Meteo (modèles Météo-France) | `collect_meteo.py` | 1 h | voir « Limites » |

La carte Flash zoomée sur le Sud-Ouest pour la saison en cours est réservée aux abonnés de palombe.com : elle n'est pas utilisée.

## Autorisations
| Source | Accord reçu | Condition |
|---|---|---|
| palombe.com (dont les comptages des cols réalisés pour le GIFS France) | 5 novembre 2026 | utilisation libre, citation dans les mentions légales |
| Trektellen | 13 novembre 2026 | utilisation libre, citation dans les mentions légales |

Les mails d'accord sont à ranger dans `docs/autorisations/`. Les mentions sont publiées sur la page `/mentions-legales/` du site (texte dans `docs/mentions-legales-sources.md`). Interrupteurs : variables du dépôt `PALOMBE_COM_ENABLED` et `TREKTELLEN_ENABLED` (`true` par défaut), dans Settings > Secrets and variables > Actions > Variables.

## Installation locale
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd pipeline && ../.venv/bin/python collect_palombe_flash.py && ../.venv/bin/python build_json.py && cd ..
cd site && npm ci && npx astro build && npx astro preview
```
Aperçu avec un relevé météo réel de test (30/10/2026) : voir `tests/load_fixture.py`.

## Mise en ligne sur GitHub Pages
1. Créer le dépôt et pousser `main`.
2. Settings > Pages > Source : **GitHub Actions**.
3. Settings > Secrets > Actions : `COLLECTOR_CONTACT` (adresse de contact affichée dans le User-Agent des collecteurs).
4. Lancer le workflow « Collecte et publication » à la main une première fois (case « Interroger toutes les sources »).

## Limites
- **Météo** : le `robots.txt` de api.open-meteo.com interdit tout (`Disallow: /`). Les collecteurs respectent robots.txt, donc la météo est marquée « bloquée » et le site passe en mode dégradé (signalements et comptages seulement). Décision à prendre : autoriser l'API Open-Meteo (dont les conditions d'utilisation permettent l'usage gratuit non commercial), ou passer à l'API Météo-France (clé gratuite).
- **Trektellen** : vérification anti-robots Cloudflare (403). Non contournée. Il faut un export ou une autorisation du User-Agent.
- **Flash** : positions calées à 3 à 5 km près, puis arrondies à environ 10 km. Le regroupement des minutes (5 min) retrouve 16 signalements le 17/11/2026 quand palombe.com en annonce 17. Les classes de taille 1 à 5 sont supposées correspondre aux classes de palombe.com (1-10 … +300).
- **Indice** : règle provisoire, non validée (voir la page Méthode).
- **GitHub Actions** : les tâches planifiées peuvent être retardées. Sur un dépôt public, elles s'arrêtent après 60 jours sans activité sur le dépôt.
- **Signalements des chasseurs depuis le site** et **notifications** : demandent un serveur (prévus pour la phase OVH).
