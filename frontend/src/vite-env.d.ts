/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Base URL of the Flask API on Railway, e.g. "https://web-production-188c4.up.railway.app".
  // Empty/unset falls back to relative paths (same-origin), matching pre-Vercel-split behavior.
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
