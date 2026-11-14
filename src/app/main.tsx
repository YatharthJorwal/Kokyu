import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { actions } from "./store";
import "./app.css";

const root = document.getElementById("root");
if (!root) throw new Error("index.html must contain #root");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Outside React so StrictMode's double effects never open two sockets.
actions.connect();
