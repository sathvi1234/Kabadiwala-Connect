import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon-192.png", "icon-512.png"],
      manifest: {
        name: "Kabadiwala Connect",
        short_name: "Kabadiwala",
        description: "Traceable scrap collection for collectors and authorized recyclers",
        start_url: "/",
        display: "standalone",
        background_color: "#123d31",
        theme_color: "#176b52",
        lang: "en",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "any maskable" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,webmanifest,json}"],
        navigateFallback: "/index.html",
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith("/api/prices") || url.pathname.startsWith("/api/recyclers/nearby"),
            handler: "NetworkFirst",
            options: { cacheName: "kabadi-api", networkTimeoutSeconds: 4 },
          },
        ],
      },
      devOptions: { enabled: true },
    }),
  ],
  envDir: "..",
  server: { port: 5173 },
  preview: { port: 4173 },
});
