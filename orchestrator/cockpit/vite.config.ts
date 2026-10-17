import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // `npm run dev` : l’API vient d’un `wap-runtime serve` local.
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8787", ws: true }, "/health": "http://127.0.0.1:8787" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    env: { TZ: "UTC" },
  },
});
