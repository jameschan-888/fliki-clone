import React from "react";
import { createRoot } from "react-dom/client";
import { WorkflowPage } from "./pages/WorkflowPage";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WorkflowPage endpoint={"/workflow-record"} title={"Record to Video - 录屏转视频"} inputLabel={"录屏/录音后粘贴 transcript"} inputField={"transcript"} mode={"record"} inputPlaceholder={"粘贴录屏转写文本..."} />
  </React.StrictMode>
);
