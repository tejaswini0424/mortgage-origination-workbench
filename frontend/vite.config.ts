import { defineConfig } from "vite";
const backend = process.env.MORTGAGE_API_TARGET ?? "http://127.0.0.1:8000";
export default defineConfig({
  server: {
    proxy: { "/api": backend, "/docs": backend, "/openapi.json": backend },
  },
});
