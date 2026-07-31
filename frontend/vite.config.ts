import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Builds to app/static/dist/ with a fixed filename (no content hash / manifest) -- matches
// this repo's existing convention of every other static asset being referenced by a plain
// hardcoded filename in Jinja templates (see app/templates/base.html). Library mode with a
// single ES module output is the simplest way to get one predictable <script type="module">
// entry point without needing an index.html to drive the build (this bundle mounts itself into
// #player-root on load, it isn't a standalone page).
export default defineConfig({
  plugins: [react()],
  // Standard `vite build` (app mode) replaces process.env.NODE_ENV automatically; library mode
  // doesn't apply that default the same way, and React itself (plus several dependencies)
  // reads it at runtime for dev-only warnings -- without this, `process` is simply undefined
  // in the browser and the whole app throws on load before ever rendering.
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    outDir: "../app/static/dist",
    emptyOutDir: true,
    lib: {
      entry: "src/main.tsx",
      formats: ["es"],
      fileName: () => "player-dashboard.js",
    },
    rollupOptions: {
      output: {
        // Everything (including Monaco's worker chunk) still gets fixed, predictable names --
        // avoids needing a manifest.json lookup in the Flask template for this first pilot.
        chunkFileNames: "[name].js",
        assetFileNames: "[name].[ext]",
      },
    },
  },
});
