import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/App";
import { assertLoopbackApiBase, LOCAL_API_ORIGIN } from "@/lib/api";
import "@/index.css";

assertLoopbackApiBase(LOCAL_API_ORIGIN);

const root = document.getElementById("root");
if (root === null) {
  throw new Error("DevPilot could not find the root element.");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
