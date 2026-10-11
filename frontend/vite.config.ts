import { defineConfig } from "vite";

// Dev: `npm run dev` proxies /api to the FastAPI server (python -m registry serve).
// REGISTRY_API is set by ../run.sh --dev when the backend runs on a non-default host/port.
const api = process.env.REGISTRY_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  server: {
    port: 5173,
    proxy: { "/api": { target: api, changeOrigin: true } },
  },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 900 },
});
