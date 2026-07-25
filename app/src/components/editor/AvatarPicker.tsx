import { useEffect, useState } from "react";
import { apiAssetUrl, listAvatarClones, previewAvatarUrl } from "../../api/drafts";

export type AvatarClone = {
  uuid: string;
  avatar_name: string;
  ref_face_path: string;
  enabled: boolean;
};

type Props = {
  open: boolean;
  current: string | null;
  onPick: (value: string | null) => void;
  onClose: () => void;
  onAfterChange?: () => void;
};

export function AvatarPicker({ open, current, onPick, onClose, onAfterChange }: Props) {
  const [clones, setClones] = useState<AvatarClone[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError("");
    listAvatarClones()
      .then((rows) => setClones(rows as AvatarClone[]))
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  async function submit() {
    if (!file || !name.trim()) {
      setError("需要名称和人脸图片");
      return;
    }
    setCreating(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("avatar_name", name.trim());
      fd.append("language", "zh");
      fd.append("ref_face", file);
      const r = await fetch(apiAssetUrl("/avatar-clones"), { method: "POST", body: fd });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.message || body.detail || "创建失败");
      }
      const rows = await listAvatarClones();
      setClones(rows as AvatarClone[]);
      setShowCreate(false);
      setName("");
      setFile(null);
      onAfterChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="modalMask" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modalHeader">
          <h3>选择 Avatar</h3>
          <button type="button" onClick={onClose}>✕</button>
        </div>
        <p className="hint">未安装数字人模型时会自动生成静态头像视频，不会阻塞整条任务。</p>
        {error && <p className="error">{error}</p>
        {loading ? <p>加载中…</p> : (
          <>
            <div className="cloneGrid">
              <button type="button" className={"cloneCard" + (current === null ? " active" : "")} onClick={() => onPick(null)}>
                <div className="empty">无</div>
                <strong>不调用数字人</strong>
                <span>纯旁白 / 字幕</span>
              </button>
              {clones.map((c) => (
                <button key={c.uuid} type="button" className={"cloneCard" + (current === `avatar:${c.uuid}` ? " active" : "")} onClick={() => onPick(`avatar:${c.uuid}`)}>
                  <img src={previewAvatarUrl(c.uuid)} alt={c.avatar_name} />
                  <strong>{c.avatar_name}</strong>
                  <span>{c.enabled ? "已启用" : "已停用"}</span>
                </button>
              ))}
            </div>
            <div className="modalFoot">
              {!showCreate ? (
                <button type="button" onClick={() => setShowCreate(true)}>+ 新建 Avatar</button>
              ) : (
                <div className="createForm">
                  <input placeholder="Avatar 名称" value={name} onChange={(e) => setName(e.target.value)} />
                  <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                  <button type="button" disabled={creating} onClick={submit}>{creating ? "上传中…" : "保存"}</button>
                  <button type="button" onClick={() => { setShowCreate(false); setName(""); setFile(null); }}>取消</button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}