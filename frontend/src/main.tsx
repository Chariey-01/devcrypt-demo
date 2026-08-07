import "./monacoSetup";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

const container = document.getElementById("player-root");
if (!container) {
  throw new Error("#player-root not found -- frontend/index.html must include it.");
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>
);
