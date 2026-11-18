import { defineConfig } from "astro/config";

// SITE_URL et BASE_PATH sont fournis par le workflow GitHub Pages (ex. https://compte.github.io et /depot/).
export default defineConfig({
  site: process.env.SITE_URL || "http://localhost:4321",
  base: process.env.BASE_PATH || "/",
  trailingSlash: "always",
  output: "static",
  build: { inlineStylesheets: "always" },
  compressHTML: true,
});
