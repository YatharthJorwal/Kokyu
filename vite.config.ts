import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Tauri expects a fixed dev server port (matches src-tauri/tauri.conf.json's
// build.devUrl) and needs HMR to ignore its own Rust source tree.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      // Only src/ and the pages matter. .venv alone is ~8,000 files, and the kernel
      // writes to data/ and logs/ all the time (D-060).
      ignored: ["**/src-tauri/**", "**/KASANE/**", "**/.venv/**", "**/data/**", "**/logs/**", "**/assets/**", "**/docs/**", "**/dist/**"],
    },
  },
});
