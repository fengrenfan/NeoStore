import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * The console is served from `/admin/`. Caddy forwards that prefix to the admin
 * container *without* stripping it (see the root `Caddyfile`), and nginx serves
 * the build from `/admin/` to match — so a single `base` here is what keeps the
 * bundled asset URLs, the dev server and production in step. The router carries
 * the same prefix as its basename (see `src/main.tsx`).
 */
export default defineConfig({
  base: "/admin/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // In dev the API runs separately; in production Caddy owns this prefix.
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    // `preview` does not inherit `server.proxy`, so the built console is only
    // usable over the API if this is repeated here.
    port: 4173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
