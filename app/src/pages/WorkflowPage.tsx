import { useState } from "react";
import { Footer } from "../components/layout/Footer";
import { API } from "../api/drafts";
import { ensureSession } from "../api/auth";

export type WorkflowPageProps = {
  endpoint: string;
  title: string;
  inputLabel: string;
  inputField: string;
  inputPlaceholder: string;
};

export function WorkflowPage(props: WorkflowPageProps) {
  const [title, setTitle] = useState("未命名视频");
  const [language, setLanguage] = useState("zh-CN");
  const [inputText, setInputText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [sceneCount, setSceneCount] = useState<number | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!inputText.trim()) {
      setError(props.inputLabel + " 不能为空");
      return;
    }
    setBusy(true);
    try {
      await ensureSession();
      const token = localStorage.getItem("fliki-auth-token") || "";
      const body: Record<string, unknown> = { title, language };
      if (props.inputField === "slides") {
        try {
          body.slides = JSON.parse(inputText);
        } catch {
          throw new Error("slides 必须是合法 JSON 数组 [{title, content}]");
        }
      } else {
        body[props.inputField] = inputText;
      }
      const r = await fetch(API + props.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const errBody = await r.json().catch(() => ({}));
        throw new Error(errBody.message || errBody.detail || ("HTTP " + r.status));
      }
      const draft = await r.json();
      setDraftId(draft.id);
      setSceneCount((draft.scenes || []).length);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
    <div className="workflow-page">
      <nav style={{ padding: "12px 24px", borderBottom: "1px solid #eee" }}>
        <a href="/index.html" style={{ marginRight: 16 }}>首页</a>
        <a href="/drafts.html" style={{ marginRight: 16 }}>Script to Video</a>
        <a href="/blog.html" style={{ marginRight: 16 }}>Blog to Video</a>
        <a href="/ppt.html" style={{ marginRight: 16 }}>PPT to Video</a>
        <a href="/record.html" style={{ marginRight: 16 }}>Record to Video</a>
        <a href="/translate.html" style={{ marginRight: 16 }}>Translate Video</a>
        <a href="/autoedit.html" style={{ marginRight: 16 }}>Auto-edit</a>
        <a href="/voices.html" style={{ marginRight: 16 }}>声音库</a>
        <a href="/templates.html" style={{ marginRight: 16 }}>模板</a>
      </nav>
      <div style={{ maxWidth: 720, margin: "32px auto", padding: "0 24px" }}>
        <h1>{props.title}</h1>
        <p style={{ color: "#666" }}>{props.inputLabel}</p>
        <form onSubmit={submit}>
          <div style={{ marginBottom: 12 }}>
            <label>标题<br /><input type="text" value={title} onChange={(e) => setTitle(e.target.value)} style={{ width: "100%", padding: 8 }} /></label>
          </div>
          <div style={{ marginBottom: 12 }}>
            <label>语言<br /><input type="text" value={language} onChange={(e) => setLanguage(e.target.value)} style={{ width: 200, padding: 8 }} /></label>
          </div>
          <div style={{ marginBottom: 12 }}>
            <label>{props.inputLabel}<br />
              <textarea value={inputText} onChange={(e) => setInputText(e.target.value)} placeholder={props.inputPlaceholder} rows={12} style={{ width: "100%", padding: 8, fontFamily: props.inputField === "slides" ? "monospace" : "inherit" }} />
            </label>
          </div>
          <button type="submit" disabled={busy} style={{ padding: "8px 24px", background: busy ? "#ccc" : "#2c7be5", color: "#fff", border: "none", borderRadius: 4, cursor: busy ? "wait" : "pointer" }}>
            {busy ? "生成中..." : "生成草稿"}
          </button>
        </form>
        {error && <div style={{ marginTop: 16, padding: 12, background: "#fee", color: "#c00", borderRadius: 4 }}>错误: {error}</div>}
        {draftId && (
          <div style={{ marginTop: 16, padding: 12, background: "#efe", color: "#080", borderRadius: 4 }}>
            <div>草稿 ID: <code>{draftId}</code></div>
            <div>已生成 {sceneCount} 个 scene</div>
            <div style={{ marginTop: 8 }}>前往 <a href={"/drafts.html?draft=" + draftId}>Composer</a> 编辑并确认。</div>
          </div>
        )}
      </div>
    </div>
      <Footer />
    </>
  );
}
