import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Tauri expects a fixed dev server port (matches src-tauri/tauri.conf.json's
// build.devUrl) and needs HMR to ignore its own Rust source tree.
// Two pages (K1-02): index.html is the React chat window; widget.html is Yuri's
// stage widget, kept reachable until the Stage view replaces it in K2.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      ignored: ["**/src-tauri/**", "**/KASANE/**"],
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, "index.html"),
        widget: resolve(import.meta.dirname, "widget.html"),
      },
    },
  },
});
