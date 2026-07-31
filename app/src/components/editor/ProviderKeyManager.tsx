import { useEffect, useState } from "react";
import { API } from "../../api/drafts";

type ProviderRow = {
  id: string;
  category: string;
  name: string;
  enabled: boolean;
  is_default: boolean;
  priority: number;
  base_url: string | null;
  model: string | null;
  extra: Record<string, unknown>;
  has_api_key: boolean;
  api_key_masked: string | null;
  is_mock?: boolean;
  source?: string;
  persist?: boolean;
  api_key_env?: string;
};

type Props = {
  open: boolean;
  onClose: () => void;
  category?: string;
};

const CATEGORY_LABEL: Record<string, string> = {
  stock: "素材库",
  tts: "配音",
  avatar: "数字人",
  music: "音乐"
};

export function ProviderKeyManager({ open, onClose, category }: Props) {
  const [rows, setRows] = useState<ProviderRow[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [extra, setExtra] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setError("");
    try {
      const qs = category ? `?category=${encodeURIComponent(category)}` : "";
      const r = await fetch(API + "/provider-configs" + qs);
      if (!r.ok) throw new Error("加载失败");
      setRows((await r.json()) as ProviderRow[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
  }

  useEffect(() => { if (open) void load(); }, [open, category]);

  function publishClass(r: ProviderRow): string {
  if (r.is_mock) return "warning";
  if (r.has_api_key && r.enabled) return "good";
  if (!r.has_api_key) return "bad";
  return "warn";
}
function publishLabel(r: ProviderRow): string {
  if (r.is_mock) return "仅 Mock";
  if (r.has_api_key && r.enabled) return "可发布";
  if (!r.has_api_key) return "需 Key";
  return "未启用";
}
function copyEnvBlock(rows: ProviderRow[]): string {
  return rows
    .filter((r) => r.has_api_key)
    .map((r) => `${r.api_key_env || r.id.toUpperCase().replace(/[^A-Z0-9]+/g, "_")}=`)
    .join("\n");
}
function startEdit(row: ProviderRow) {
    setEditing(row.id);
    setApiKey("");
    setBaseUrl(row.base_url || "");
    setModel(row.model || "");
    setExtra(JSON.stringify(row.extra || {}, null, 2));
    setEnabled(row.enabled);
    setMessage("");
    setError("");
  }

  async function save() {
    if (!editing) return;
    const row = rows.find((r) => r.id === editing);
    if (!row) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const body: Record<string, unknown> = { enabled, base_url: baseUrl || null, model: model || null };
      if (apiKey.trim()) body.api_key = apiKey.trim();
      try { body.extra = extra.trim() ? JSON.parse(extra) : {}; }
      catch { throw new Error("extra 不是合法 JSON"); }
      const r = await fetch(
        `${API}/provider-configs/${row.category}/${row.name}`,
        { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      );
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "保存失败");
      setMessage("已保存");
      setApiKey("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  const grouped = rows.reduce<Record<string, ProviderRow[]>>((acc, r) => {
    (acc[r.category] ||= []).push(r); return acc;
  }, {});

  return (
    <div className="modalMask" onClick={onClose}>
      <div className="modal wide" onClick={(e) => e.stopPropagation()}>
        <div className="modalHeader">
          <h3>Provider 密钥与配置</h3>
          <div className="row">
            <button type="button" onClick={() => {
              const env = copyEnvBlock(rows);
              navigator.clipboard?.writeText(env);
              setMessage(env ? "已复制 key 列表到剪贴板 (无明文)" : "当前没有已配置 key");
            }}>复制 key 变量名</button>
            <button type="button" onClick={onClose}>✕</button>
          </div>
        </div>
        {error && <p className="error">{error}</p>}
        {message && <p className="hint ok">{message}</p>}
        {Object.entries(grouped).map(([cat, list]) => (
          <section key={cat} className="provGroup">
            <h4>{CATEGORY_LABEL[cat] || cat}</h4>
            <ul>
              {list.map((r) => (
                <li key={r.id} className={"prov " + publishClass(r)}>
                  <div>
                    <strong>{r.name}</strong>
                    <span className="keyTag">{r.has_api_key ? `key: ${r.api_key_masked}` : "未配 key"}</span>
                    {r.is_default && <span className="defaultTag">默认</span>}
                    {r.is_mock && <span className="tag warning">Mock</span>}
                    <span className={"tag " + publishClass(r)}>{publishLabel(r)}</span>
                  </div>
                  <div>
                    <span>{r.base_url || "—"}</span>
                    <span>{r.model || "—"}</span>
                    <button type="button" onClick={() => startEdit(r)}>编辑</button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
        {editing && (() => {
          const row = rows.find((r) => r.id === editing);
          if (!row) return null;
          return (
            <div className="editPanel">
              <h4>编辑 {row.category}/{row.name}</h4>
              <label>API Key（留空不修改）<input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="保持原值" /></label>
              <label>Base URL<input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} /></label>
              <label>Model<input value={model} onChange={(e) => setModel(e.target.value)} /></label>
              <label>Extra (JSON)<textarea rows={6} value={extra} onChange={(e) => setExtra(e.target.value)} /></label>
              <label className="check"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />启用此 provider</label>
              <div className="editFoot">
                <button type="button" onClick={() => setEditing(null)}>取消</button>
                <button type="button" className="primary" disabled={saving} onClick={save}>{saving ? "保存中…" : "保存"}</button>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}