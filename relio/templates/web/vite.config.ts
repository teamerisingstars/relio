/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: Vite serves the UI and proxies /api to the FastAPI backend on :8000,
// so the whole app is reachable at a single URL. Prod: `vite build` emits
// static assets that the backend serves itself (one port, one deploy).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    globals: true,
    environment: "node",
  },
});
