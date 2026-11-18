# Prompt Claude Code : collecte automatique des données de migration

> Prompt fourni par Pierre le 18/11/2026, repris tel quel. La section « Compléments » à la fin a été ajoutée après vérification des pages le même jour. Colle **les deux parties** dans Claude Code, depuis un dossier vide (par exemple `~/projets/migration-data`).
>
> Ce dépôt de collecte alimente le site décrit dans [PROMPT-CLAUDE-CODE.md](PROMPT-CLAUDE-CODE.md) : le site lit `public/latest.json`.

---

## Contexte
Je construis un site pour un chasseur de palombes et de grives qui chasse dans les dunes entre Labenne et Seignosse (Landes, environ 43.64 N, -1.45 E). Il le consultera sur son téléphone pendant la chasse. Ta mission ici couvre uniquement la couche de données : récupérer automatiquement les comptages et observations de référence, les normaliser, les stocker et exposer un JSON que le site lira. Ne construis pas le site.

## Outil imposé pour les sources sans API
Utilise reverse-api-engineer (github.com/kalil0321/reverse-api-engineer) pour trouver les endpoints derrière les pages :

* Installe-le en skill Claude Code : `npx -y skills add kalil0321/reverse-api-engineer --skill reverse-engineering-api --agent claude-code`
* Ou en CLI : `uv tool install reverse-api-engineer` puis `playwright install chromium`
* Commence en mode Manual ou Agent sur chaque page, puis génère un client Python. Relis le code généré avant de l'exécuter.

Si une source propose déjà un export (CSV, JSON, flux), utilise-le plutôt que du reverse engineering.

## Sources, par ordre de priorité
1. **palombe.com : comptages des postes pyrénéens et basques** (réalisés par les techniciens des fédérations de chasse pour GIFS France)
   `https://www.palombe.com/migration/comptages.php?year=2026`
   Par jour et par poste (Arnéguy, Banca, Sare, Urrugne) : oiseaux, nombre de vols, aller et retour, météo, note. Récupère la saison en cours et les saisons précédentes (paramètre `year`).
2. **palombe.com : Flash migration en temps réel** (signalements des observateurs sur une carte)
   `https://www.palombe.com/flash/flash.php`
   Trouve l'endpoint qui alimente la carte : heure, position, effectif, vols de recul (affichés en orange). C'est la source la plus utile en direct pour le Sud-Ouest.
3. **palombe.com : observations et synthèse**
   `https://www.palombe.com/migration/observations.php?year=2026` et `https://www.palombe.com/migration/migration.php?year=2026`
4. **Trektellen** (comptages standardisés, toutes espèces, y compris grives)
   Col d'Organbidexka = site 2133 (`https://www.trektellen.nl/site/totals/2133/2020`). Trouve les identifiants de Lindux, Lizarrieta, et des sites côtiers landais ou girondins s'il y en a. Espèces : Pigeon ramier, Grive musicienne, Grive mauvis, Grive draine, Grive litorne.
5. **Météo** (obligatoire, c'est le premier facteur de passage) : API Open-Meteo, gratuite et sans clé. Vent (direction, force, rafales), couverture nuageuse, précipitations, à l'heure, pour 43.64 / -1.45 et pour le col d'Organbidexka (43.035 / -1.022). Prévisions J à J+3.

**Exclus** : l'appli Palombe Passion (contenu derrière un abonnement et une appli mobile), Facebook et Instagram (CGU, connexion obligatoire).

## Règles de collecte (non négociables)
* Lis le `robots.txt` de chaque site et respecte-le.
* Aucun contournement de connexion, de captcha ou de paywall. Données publiques uniquement.
* Débit : une requête par source toutes les 15 min au maximum pour le Flash, une fois par jour pour les comptages et Trektellen. Mets en cache.
* User-Agent explicite avec une adresse de contact (demande-la-moi).
* Garde la source et l'URL d'origine sur chaque ligne de données. Le site affichera « Source : palombe.com / GIFS France » avec un lien.
* **Autorisations** : palombe.com (accord reçu le 5 novembre 2026) et Trektellen (accord reçu le 13 novembre 2026) autorisent une utilisation totalement libre de leurs données. Leur seule condition : être cités dans les mentions légales du site. Le JSON public peut donc reprendre leurs chiffres complets.
  * Écris le paragraphe à insérer dans les mentions légales (`docs/mentions-legales-sources.md`) : nom de chaque source, lien vers son site, rôle de GIFS France pour les comptages des postes, date de l'accord.
  * Ajoute dans `README.md` une section « Autorisations » qui reprend ces deux accords, leur date et leur condition. Les mails d'accord sont rangés dans `docs/autorisations/`.
  * En plus de cette obligation, garde un lien discret vers la page d'origine sur chaque bloc de données : c'est ce qui rend le site crédible auprès des chasseurs.
  * Règle de qualité : ne modifie jamais les chiffres bruts (aucune correction, aucun lissage). Les calculs dérivés vont dans des champs séparés, nommés comme tels.
  * Prévois les interrupteurs `PALOMBE_COM_ENABLED` et `TREKTELLEN_ENABLED` pour couper une source en une ligne si besoin.

## Modèle de données
Base SQLite `data/migration.db`, avec :
- une table `observations` : `source, url, site_name, lat, lon, species, date, time, count, flights, direction (aller/retour/recul), weather_note, fetched_at` ;
- une table `weather` : `lat, lon, datetime, wind_dir, wind_speed, gusts, cloud, precip, is_forecast`.

Export `public/latest.json` :
* les dernières 24 h de Flash dans un rayon de 150 km autour de Labenne–Seignosse ;
* les comptages J et J-1 par poste, avec le cumul de la saison ;
* la comparaison avec la moyenne des saisons précédentes à la même date ;
* la météo actuelle et à J+3 ;
* un champ `status` par source (ok, vide, en erreur) et l'heure de la dernière mise à jour.

## Automatisation
* Un script `collect.py` par source, plus un `build_json.py`.
* Planification avec GitHub Actions (cron) : toutes les 15 min du 15 septembre au 30 novembre, une fois par jour le reste de l'année.
* Publication du `latest.json` sur mon hébergement OVH en SFTP (identifiants en secrets GitHub, jamais dans le code ; demande-les-moi au moment voulu).
* Alerte (issue GitHub ou mail) si une source renvoie zéro ligne alors qu'on est en pleine saison, ou si le format de la page a changé.

## Critère de réussite (à vérifier avant de me rendre le travail)
1. Pour 3 dates de la saison 2026 que tu choisis, les chiffres stockés pour chaque poste sont identiques à ceux affichés sur `comptages.php`. Mets dans `VERIFICATION.md` un tableau page / base côte à côte, avec les URL, pour que je contrôle à la main.
2. `latest.json` passe la validation d'un schéma JSON que tu écris (`schema.json`).
3. Le workflow GitHub Actions a tourné 3 fois de suite sans erreur (lien vers les exécutions).
4. Test de panne : si tu coupes une source, l'alerte se déclenche.

Liste ce qui n'a pas pu être vérifié au lieu de le présenter comme fait.

## Livrables
Le repo avec `README.md` (installation, sources, limites), `VERIFICATION.md`, `schema.json`, le workflow et `docs/mentions-legales-sources.md`.

---

## Compléments (constats du 18/11/2026, à coller avec le reste)

**1. Structure réelle de `comptages.php`** (lue sur `?year=2025` et `?year=2026`) :
- C'est un seul `<table>`. Chaque poste a deux colonnes (`Nb`, `Vol`). **Chaque cellule contient deux nombres** : le nombre principal, puis un second dans `<span class="little">`. Exemple réel du samedi 25/10/2025 à Urrugne : `1&nbsp;855<br/><span class="little">360</span>`. Ne lis jamais le texte brut de la cellule : il colle les deux nombres (« 1 855360 »). Lis le nombre principal et le `span.little` séparément. Vérifie sur la légende de la page lequel est l'aller et lequel le retour avant de nommer les champs.
- Les milliers sont séparés par `&nbsp;` (« 2&nbsp;741 »).
- La météo n'est pas du texte : c'est une classe CSS d'icône (`<td class="meteo3">`). Stocke le code tel quel (`meteo_code = "meteo3"`) et retrouve sa signification sur la page, sans l'inventer. La colonne vent est en commentaire HTML et vaut `-NC-`.
- La note du jour (« RETOURS : 11 442 pal à Urrugne… ») contient des emojis : UTF-8 partout.
- La page indique une mise à jour « en principe entre 18 h 30 et 19 h 30 ». Planifie la collecte quotidienne à **20 h 30 heure de Paris**, avec une seconde tentative à 22 h, en convertissant en UTC selon l'heure d'été ou d'hiver.
- Pour `VERIFICATION.md`, choisis au moins une date avec des nombres à 4 chiffres et des retours non nuls (par exemple le 27/10/2026), pour prouver que séparateurs et `span.little` sont bien gérés.
- Ces postes sont **en aval** des Landes (cols basques) : c'est un signal de confirmation, pas d'arrivée. Indique-le dans `latest.json` (`"role": "aval"`).

**2. Trektellen** : le 30/10/2026, `site/totals/…` renvoyait une page de vérification anti-robots Cloudflare (« Just a moment… Enable JavaScript and cookies »). Son `robots.txt` interdit `ClaudeBot` et `anthropic-ai` et déclare `ai-train=no`. L'accord du 13/11 autorise l'**usage des données**, pas le contournement de cette protection. **Ne fais pas passer le défi Cloudflare par Playwright.** Demande d'abord à Trektellen (Gerard Troost) un export CSV ou JSON, ou une autorisation du User-Agent du collecteur. En attendant, désactive la source (`TREKTELLEN_ENABLED=false`) et note-le dans « non vérifié ». Le reverse engineering sert seulement aux pages qui s'ouvrent normalement.

**3. Flash palombe.com : vie privée.** Les signalements portent un pseudo et une position. Dans `latest.json` (public) :
- **aucun pseudo** ;
- position arrondie à 0,1° (environ 10 km) ou ramenée à la commune ;
- ne stocke pas les pseudos en base non plus.

C'est la règle du site : jamais de position précise de poste en public (voir [04-legal-securite.md](04-legal-securite.md)).

**4. Persistance de la base avec GitHub Actions** : le runner est effacé après chaque exécution, donc `data/migration.db` disparaîtrait. Au début de chaque run, télécharge la base depuis OVH (SFTP) ; à la fin, renvoie-la avec `latest.json`. Ajoute `concurrency: { group: collect, cancel-in-progress: false }` pour que deux runs n'écrivent jamais en même temps. Garde une sauvegarde quotidienne datée (`backups/migration-AAAA-MM-JJ.db`, 30 jours).

**5. Limites de GitHub Actions à connaître** :
- un cron planifié peut être retardé, voire sauté, quand GitHub est chargé : ne promets pas « toutes les 15 min pile » ;
- sur un dépôt **public**, les workflows planifiés sont désactivés après 60 jours sans activité sur le dépôt ;
- sur un dépôt **privé**, 2 000 minutes gratuites par mois, chaque run étant arrondi à la minute supérieure. 96 runs par jour en octobre font environ 3 000 minutes : ça dépasse le quota. Choisis le dépôt public, ou un cron à 30 min, ou le cron à 15 min seulement de 6 h à 20 h. **Demande-moi lequel.**

**6. Alertes intelligentes** :
- « zéro ligne en pleine saison » ne vaut que pendant les heures où l'on en attend : Flash de 7 h à 18 h, du 1er octobre au 20 novembre ; comptages du 15 octobre au 15 novembre.
- « format changé » : contrôle l'en-tête du tableau (les 4 postes, `Nb`/`Vol`) et la présence de `span.little`.
- Une seule issue GitHub ouverte par incident, fermée automatiquement au retour à la normale.

**7. Autorisations** : le dossier `docs/autorisations/` du projet principal ne contient pas encore les mails d'accord. Ne mets pas `PALOMBE_COM_ENABLED` ni `TREKTELLEN_ENABLED` à `true` en production tant que les mails n'y sont pas. Ajoute un test de CI qui échoue si une source activée n'a pas de fichier d'accord correspondant.

**8. Coordonnées** : -1.45 signifie 1,45° **Ouest**. Garde -1.45 dans le code (convention : longitude négative à l'ouest).

**9. Lien avec le site** : le champ « Dernier signal en amont » de l'accueil lira dans `latest.json` le dernier Flash au nord des secteurs (latitude supérieure à 43,72), avec son heure. Les comptages des cols alimentent le bloc « Ce qui s'est passé hier en aval ». Expose ces deux blocs tels quels, sans les réinterpréter.
