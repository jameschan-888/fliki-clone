import React from "react";
import { createRoot } from "react-dom/client";
import { BillingPage } from "./pages/BillingPage";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><BillingPage /></React.StrictMode>);
