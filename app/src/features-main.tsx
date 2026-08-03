import React from "react";
import { createRoot } from "react-dom/client";
import { FeaturesPage } from "./pages/CatalogPages";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><FeaturesPage /></React.StrictMode>);
