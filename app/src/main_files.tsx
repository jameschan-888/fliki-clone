import React from "react";
import { createRoot } from "react-dom/client";
import { FilesPage } from "./pages/FilesPage";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <FilesPage />
  </React.StrictMode>
);
