import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    setupFiles: ["./src/test/setup.ts"],
  },
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true, ws: true },
      "/docs": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
