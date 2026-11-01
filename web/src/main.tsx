import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { OverlayPage, overlayFromUrl } from "./ui/Overlay";
import "./styles/tokens.css";
import "./styles/app.css";

// `?overlay=1` is the OBS Browser Source: its own page, no landing, no dashboard, no history
const overlay = overlayFromUrl();

createRoot(document.getElementById("root")!).render(
  <StrictMode>{overlay ? <OverlayPage route={overlay} /> : <App />}</StrictMode>,
);
