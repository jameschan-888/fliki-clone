import React from "react";
import { createRoot } from "react-dom/client";
import { WorkflowPage } from "./pages/WorkflowPage";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WorkflowPage endpoint={"/workflow-translate"} title={"Translate Video - 翻译视频"} inputLabel={"粘贴待翻译文本"} inputField={"source"} mode={"translate"} inputPlaceholder={"粘贴视频源文本..."} />
  </React.StrictMode>
);
