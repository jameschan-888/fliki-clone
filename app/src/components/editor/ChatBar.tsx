import { useState } from "react";
import { API } from "../../api/drafts";

export type ChatBarProps = {
  draftId: string;
  onApplied?: (result: { operation: string; applied_count: number }) => void;
};

export function ChatBar(props: ChatBarProps) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<{ role: "user" | "ai"; content: string; meta?: string }[]>([]);
  const [error, setError] = useState<string | null>(null);

  const suggestions = [
    "make all scenes 9:16",
    "shorten all scenes by 1 second",
    "darken all scenes",
    "change voice to en-US-AriaNeural",
    "add sunset to visuals",
  ];

  async function submit(instruction?: string) {
    const finalText = (instruction ?? text).trim();
    if (!finalText) return;
    setError(null);
    setBusy(true);
    setHistory((h) => [...h, { role: "user", content: finalText }]);
    setText("");
    try {
      const token = localStorage.getItem("fliki-auth-token") || "";
      const r = await fetch(API + "/chat/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
        body: JSON.stringify({ draft_id: props.draftId, instruction: finalText }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(data.message || data.detail || "HTTP " + r.status);
      }
      const msg = "applied " + data.applied_count + " change(s) via " + data.operation;
      setHistory((h) => [...h, { role: "ai", content: msg, meta: finalText }]);
      if (props.onApplied) props.onApplied({ operation: data.operation, applied_count: data.applied_count });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "chat failed";
      setError(msg);
      setHistory((h) => [...h, { role: "ai", content: "error: " + msg }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{
      position: "fixed",
      bottom: 16,
      right: 16,
      width: 360,
      maxHeight: "70vh",
      background: "#fff",
      border: "1px solid #ddd",
      borderRadius: 12,
      boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      fontFamily: "system-ui, -apple-system, sans-serif",
      zIndex: 1000,
    }}>
      <div style={{
        padding: "10px 14px",
        background: "linear-gradient(135deg, #2c7be5, #5b6cff)",
        color: "#fff",
        fontWeight: 700,
        fontSize: 13,
      }}>
        Chat Edit (beta)
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 10, fontSize: 13 }}>
        {history.length === 0 && (
          <div style={{ color: "#888", padding: "20px 8px", textAlign: "center" }}>
            用自然语言编辑草稿。试试：
          </div>
        )}
        {history.map((h, i) => (
          <div key={i} style={{
            margin: "6px 0",
            padding: "8px 10px",
            borderRadius: 8,
            background: h.role === "user" ? "#eef4ff" : "#f4f4f4",
            color: "#222",
            whiteSpace: "pre-wrap",
          }}>
            <strong style={{ color: h.role === "user" ? "#2c7be5" : "#666" }}>
              {h.role === "user" ? "you" : "ai"}
            </strong>
            : {h.content}
          </div>
        ))}
      </div>
      <div style={{ padding: 8, borderTop: "1px solid #eee" }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 6 }}>
          {suggestions.map((s) => (
            <button key={s} type="button" disabled={busy} onClick={() => submit(s)} style={{
              fontSize: 11, padding: "3px 8px", background: "#f8f9fa",
              border: "1px solid #ddd", borderRadius: 12, cursor: busy ? "wait" : "pointer",
            }}>{s}</button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            placeholder="输入指令 (e.g. darken scene 2)"
            disabled={busy}
            style={{ flex: 1, padding: 8, border: "1px solid #ddd", borderRadius: 6, fontSize: 13 }}
          />
          <button type="button" disabled={busy} onClick={() => submit()} style={{
            padding: "8px 14px", background: busy ? "#ccc" : "#2c7be5", color: "#fff",
            border: "none", borderRadius: 6, cursor: busy ? "wait" : "pointer",
          }}>{busy ? "..." : "Send"}</button>
        </div>
        {error && <div style={{ color: "#c00", fontSize: 11, marginTop: 4 }}>{error}</div>}
      </div>
    </div>
  );
}
