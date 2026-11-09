import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The target is server configuration, never a browser-supplied host/credential.
const target = process.env.INDEXPILOT_API_TARGET ?? "http://127.0.0.1:8000";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(
      ["/api", "/health", "/docs", "/openapi.json"].map((path) => [
        path,
        { target },
      ]),
    ),
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
    proxy: Object.fromEntries(
      ["/api", "/health", "/docs", "/openapi.json"].map((path) => [
        path,
        { target },
      ]),
    ),
  },
});
