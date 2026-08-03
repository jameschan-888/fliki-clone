import React from "react";
import { createRoot } from "react-dom/client";
import { TermsPage } from "./pages/MarketingFooterPages";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><TermsPage /></React.StrictMode>);
