import React from "react";
import { createRoot } from "react-dom/client";
import { AutoEditPage } from "./pages/AutoEditPage";
import "./styles/autoedit.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AutoEditPage />
  </React.StrictMode>
);
