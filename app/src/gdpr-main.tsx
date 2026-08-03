import React from "react";
import { createRoot } from "react-dom/client";
import { GdprPage } from "./pages/MarketingFooterPages";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><GdprPage /></React.StrictMode>);
