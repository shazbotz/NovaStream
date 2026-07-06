import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Deployed as a static bundle to a CDN/static host, separate from the
// bot/API instance - see README.md and
// docs/design-log/architecture-design-phase1.md §4.4.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
