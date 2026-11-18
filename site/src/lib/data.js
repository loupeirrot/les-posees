// Données produites par le pipeline (pipeline/build_json.py) et aides d'affichage.
import latest from "../data/latest.json";
import archives from "../data/archives.json";

export { latest, archives };

export const BASE = import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : import.meta.env.BASE_URL + "/";
export const url = (path = "") => BASE + path.replace(/^\//, "");

export const SECTOR_KEYS = ["labenne", "capbreton", "hossegor", "seignosse"];
export const DEFAULT_SECTOR = "seignosse";
export const CATEGORIES = { palombe: "Palombe", grives: "Grives" };

const TZ = "Europe/Paris";
const atNoon = (iso) => new Date(iso + "T12:00:00Z");

export const frDay = (iso) => new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(atNoon(iso));
export const frDate = (iso) => new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(atNoon(iso));
export const frTime = (isoUtc) => new Intl.DateTimeFormat("fr-FR", { hour: "numeric", minute: "2-digit", timeZone: TZ }).format(new Date(isoUtc)).replace(":", " h ");
export const frDateTime = (isoUtc) =>
  new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", hour: "numeric", minute: "2-digit", timeZone: TZ }).format(new Date(isoUtc)).replace(":", " h ");
export const nf = (n) => (n === null || n === undefined ? "–" : new Intl.NumberFormat("fr-FR").format(n));

export const days = () => {
  const t = latest.today;
  const d = new Date(t + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + 1);
  return [t, d.toISOString().slice(0, 10)];
};

// Avant midi (heure de Paris) on montre « ce matin », après midi « demain matin ».
export const defaultDayIndex = () => {
  const h = +new Intl.DateTimeFormat("fr-FR", { hour: "numeric", hour12: false, timeZone: TZ }).format(new Date(latest.generated_at));
  return h >= 12 ? 1 : 0;
};

export const source = (id) => latest.sources.find((s) => s.id === id);
export const STATUS_WORDS = { ok: "à jour", vide: "rien de nouveau", erreur: "en erreur", "bloquée": "bloquée", format: "page modifiée", "coupée": "coupée", jamais: "pas encore lue" };

export const DEPARTEMENTS = {
  "09": "Ariège", 11: "Aude", 16: "Charente", 17: "Charente-Maritime", 19: "Corrèze", 24: "Dordogne", 31: "Haute-Garonne",
  32: "Gers", 33: "Gironde", 40: "Landes", 46: "Lot", 47: "Lot-et-Garonne", 64: "Pyrénées-Atlantiques", 65: "Hautes-Pyrénées",
  81: "Tarn", 82: "Tarn-et-Garonne", 87: "Haute-Vienne", 34: "Hérault", 30: "Gard", 13: "Bouches-du-Rhône", 83: "Var",
  84: "Vaucluse", "04": "Alpes-de-Haute-Provence", "06": "Alpes-Maritimes", 12: "Aveyron", 66: "Pyrénées-Orientales",
};
export const deptName = (d) => DEPARTEMENTS[d] || DEPARTEMENTS[+d] || `Département ${d}`;
