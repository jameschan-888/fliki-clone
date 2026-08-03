import { useRef, useState } from "react";
import { Footer } from "../components/layout/Footer";
import { API } from "../api/drafts";
import { ensureSession } from "../api/auth";

export type WorkflowPageProps = {
  endpoint: string;
  title: string;
  inputLabel: string;
  inputField: string;
  inputPlaceholder: string;
  mode?: "text" | "slides" | "url" | "record" | "translate";
};

export function WorkflowPage(props: WorkflowPageProps) {
  const mode = props.mode || (props.inputField === "slides" ? "slides" : "text");
  const [title, setTitle] = useState("未命名视频");
  const [language, setLanguage] = useState("zh-CN");
  const [sourceLang, setSourceLang] = useState("zh-CN");
  const [targetLang, setTargetLang] = useState("en-US");
  const [inputText, setInputText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [sceneCount, setSceneCount] = useState<number | null>(null);
  const [recording, setRecording] = useState(false);
  const [recordingReady, setRecordingReady] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  async function toggleRecording() {
    if (recording && recorderRef.current) {
      recorderRef.current.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      setRecording(false);
      setRecordingReady(true);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = () => setRecordingReady(true);
      recorder.onstop = () => stream.getTracks().forEach((track) => track.stop());
      streamRef.current = stream;
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      setRecordingReady(false);
    } catch {
      setError("无法访问摄像头或麦克风，请检查浏览器权限");
    }
  }

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
      if (mode === "slides") {
        try {
          body.slides = JSON.parse(inputText);
        } catch {
          throw new Error("slides 必须是合法 JSON 数组 [{title, content}]");
        }
      } else if (mode === "url") {
        try {
          new URL(inputText);
        } catch {
          throw new Error("请输入合法的文章 URL");
        }
        body.url = inputText;
      } else {
        body[props.inputField] = inputText;
      }
      if (mode === "translate") {
        body.source_lang = sourceLang;
        body.target_lang = targetLang;
      }
      const response = await fetch(API + props.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.message || errorBody.detail || ("HTTP " + response.status));
      }
      const draft = await response.json();
      setDraftId(draft.id);
      setSceneCount((draft.scenes || []).length);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "提交失败");
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
            <div style={{ marginBottom: 12 }}><label>标题<br /><input type="text" value={title} onChange={(e) => setTitle(e.target.value)} style={{ width: "100%", padding: 8 }} /></label></div>
            <div style={{ marginBottom: 12 }}><label>语言<br /><input type="text" value={language} onChange={(e) => setLanguage(e.target.value)} style={{ width: 200, padding: 8 }} /></label></div>
            {mode === "translate" && <div style={{ display: "flex", gap: 12, marginBottom: 12 }}><label>源语言<br /><input value={sourceLang} onChange={(e) => setSourceLang(e.target.value)} style={{ padding: 8 }} /></label><label>目标语言<br /><input value={targetLang} onChange={(e) => setTargetLang(e.target.value)} style={{ padding: 8 }} /></label></div>}
            <div style={{ marginBottom: 12 }}><label>{props.inputLabel}<br /><textarea value={inputText} onChange={(e) => setInputText(e.target.value)} placeholder={props.inputPlaceholder} rows={mode === "url" ? 2 : 12} style={{ width: "100%", padding: 8, fontFamily: mode === "slides" ? "monospace" : "inherit" }} /></label></div>
            {mode === "record" && <div style={{ marginBottom: 16 }}><button type="button" onClick={toggleRecording} style={{ padding: "8px 16px" }}>{recording ? "停止录制" : "开始录屏/录音"}</button>{recordingReady && <span style={{ marginLeft: 12, color: "#087f23" }}>录制已完成，请补充转写文本</span>}</div>}
            <button type="submit" disabled={busy || recording} style={{ padding: "8px 24px", background: busy || recording ? "#ccc" : "#2c7be5", color: "#fff", border: "none", borderRadius: 4, cursor: busy || recording ? "wait" : "pointer" }}>{busy ? "生成中..." : "生成草稿"}</button>
          </form>
          {error && <div style={{ marginTop: 16, padding: 12, background: "#fee", color: "#c00", borderRadius: 4 }}>错误: {error}</div>}
          {draftId && <div style={{ marginTop: 16, padding: 12, background: "#efe", color: "#080", borderRadius: 4 }}><div>草稿 ID: <code>{draftId}</code></div><div>已生成 {sceneCount} 个 scene</div><div style={{ marginTop: 8 }}>前往 <a href={"/drafts.html?draft=" + draftId}>Composer</a> 编辑并确认。</div></div>}
        </div>
      </div>
      <Footer />
    </>
  );
}
