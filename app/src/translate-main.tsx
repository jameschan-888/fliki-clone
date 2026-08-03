import React from "react";
import { createRoot } from "react-dom/client";
import { WorkflowPage } from "./pages/WorkflowPage";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WorkflowPage endpoint={"/workflow-translate"} title={"Translate Video - 翻译视频"} inputLabel={"粘贴已翻译文本 (后续 P1 接入 ASR+MT)"} inputField={"source"} inputPlaceholder={"粘贴翻译后文本..."} />
  </React.StrictMode>
);
