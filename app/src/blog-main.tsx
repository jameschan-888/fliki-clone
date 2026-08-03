import React from "react";
import { createRoot } from "react-dom/client";
import { WorkflowPage } from "./pages/WorkflowPage";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WorkflowPage endpoint={"/workflow-blog"} title={"Blog to Video - 博客转视频"} inputLabel={"输入文章 URL"} inputField={"url"} mode={"url"} inputPlaceholder={"https://example.com/article"} />
  </React.StrictMode>
);
