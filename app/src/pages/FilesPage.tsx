import { useEffect, useMemo, useState } from "react";
import { Footer } from "../components/layout/Footer";

const TABS = [
  { id: "all", label: "全部" },
  { id: "video", label: "Video" },
  { id: "audio", label: "Audio" },
  { id: "design", label: "Design" },
  { id: "trash", label: "Trash" },
] as const;

type TabId = typeof TABS[number]["id"];

type FileItem = {
  id: string;
  title: string;
  kind: "video" | "audio" | "design";
  updated_at: string;
  size?: string;
  meta?: string;
  href: string;
  trashed?: boolean;
};

function fmtRel(iso: string): string {
  const t = new Date(iso).getTime();
  const now = Date.now();
  const d = Math.floor((now - t) / 86400000);
  if (d < 1) return "今天";
  if (d < 7) return d + " 天前";
  if (d < 30) return Math.floor(d / 7) + " 周前";
  return Math.floor(d / 30) + " 个月前";
}

function iconOf(kind: string): string {
  if (kind === "video") return "🎬";
  if (kind === "audio") return "🎙️";
  if (kind === "design") return "🖼️";
  return "📄";
}

export function FilesPage() {
  const [tab, setTab] = useState<TabId>("all");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [q, setQ] = useState("");
  const [files, setFiles] = useState<FileItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  async function load() {
    setBusy(true); setError(null);
    try {
      const token = localStorage.getItem("fliki-auth-token") || "";
      // 1. 拉 workflow drafts
      const drafts = await fetch("/workflow-drafts", { headers: { Authorization: "Bearer " + token } })
        .then(function (r) { return r.ok ? r.json() : []; })
        .catch(function () { return []; });
      const draftsItems: FileItem[] = (Array.isArray(drafts) ? drafts : []).map(function (d: any) {
        return {
          id: "draft-" + d.id,
          title: d.title || "未命名草稿",
          kind: "video",
          updated_at: d.updated_at || d.created_at || new Date().toISOString(),
          meta: (d.scene_count || "?") + " scene · " + (d.language || "zh-CN"),
          href: "/drafts.html?draft=" + encodeURIComponent(d.id),
        };
      });
      // 2. 拉 autoedit runs (作为成品 video)
      const runs = await fetch("/autoedit/runs", { headers: { Authorization: "Bearer " + token } })
        .then(function (r) { return r.ok ? r.json() : []; })
        .catch(function () { return []; });
      const runsItems: FileItem[] = (Array.isArray(runs) ? runs : []).map(function (r: any) {
        return {
          id: "run-" + r.run_id,
          title: r.title || "Autoedit " + (r.run_id || "").slice(0, 6),
          kind: "video",
          updated_at: r.updated_at || r.created_at || new Date().toISOString(),
          meta: r.status + " · " + (r.duration_seconds || 0) + "s",
          href: "/autoedit.html?run=" + encodeURIComponent(r.run_id),
        };
      });
      // 3. 拉 voice clones (作为 audio)
      const voices = await fetch("/voice-clones", { headers: { Authorization: "Bearer " + token } })
        .then(function (r) { return r.ok ? r.json() : []; })
        .catch(function () { return []; });
      const voiceItems: FileItem[] = (Array.isArray(voices) ? voices : []).map(function (v: any) {
        return {
          id: "voice-" + v.uuid,
          title: v.voice_name || v.avatar_name || "Voice Clone",
          kind: "audio",
          updated_at: v.created_at || new Date().toISOString(),
          meta: v.enabled ? "已启用" : "已停用",
          href: "/voices.html",
        };
      });
      // 4. 拉 templates 渲染 (作为 design)
      const tpls = await fetch("/templates", { headers: { Authorization: "Bearer " + token } })
        .then(function (r) { return r.ok ? r.json() : []; })
        .catch(function () { return []; });
      const tplItems: FileItem[] = (Array.isArray(tpls) ? tpls : []).map(function (t: any) {
        return {
          id: "tpl-" + (t.slug || t.id),
          title: t.name || t.slug || "Template",
          kind: "design",
          updated_at: new Date().toISOString(),
          meta: (t.category || "") + (t.aspect_ratio ? " · " + t.aspect_ratio : ""),
          href: "/templates.html",
        };
      });
      setFiles(draftsItems.concat(runsItems, voiceItems, tplItems));
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setBusy(false);
    }
  }

  useEffect(function () { load(); }, []);

  const filtered = useMemo(function () {
    var query = q.trim().toLowerCase();
    return files.filter(function (f) {
      if (tab === "trash" && !f.trashed) return false;
      if (tab !== "all" && tab !== "trash" && f.kind !== tab) return false;
      if (query && f.title.toLowerCase().indexOf(query) === -1) return false;
      return true;
    }).sort(function (a, b) { return b.updated_at.localeCompare(a.updated_at); });
  }, [files, q, tab]);

  const counts = useMemo(function () {
    var c: Record<string, number> = { all: files.length, video: 0, audio: 0, design: 0, trash: 0 };
    files.forEach(function (f) { c[f.kind] = (c[f.kind] || 0) + 1; });
    return c;
  }, [files]);

  function toggle(id: string) {
    var ns = new Set(selected);
    if (ns.has(id)) ns.delete(id); else ns.add(id);
    setSelected(ns);
  }

  async function shareDraft(id: string) {
    const draftId = id.startsWith("draft-") ? id.slice(6) : "";
    if (!draftId) return;
    try {
      const token = localStorage.getItem("fliki-auth-token") || "";
      const response = await fetch("/workflow-drafts/" + encodeURIComponent(draftId) + "/share", { method: "POST", headers: { Authorization: "Bearer " + token } });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail?.message || "分享链接创建失败");
      await navigator.clipboard?.writeText(new URL(body.url, window.location.origin).toString());
      setError("分享链接已复制");
    } catch (shareError) { setError(shareError instanceof Error ? shareError.message : "分享失败"); }
  }
  function bulkDelete() {
    if (selected.size === 0) return;
    if (!confirm("确定要删除选中的 " + selected.size + " 个文件吗?")) return;
    setFiles(function (arr) { return arr.filter(function (f) { return !selected.has(f.id); }); });
    setSelected(new Set());
  }

  return (
    <main className="shell">
      <h1>我的文件</h1>
      <p className="lead">管理所有草稿、视频、音频和模板. 支持搜索、批量操作和回收站.</p>

      <div className="tabs" role="tablist" aria-label="文件分类">
        {TABS.map(function (t) { return (
          <button role="tab" aria-selected={tab === t.id} key={t.id} className={"tab" + (tab === t.id ? " active" : "")} onClick={function () { setTab(t.id); setSelected(new Set()); }}>
            {t.label} ({(counts[t.id] || 0)})
          </button>
        ); })}
      </div>

      <div className="toolbar">
<label htmlFor="files-search" className="visuallyHidden">搜索文件名</label>
                <input type="search" id="files-search" placeholder="搜索文件名..." value={q} onChange={function (e) { setQ(e.target.value); }} />
        <button className="primary" onClick={function () { window.location.href = "/drafts.html"; }}>+ 新建视频</button>
        <button onClick={function () { window.location.href = "/autoedit.html"; }}>上传素材</button>
        <button onClick={function () { window.location.href = "/voices.html"; }}>克隆声音</button>
        {selected.size > 0 && (
          <div className="bulk">
            <span className="count">已选 {selected.size}</span>
            <button onClick={bulkDelete}>批量删除</button>
            <button onClick={function () { setSelected(new Set()); }}>取消选择</button>
          </div>
        )}
        <div className="view-toggle" role="group" aria-label="视图切换" style={{ marginLeft: "auto" }}>
          <button aria-pressed={view === "grid"} className={view === "grid" ? "active" : ""} onClick={function () { setView("grid"); }}>网格</button>
          <button aria-pressed={view === "list"} className={view === "list" ? "active" : ""} onClick={function () { setView("list"); }}>列表</button>
        </div>
      </div>

      {error && <div className="empty" style={{ borderColor: "rgba(220,80,80,.4)", color: "#ff8585" }}>加载出错: {error}</div>}
      {busy && <div className="empty">加载中...</div>}
      {!busy && !error && filtered.length === 0 && (
        <div className="empty">
          <h3>还没有文件</h3>
          <p>新建视频草稿、上传素材或克隆声音, 文件会自动出现在这里.</p>
          <button className="primary" style={{ marginTop: 14, padding: "10px 22px" }} onClick={function () { window.location.href = "/drafts.html"; }}>+ 新建第一个文件</button>
        </div>
      )}

      {!busy && filtered.length > 0 && view === "grid" && (
        <div className="grid">
          {filtered.map(function (f) {
            return (
              <div key={f.id} className="file-card" style={{ position: "relative" }}>
                <span className="file-tag">{f.kind}</span>
                <button aria-label={selected.has(f.id) ? "取消选择" : "选择"} aria-pressed={selected.has(f.id)} className={"check" + (selected.has(f.id) ? " on" : "")} style={{ position: "absolute", top: 14, left: 14, zIndex: 2 }} onClick={function (e) { e.preventDefault(); e.stopPropagation(); toggle(f.id); }}>
                  {selected.has(f.id) ? "✓" : ""}
                </button>
                <a href={f.href} style={{ textDecoration: "none", color: "inherit", display: "block" }}>
                  <div className={"file-thumb " + f.kind}>{iconOf(f.kind)}</div>
                  <p className="file-title">{f.title}</p>
                  <div className="file-meta"><span>{fmtRel(f.updated_at)}</span><span>{f.meta || ""}</span></div>
                </a>
              </div>
            );
          })}
        </div>
      )}

      {!busy && filtered.length > 0 && view === "list" && (
        <div className="list-view">
          {filtered.map(function (f) {
            return (
              <div key={f.id} className="file-row">
                <button aria-label={selected.has(f.id) ? "取消选择" : "选择"} aria-pressed={selected.has(f.id)} className={"check" + (selected.has(f.id) ? " on" : "")} onClick={function () { toggle(f.id); }}>
                  {selected.has(f.id) ? "✓" : ""}
                </button>
                <div>
                  <span className="ico">{iconOf(f.kind)}</span> <a href={f.href} style={{ color: "#eef2ff", textDecoration: "none", fontWeight: 600 }}>{f.title}</a>
                </div>
                <span className="meta">{f.kind.toUpperCase()}</span>
                <span className="meta">{fmtRel(f.updated_at)}</span>
                <span className="meta">{f.meta || ""}</span>
                <div className="actions">
                  <button onClick={function () { window.location.href = f.href; }}>打开</button>{f.id.startsWith("draft-") && <button onClick={function () { void shareDraft(f.id); }}>分享</button>}
                  <button onClick={function () { setFiles(function (arr) { return arr.filter(function (x) { return x.id !== f.id; }); }); }}>删除</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Footer />
    </main>
  );
}

export default FilesPage;
