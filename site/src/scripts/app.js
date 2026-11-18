// Comportements côté navigateur : choix mémorisés, mode aube, hors ligne, nouvelle prévision, carte à la demande.
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
};
const base = document.body.dataset.base || "/";
const root = document.documentElement;

// --- mode aube ---
const themeBtn = document.getElementById("theme");
const isDark = () => (root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches);
const syncTheme = () => {
  themeBtn?.setAttribute("aria-pressed", String(isDark()));
  themeBtn?.setAttribute("aria-label", isDark() ? "Mode jour" : "Mode aube");
};
themeBtn?.addEventListener("click", () => {
  root.dataset.theme = isDark() ? "light" : "dark";
  store.set("theme", root.dataset.theme);
  syncTheme();
});
syncTheme();

// --- choix gibier / secteur / jour ---
const fcs = document.getElementById("forecasts");
if (fcs) {
  const state = {
    sector: fcs.dataset.defaultSector,
    cat: store.get("cat") || "palombe",
    day: document.querySelector("#pick-day [aria-pressed='true']")?.dataset.day,
  };
  // sur la page d'accueil, on reprend le secteur favori
  if (location.pathname === base && store.get("sector")) state.sector = store.get("sector");
  const render = () => {
    document.querySelectorAll("[data-fc]").forEach((el) => {
      el.hidden = !(el.dataset.sector === state.sector && el.dataset.cat === state.cat && el.dataset.day === state.day);
    });
    document.querySelectorAll("#pick-cat [data-cat]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.cat === state.cat)));
    document.querySelectorAll("#pick-day [data-day]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.day === state.day)));
    document.querySelectorAll("#pick-sector [data-sector]").forEach((a) => {
      if (a.dataset.sector === state.sector) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
  };
  document.getElementById("pick-cat")?.addEventListener("click", (e) => {
    const b = e.target.closest("[data-cat]");
    if (!b) return;
    state.cat = b.dataset.cat;
    store.set("cat", state.cat);
    render();
  });
  document.getElementById("pick-day")?.addEventListener("click", (e) => {
    const b = e.target.closest("[data-day]");
    if (!b) return;
    state.day = b.dataset.day;
    render();
  });
  document.getElementById("pick-sector")?.addEventListener("click", (e) => {
    const a = e.target.closest("[data-sector]");
    if (!a || e.metaKey || e.ctrlKey) return;
    e.preventDefault();
    state.sector = a.dataset.sector;
    store.set("sector", state.sector);
    render();
  });
  render();
}

// --- réseau et fraîcheur ---
const banner = document.getElementById("net-banner");
const showBanner = (html) => { if (banner) { banner.innerHTML = html; banner.hidden = false; } };
const generated = document.body.dataset.generated;
const fmt = (iso) => new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" }).format(new Date(iso)).replace(":", " h ");
const offline = () => showBanner(`Hors ligne : prévision enregistrée du ${fmt(generated)}.`);
addEventListener("offline", offline);
if (!navigator.onLine) offline();
if (Date.now() - new Date(generated).getTime() > 45 * 60 * 1000 && navigator.onLine) {
  showBanner(`Données du ${fmt(generated)} : la mise à jour automatique est en retard.`);
}
fetch(base + "data/latest.json", { cache: "no-store" })
  .then((r) => (r.ok ? r.json() : null))
  .then((d) => {
    if (d && d.generated_at > generated) {
      showBanner(`Nouvelle prévision disponible (${fmt(d.generated_at)}). <button type="button" id="reload">Actualiser</button>`);
      document.getElementById("reload")?.addEventListener("click", () => location.reload());
    }
  })
  .catch(() => {});

// --- hors ligne : service worker ---
if ("serviceWorker" in navigator && location.protocol === "https:") {
  navigator.serviceWorker.register(base + "sw.js", { scope: base }).catch(() => {});
}

// --- carte à la demande ---
const mapBtn = document.getElementById("map-load");
mapBtn?.addEventListener("click", async () => {
  mapBtn.disabled = true;
  mapBtn.textContent = "Chargement de la carte…";
  try {
    const { showMap } = await import("./map.js");
    await showMap(JSON.parse(document.getElementById("map-data").textContent));
    mapBtn.hidden = true;
  } catch {
    mapBtn.disabled = false;
    mapBtn.textContent = "Carte indisponible, réessayer";
  }
});
