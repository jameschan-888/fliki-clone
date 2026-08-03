import React from "react";
import { createRoot } from "react-dom/client";
import { WorkflowPage } from "./pages/WorkflowPage";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WorkflowPage endpoint={"/workflow-record"} title={"Record to Video - 录屏转视频"} inputLabel={"粘贴 ASR 转写后的 transcript"} inputField={"transcript"} inputPlaceholder={"粘贴录屏转写文本..."} />
  </React.StrictMode>
);
