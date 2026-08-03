import React from "react";
import { createRoot } from "react-dom/client";
import { CookiesPage } from "./pages/MarketingFooterPages";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><CookiesPage /></React.StrictMode>);
