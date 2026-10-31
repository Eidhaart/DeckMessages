import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

// Keep the app sized to the area above the on-screen keyboard, and undo the browser's
// attempt to scroll the whole page up to reveal the input.
const vv = window.visualViewport;
if (vv) {
  const fit = () => {
    document.documentElement.style.setProperty("--app-h", `${vv.height}px`);
    window.scrollTo(0, 0);
  };
  vv.addEventListener("resize", fit);
  vv.addEventListener("scroll", () => window.scrollTo(0, 0));
  fit();
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
