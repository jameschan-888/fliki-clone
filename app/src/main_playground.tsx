import React from "react";
import { createRoot } from "react-dom/client";
import { PlaygroundPage } from "./pages/PlaygroundPage";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PlaygroundPage />
  </React.StrictMode>
);
