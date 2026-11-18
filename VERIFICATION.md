# Vérification (18 novembre 2026)

## 1. Comptages : page et base côte à côte
Page relue : https://www.palombe.com/migration/comptages.php?year=2026 (relecture indépendante par expressions régulières, `tests/verify_comptages.py`). Le collecteur, lui, utilise BeautifulSoup.

| Date | Poste | Aller oiseaux (page / base) | Aller vols | Retour oiseaux | Retour vols | Identique |
|---|---|---|---|---|---|---|
| 2026-10-27 | Arnéguy | 5009 / 5009 | 38 / 38 | 814 / 814 | 10 / 10 | oui |
| 2026-10-27 | Banca | 40643 / 40643 | 108 / 108 | 474 / 474 | 14 / 14 | oui |
| 2026-10-27 | Sare | 51951 / 51951 | 108 / 108 | 104 / 104 | 3 / 3 | oui |
| 2026-10-27 | Urrugne | 44674 / 44674 | 85 / 85 | 11442 / 11442 | 141 / 141 | oui |
| 2026-10-30 | Arnéguy | 213 / 213 | 10 / 10 | 28 / 28 | 5 / 5 | oui |
| 2026-10-30 | Banca | 145 / 145 | 7 / 7 | 672 / 672 | 13 / 13 | oui |
| 2026-10-30 | Sare | 40 / 40 | 3 / 3 | 468 / 468 | 11 / 11 | oui |
| 2026-10-30 | Urrugne | 27 / 27 | 3 / 3 | 10774 / 10774 | 249 / 249 | oui |
| 2026-11-17 | Arnéguy | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | oui |
| 2026-11-17 | Banca | 3 / 3 | 1 / 1 | 0 / 0 | 0 / 0 | oui |
| 2026-11-17 | Sare | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | oui |
| 2026-11-17 | Urrugne | 0 / 0 | 0 / 0 | 19 / 19 | 1 / 1 | oui |

**48 nombres sur 48 identiques.** Le 27/10/2026 a été choisi pour ses nombres à 5 chiffres (séparateur d'espace insécable) et ses retours importants. La note du jour, « RETOURS : 11 442 pal à Urrugne », confirme que le petit nombre de chaque case est le **retour**. Contrôle à la main : ouvrir la page et regarder ces trois lignes.

## 2. Schéma JSON
`python pipeline/validate.py` : « latest.json valide », sur les données réelles du 18/11/2026 (mode dégradé) et sur l'aperçu avec la météo de test du 30/10/2026 (mode complet).

## 3. Workflow GitHub Actions
**Non vérifié** : le dépôt n'est pas encore créé sur GitHub. Il faudra trois exécutions consécutives réussies après la mise en ligne. Les liens seront ajoutés ici.

## 4. Test de panne
Flash coupé (`PALOMBE_COM_ENABLED=false`) sur une copie de la base, puis `build_json.py` et `alerts.py` :
```
ALERTE palombe_flash : coupée Source désactivée par interrupteur
ALERTE meteo : bloquée robots.txt interdit https://api.open-meteo.com/v1/forecast?...
```
L'alerte se déclenche. En local, sans jeton GitHub, elle s'affiche seulement. Dans le workflow, elle ouvre une issue (étiquette `alerte-source`), qui se ferme seule au retour à la normale. **La création réelle d'issue n'est pas vérifiée** tant que le dépôt n'existe pas.

## Ce qui n'a pas pu être vérifié
- **Météo réelle en production** : bloquée par le robots.txt d'Open-Meteo (décision à prendre). Le mode complet n'a été vu qu'avec le relevé réel du 30/10/2026.
- **Trektellen** : la lecture du tableau des totaux n'a jamais pu être testée (page derrière la protection anti-robots).
- **Correspondance des classes de taille Flash** (1 à 5 contre 1-10 … +300) : supposée, pas confirmée par palombe.com.
- **Regroupement des signalements Flash** : 16 trouvés contre 17 annoncés le 17/11/2026.
- **Lighthouse et test sur un téléphone d'entrée de gamme** : non faits. Page d'accueil de 22 Ko compressée, sans JavaScript bloquant.
- **Hors ligne (service worker)** : il ne s'active qu'en HTTPS, donc il n'a pas été testé en local.
