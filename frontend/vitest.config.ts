import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Deliberately separate from vite.config.ts, not merged into it: that file is tuned for
// library-mode production output (fixed filenames, no manifest, process.env.NODE_ENV hardcoded
// to "production" since React reads it at runtime) -- assumptions a test run shouldn't inherit.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    globals: true,
  },
});
