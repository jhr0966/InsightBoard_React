import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// FastAPI(api/) 를 /api 로 프록시 — dev 에서 CORS 없이 동일 출처처럼 호출.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
