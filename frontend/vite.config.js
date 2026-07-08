import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During `npm run dev`, proxy /api to the FastAPI backend so the frontend can
// call it same-origin. In production the backend serves the built dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8765",
    },
  },
});
