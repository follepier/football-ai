import { defineConfig } from "vite";

export default defineConfig({
  server: {
    allowedHosts: [".app.github.dev"],
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
