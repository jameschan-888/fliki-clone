import React from "react";
import { createRoot } from "react-dom/client";
import { StatusPage } from "./pages/MarketingFooterPages";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><StatusPage /></React.StrictMode>);
