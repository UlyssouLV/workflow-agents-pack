import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./index.css";
import "./style.css";

createRoot(document.getElementById("racine")!).render(
  <StrictMode>
    <App chemin={window.location.pathname} />
  </StrictMode>,
);
