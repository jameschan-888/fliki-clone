import React from "react";
import { createRoot } from "react-dom/client";
import { ChangelogPage } from "./pages/MarketingFooterPages";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><ChangelogPage /></React.StrictMode>);
