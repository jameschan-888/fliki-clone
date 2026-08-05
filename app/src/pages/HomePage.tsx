import { useRef, useState } from "react";
import { EnvCheckBadge } from "../components/layout/EnvCheckBadge";
import { Footer } from "../components/layout/Footer";
import { ProviderKeyManager } from "../components/editor/ProviderKeyManager";
import App from "../App";
import { API } from "../api/drafts";

const NAV_LINKS = [
  { href: "/index.html", label: "首页" },
  { href: "/drafts.html", label: "Script to Video" },
  { href: "/blog.html", label: "Blog to Video" },
  { href: "/ppt.html", label: "PPT to Video" },
  { href: "/record.html", label: "Record to Video" },
  { href: "/translate.html", label: "Translate Video" },
  { href: "/autoedit.html", label: "Auto-edit" },
  { href: "/voices.html", label: "声音库" },
  { href: "/templates.html", label: "模板" },
];

type AvatarSummary = { uuid: string; avatar_name: string; ref_face_path: string | null; enabled: boolean };

export function HomePage() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [avatarOpen, setAvatarOpen] = useState(false);
  const [avatars, setAvatars] = useState<AvatarSummary[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newFile, setNewFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const fileRef = useRef<HTMLInputElement | null>(null);

  async function openAvatarPanel() {
    setAvatarOpen(true);
    setError("");
    setMessage("");
    try {
      const r = await fetch(API + "/avatar-clones");
      if (!r.ok) throw new Error("加载失败");
      setAvatars((await r.json()) as AvatarSummary[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
  }

  async function submitAvatar(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim() || !newFile) {
      setError("需要名称和人脸图片");
      return;
    }
    setCreating(true);
    setError("");
    setMessage("");
    try {
      const fd = new FormData();
      fd.append("avatar_name", newName.trim());
      fd.append("language", "zh");
      fd.append("ref_face", newFile);
      const r = await fetch(API + "/avatar-clones", { method: "POST", body: fd });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.message || body.detail || "创建失败");
      }
      const created = await r.json() as { avatar_name: string };
      setMessage("已创建 " + created.avatar_name);
      setNewName("");
      setNewFile(null);
      if (fileRef.current) fileRef.current.value = "";
      const refreshed = await fetch(API + "/avatar-clones");
      if (refreshed.ok) setAvatars((await refreshed.json()) as AvatarSummary[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  return (
    <>
      <nav>
        <div className="navLeft">
          <a href="#" onClick={(e) => { e.preventDefault(); location.reload(); }}>Fliki 还原</a>
          <div className="navLinks">
            {NAV_LINKS.map((link) => (
              <a key={link.href} href={link.href}>{link.label}</a>
            ))}
            <button type="button" className="linkButton" onClick={openAvatarPanel}>Avatar 库</button>
            <a href="/env-check.html">环境诊断</a>
          </div>
        </div>
        <div className="navRight">
          <EnvCheckBadge />
          <button type="button" className="textButton" onClick={() => setSettingsOpen(true)}>设置</button>
        </div>
      </nav>
      <App />
      <Footer />
      <ProviderKeyManager open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      {avatarOpen && (
        <div className="modalMask" onClick={() => setAvatarOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modalHeader">
              <h3>Avatar 库</h3>
              <button type="button" onClick={() => setAvatarOpen(false)}>✕</button>
            </div>
            {error && <p className="error">{error}</p>}
            {message && <p className="hint ok">{message}</p>}
            <form onSubmit={submitAvatar} className="createForm" style={{ marginBottom: 16 }}>
              <label htmlFor="avatar-name" className="visuallyHidden">Avatar 名称</label>
              <input id="avatar-name" placeholder="Avatar 名称" value={newName} onChange={(e) => setNewName(e.target.value)} />
              <button type="submit" className="primary" disabled={creating}>{creating ? "上传中…" : "保存"}</button>
              <label htmlFor="avatar-ref-face" className="visuallyHidden">人脸图片</label>
              <input id="avatar-ref-face" ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setNewFile(e.target.files?.[0] || null)} />
            </form>
            {avatars === null ? <p>加载中…</p> : avatars.length === 0 ? <p>还没有 Avatar 克隆</p> : (
              <ul className="avatarList">
                {avatars.map((a) => (
                  <li key={a.uuid}>
                    {a.ref_face_path ? <img src={API + "/avatar-clones/" + encodeURIComponent(a.uuid) + "/ref-face"} alt={a.avatar_name} /> : <span className="empty">🧑</span>}
                    <strong>{a.avatar_name}</strong>
                    <span className={a.enabled ? "tag ok" : "tag off"}>{a.enabled ? "已启用" : "已停用"}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="hint">上传的人脸参考图保存到 <code>data/uploads/avatars/</code>，确认草稿后 pipeline 会自动调用 Wav2Lip-ONNX。</p>
          </div>
        </div>
      )}
    </>
  );
}
