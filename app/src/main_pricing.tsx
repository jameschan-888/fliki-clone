import React from "react";
import { createRoot } from "react-dom/client";
import { PricingPage } from "./pages/PricingPage";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PricingPage />
  </React.StrictMode>
);
