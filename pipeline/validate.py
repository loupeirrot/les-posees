"""Valide public/latest.json contre schema.json ; code de sortie 1 si invalide."""
import json
import sys

from jsonschema import Draft202012Validator

from common import ROOT

schema = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))
data = json.loads((ROOT / "public" / "latest.json").read_text(encoding="utf-8"))
errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
for e in errors[:20]:
    print("ERREUR", "/".join(map(str, e.path)), ":", e.message)
print("latest.json valide" if not errors else f"{len(errors)} erreur(s)")
sys.exit(1 if errors else 0)
