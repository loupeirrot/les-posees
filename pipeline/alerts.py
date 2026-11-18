"""Alertes : une issue GitHub par source en panne pendant sa saison, fermée automatiquement au retour à la normale.

En panne : erreur, page modifiée, bloquée, coupée ; ou Flash vide entre 7 h et 18 h en pleine saison.
Sans GITHUB_TOKEN (exécution locale), affiche seulement ce qui serait signalé.
"""
import json
import os

import requests

from common import ROOT, paris_now

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY")
TOKEN = os.environ.get("GITHUB_TOKEN")
LABEL = "alerte-source"
H = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"} if TOKEN else {}


def problems(latest):
    hour = paris_now().hour
    out = {}
    for s in latest["sources"]:
        if not s["in_season"]:
            continue
        bad = s["status"] in ("erreur", "format", "bloquée", "coupée")
        empty_flash = s["id"] == "palombe_flash" and s["status"] == "vide" and 7 <= hour < 18
        if bad or empty_flash:
            out[s["id"]] = s
    return out


def main():
    latest = json.loads((ROOT / "public" / "latest.json").read_text(encoding="utf-8"))
    probs = problems(latest)
    for k, s in probs.items():
        print(f"ALERTE {k} : {s['status']} {s.get('message') or ''}")
    if not (TOKEN and REPO):
        return
    issues = requests.get(f"{API}/repos/{REPO}/issues", headers=H, params={"labels": LABEL, "state": "open", "per_page": 100}, timeout=30).json()
    open_by_src = {i["title"].split("]")[0].strip("["): i for i in issues if i["title"].startswith("[")}
    for k, s in probs.items():
        body = (f"La source **{s['label']}** ({s['owner']}) est en état **{s['status']}** pendant sa saison.\n\n"
                f"- Message : {s.get('message') or '—'}\n- Dernier essai : {s.get('checked_at')}\n- Dernière réussite : {s.get('last_ok_at') or 'jamais'}\n"
                f"- Page : {s['url']}\n\nCette issue se ferme seule quand la source redevient normale.")
        if k not in open_by_src:  # une seule issue ouverte par source
            requests.post(f"{API}/repos/{REPO}/issues", headers=H, json={"title": f"[{k}] source en panne : {s['status']}", "body": body, "labels": [LABEL]}, timeout=30)
    for k, issue in open_by_src.items():
        if k not in probs:
            requests.post(f"{API}/repos/{REPO}/issues/{issue['number']}/comments", headers=H, json={"body": "La source est revenue à la normale."}, timeout=30)
            requests.patch(f"{API}/repos/{REPO}/issues/{issue['number']}", headers=H, json={"state": "closed"}, timeout=30)


if __name__ == "__main__":
    main()
