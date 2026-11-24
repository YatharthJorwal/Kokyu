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
    // Vite serves the repo root: keep the user's data, config, the premade packs and the
    // kernel's source from being fetched off the dev server (the audit). Vite's own
    // defaults first, since this list replaces them.
    fs: {
      deny: [".env", ".env.*", "*.{crt,pem}", "**/data/**", "**/logs/**", "**/config/*.yaml", "**/assets/**", "**/KASANE/**"],
    },
    watch: {
      // Only src/ and the pages matter. .venv alone is ~8,000 files, and the kernel
      // writes to data/ and logs/ all the time (D-060).
      ignored: ["**/src-tauri/**", "**/KASANE/**", "**/.venv/**", "**/data/**", "**/logs/**", "**/assets/**", "**/docs/**", "**/dist/**"],
    },
  },
});
