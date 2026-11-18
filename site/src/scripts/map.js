// Carte MapLibre, importée seulement quand on clique sur « Afficher la carte ».
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export async function showMap(data) {
  const box = document.getElementById("map-box");
  box.hidden = false;
  const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
  const map = new maplibregl.Map({
    container: "map",
    style: `https://tiles.openfreemap.org/styles/${dark ? "dark" : "positron"}`,
    center: [-1.2, 43.75],
    zoom: 7,
    attributionControl: { compact: true },
    cooperativeGestures: true,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  await new Promise((resolve) => map.on("load", resolve));

  map.addSource("flash", {
    type: "geojson",
    data: { type: "FeatureCollection", features: data.flash.map((p) => ({ type: "Feature", properties: p, geometry: { type: "Point", coordinates: [p.lon, p.lat] } })) },
  });
  map.addLayer({
    id: "flash", type: "circle", source: "flash",
    paint: {
      "circle-radius": 7,
      "circle-color": ["case", ["==", ["get", "direction"], "recul"], css("--accent") || "#9a4f0c", css("--good") || "#146b3e"],
      "circle-opacity": 0.75, "circle-stroke-width": 1.5, "circle-stroke-color": "#ffffff",
    },
  });

  // les 4 secteurs sont à moins de 15 km les uns des autres : des points, et une seule étiquette avec le vent
  map.addSource("sectors", {
    type: "geojson",
    data: { type: "FeatureCollection", features: data.sectors.map((s) => ({ type: "Feature", properties: { name: s.name }, geometry: { type: "Point", coordinates: [s.lon, s.lat] } })) },
  });
  map.addLayer({ id: "sectors", type: "circle", source: "sectors", paint: { "circle-radius": 5, "circle-color": "#21402e", "circle-stroke-width": 2, "circle-stroke-color": "#f9f9f5" } });
  const today = Object.keys(data.wind.seignosse || {})[0];
  const dir = data.wind.seignosse?.[today];
  const el = document.createElement("div");
  el.style.cssText = "display:flex;align-items:center;gap:6px;font:700 13px/1.1 var(--f-body);color:#121a16;background:#f9f9f5;border:1px solid #21402e;border-radius:12px;padding:5px 9px";
  el.innerHTML = (dir === null || dir === undefined ? "" :
    `<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><g transform="rotate(${(dir + 180) % 360} 12 12)"><path d="M12 3v16M6 9l6-6 6 6" fill="none" stroke="#21402e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></g></svg>`) + "Labenne – Seignosse";
  new maplibregl.Marker({ element: el, anchor: "right", offset: [-10, 0] }).setLngLat([-1.46, 43.65]).addTo(map);

  map.on("click", "flash", (e) => {
    const p = e.features[0].properties;
    const t = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" }).format(new Date(p.time)).replace(":", " h ");
    new maplibregl.Popup({ closeButton: false }).setLngLat(e.lngLat)
      .setHTML(`<b>${p.direction === "recul" ? "Recul" : "Aller"}</b> à ${t}${p.size && p.size !== "null" ? `, ${p.size} palombes` : ""}`).addTo(map);
  });
}
