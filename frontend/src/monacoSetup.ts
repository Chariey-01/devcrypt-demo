// Configures @monaco-editor/react to use the npm-bundled monaco-editor instead of its default
// CDN fetch (the app's CSP is script-src 'self' with zero exceptions -- a CDN script would be
// blocked outright, and a live event can't depend on a CDN being reachable over venue wifi
// either way). Imported once from main.tsx before anything renders.
import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor";
// Vite's native `?worker` import suffix bundles this as a separate worker chunk -- no extra
// plugin needed. Only the base editor worker is wired up: this app never configures per-
// language IntelliSense/LSP features (monacoLanguageFor just picks a Monarch tokenizer for
// syntax highlighting), so the language-specific workers (typescript/json/css/html) that a
// richer Monaco setup would need are genuinely unused here.
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";

self.MonacoEnvironment = {
  getWorker() {
    return new EditorWorker();
  },
};

loader.config({ monaco });
