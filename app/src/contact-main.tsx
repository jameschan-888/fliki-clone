import React from "react";
import { createRoot } from "react-dom/client";
import { ContactPage } from "./pages/MarketingFooterPages";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><ContactPage /></React.StrictMode>);
