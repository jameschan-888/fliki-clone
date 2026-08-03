import React from "react";
import { createRoot } from "react-dom/client";
import { WorkflowPage } from "./pages/WorkflowPage";
import "./styles/app.css";

const PLACEHOLDER = String.raw`[{"title":"封面","content":"..."},{"title":"正文","content":"..."}]`;

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WorkflowPage endpoint={"/workflow-ppt"} title={"PPT to Video - 幻灯片转视频"} inputLabel={"输入 JSON 格式 slides: [{title, content}]"} inputField={"slides"} inputPlaceholder={PLACEHOLDER} />
  </React.StrictMode>
);
