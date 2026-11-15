import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { actions } from "./store";
import { THEME_KEY, applyTheme, loadTheme } from "./theme";
import "./app.css";

// The saved look before the first paint (D-073), and again when another window changes it.
applyTheme(loadTheme());
window.addEventListener("storage", (e) => {
  if (e.key === THEME_KEY) applyTheme(loadTheme());
});

const root = document.getElementById("root");
if (!root) throw new Error("index.html must contain #root");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Outside React so StrictMode's double effects never open two sockets.
actions.connect();

// A file dropped anywhere but the composer must not replace the app with that file.
// (Tauri's own drop handler is off in tauri.conf.json, so WebView2 gives the page HTML5 drops.)
for (const type of ["dragover", "drop"]) window.addEventListener(type, (e) => e.preventDefault());
