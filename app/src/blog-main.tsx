import React from "react";
import { createRoot } from "react-dom/client";
import { WorkflowPage } from "./pages/WorkflowPage";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WorkflowPage endpoint={"/workflow-blog"} title={"Blog to Video - 博客转视频"} inputLabel={"粘贴文章文本 (URL fetch 后续 P1)"} inputField={"source"} inputPlaceholder={"粘贴博客全文..."} />
  </React.StrictMode>
);
