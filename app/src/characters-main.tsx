import React from "react";
import { createRoot } from "react-dom/client";
import { CharactersPage } from "./pages/CatalogPages";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><CharactersPage /></React.StrictMode>);
