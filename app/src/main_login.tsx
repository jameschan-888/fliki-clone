import React from "react";
import { createRoot } from "react-dom/client";
import { LoginPage } from "./pages/LoginPage";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LoginPage />
  </React.StrictMode>
);
