import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// Dev: Vite on :3000 proxies API/WS/media to the FastAPI backend on :8000,
// so frontend code never needs to know where the backend lives.
// Prod: FastAPI serves the built `dist/` on :3000 directly (no proxy needed).
const BACKEND = process.env.API_BASE || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: Number(process.env.PORT || 3000),
    strictPort: true,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/media": { target: BACKEND, changeOrigin: true },
      "/ws": { target: BACKEND.replace("http", "ws"), ws: true, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
  },
});
