import { url } from "../lib/data.js";

export function GET() {
  const manifest = {
    name: "Les posées : passage des palombes et des grives",
    short_name: "Les posées",
    lang: "fr",
    start_url: url(""),
    scope: url(""),
    display: "standalone",
    background_color: "#0c1210",
    theme_color: "#21402e",
    icons: [
      { src: url("icons/icon-192.png"), sizes: "192x192", type: "image/png" },
      { src: url("icons/icon-512.png"), sizes: "512x512", type: "image/png" },
      { src: url("icons/icon-512-maskable.png"), sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
  return new Response(JSON.stringify(manifest), { headers: { "Content-Type": "application/manifest+json" } });
}
