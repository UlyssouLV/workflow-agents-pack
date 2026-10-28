import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": decodeURIComponent(new URL("./src", import.meta.url).pathname) } },
  // `npm run dev` : l’API vient d’un `wap-runtime serve` local.
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8787", ws: true }, "/health": "http://127.0.0.1:8787" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    env: { TZ: "UTC" },
    // `npm run test:coverage` (CI) : lcov dans coverage/ pour l’artefact et Sonar ; chemins `src/…`,
    // préfixés en `orchestrator/cockpit/src/…` par le job `sonar` de .github/workflows/ci.yml.
    coverage: { provider: "v8", include: ["src/**"], reporter: ["text", "lcov"], reportOnFailure: true },
  },
});
