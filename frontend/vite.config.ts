import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Standalone app now, hosted on Vercel (see frontend/vercel.json) -- no longer library mode
// embedded inside a Flask-rendered Jinja shell (app/templates/player/dashboard.html, deleted).
// Standard `vite build` gives content-hashed assets and drives from index.html directly; Vercel
// serves the output as-is. This also means Vite's default process.env.NODE_ENV replacement
// applies automatically -- library mode needed a manual `define` for that, app mode doesn't.
export default defineConfig({
  plugins: [react()],
});
