import { archives, url, SECTOR_KEYS } from "../lib/data.js";

export function GET({ site }) {
  const paths = [
    "", "secteurs/", "especes/palombe/", "especes/grives/", "guides/lire-le-vent/", "methode/", "etat/", "archives/", "mentions-legales/",
    ...SECTOR_KEYS.flatMap((k) => [`passage-du-jour/${k}/`, `secteurs/${k}/`]),
    ...archives.map((a) => `archives/${a.date}/`),
  ];
  const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${paths
    .map((p) => `  <url><loc>${new URL(url(p), site).href}</loc></url>`)
    .join("\n")}\n</urlset>\n`;
  return new Response(body, { headers: { "Content-Type": "application/xml" } });
}
