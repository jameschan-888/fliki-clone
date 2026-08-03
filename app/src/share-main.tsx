import React from "react";
import { createRoot } from "react-dom/client";
import { SharePage } from "./pages/SharePage";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(<React.StrictMode><SharePage /></React.StrictMode>);
