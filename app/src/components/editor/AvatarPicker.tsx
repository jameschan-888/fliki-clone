import { useEffect, useRef, useState } from "react";
import {
  apiAssetUrl,
  deleteAvatarClone,
  listAvatarClones,
  previewAvatarUrl,
  updateAvatarMeta,
  uploadAvatarAudio,
  uploadAvatarFace
} from "../../api/drafts";

type AvatarClone = {
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
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError("");
    listAvatarClones()
      .then((rows) => setClones(rows as AvatarClone[]))
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [open, refreshTick]);

  if (!open) return null;

  function reload() { setRefreshTick((k) => k + 1); }

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
      setShowCreate(false);
      setName("");
      setFile(null);
      reload();
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
          <h3>选择 / 管理 Avatar</h3>
          <button type="button" onClick={onClose}>✕</button>
        </div>
        <p className="hint">未安装数字人模型时会自动生成静态头像视频，不会阻塞整条任务。</p>
        {error && <p className="error">{error}</p>}
        {loading ? <p>加载中…</p> : (
          <>
            <div className="cloneGrid">
              <button type="button" className={"cloneCard" + (current === null ? " active" : "")} onClick={() => onPick(null)}>
                <div className="empty">无</div>
                <strong>不调用数字人</strong>
                <span>纯旁白 / 字幕</span>
              </button>
              {clones.map((c) => (
                <AvatarCard
                  key={c.uuid}
                  clone={c}
                  selected={current === `avatar:${c.uuid}`}
                  onPick={() => onPick(`avatar:${c.uuid}`)}
                  onChanged={() => { reload(); onAfterChange?.(); }}
                />
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

function AvatarCard({
  clone,
  selected,
  onPick,
  onChanged
}: {
  clone: AvatarClone;
  selected: boolean;
  onPick: () => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [localError, setLocalError] = useState("");
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState(clone.avatar_name);
  const faceRef = useRef<HTMLInputElement | null>(null);
  const audioRef = useRef<HTMLInputElement | null>(null);

  async function handleFace(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy("face"); setLocalError("");
    try {
      await uploadAvatarFace(clone.uuid, f);
      onChanged();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "换图失败");
    } finally {
      setBusy(null);
      if (faceRef.current) faceRef.current.value = "";
    }
  }
  async function handleAudio(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy("audio"); setLocalError("");
    try {
      await uploadAvatarAudio(clone.uuid, f);
      onChanged();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "换音失败");
    } finally {
      setBusy(null);
      if (audioRef.current) audioRef.current.value = "";
    }
  }
  async function saveName() {
    const newName = nameInput.trim();
    if (!newName || newName === clone.avatar_name) {
      setEditingName(false);
      setNameInput(clone.avatar_name);
      return;
    }
    setBusy("name"); setLocalError("");
    try {
      await updateAvatarMeta(clone.uuid, { avatar_name: newName });
      onChanged();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "改名失败");
    } finally {
      setBusy(null);
      setEditingName(false);
    }
  }
  async function handleDelete() {
    if (!window.confirm(`删除 Avatar "${clone.avatar_name}"? 文件也会一起删除。`)) return;
    setBusy("delete"); setLocalError("");
    try {
      await deleteAvatarClone(clone.uuid);
      onChanged();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "删除失败");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className={"cloneCard" + (selected ? " active" : "")}>
      <button type="button" className="clonePick" onClick={onPick}>
        <img src={previewAvatarUrl(clone.uuid)} alt={clone.avatar_name} />
        {editingName ? (
          <input
            className="renameInput"
            autoFocus
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveName();
              else if (e.key === "Escape") { setEditingName(false); setNameInput(clone.avatar_name); }
            }}
          />
        ) : (
          <strong>{clone.avatar_name}</strong>
        )}
        <span>{clone.enabled ? "已启用" : "已停用"}</span>
      </button>
      <div className="cloneTools">
        <button type="button" disabled={!!busy} title="换人脸图"
          onClick={(e) => { e.stopPropagation(); faceRef.current?.click(); }}>
          {busy === "face" ? "…" : "✏️ 换图"}
        </button>
        <input ref={faceRef} type="file" accept="image/png,image/jpeg,image/webp" hidden
          onChange={handleFace} />
        <button type="button" disabled={!!busy} title="换参考音频"
          onClick={(e) => { e.stopPropagation(); audioRef.current?.click(); }}>
          {busy === "audio" ? "…" : "🔊 换音"}
        </button>
        <input ref={audioRef} type="file" accept="audio/mpeg,audio/wav,audio/m4a" hidden
          onChange={handleAudio} />
        {editingName ? (
          <>
            <button type="button" disabled={!!busy} onClick={(e) => { e.stopPropagation(); saveName(); }}>✓</button>
            <button type="button" disabled={!!busy} onClick={(e) => { e.stopPropagation(); setEditingName(false); setNameInput(clone.avatar_name); }}>✕</button>
          </>
        ) : (
          <button type="button" disabled={!!busy} title="改名"
            onClick={(e) => { e.stopPropagation(); setEditingName(true); }}>
            {busy === "name" ? "…" : "✏️ 改名"}
          </button>
        )}
        <button type="button" className="danger" disabled={!!busy} title="删除"
          onClick={(e) => { e.stopPropagation(); handleDelete(); }}>
          {busy === "delete" ? "…" : "🗑"}
        </button>
      </div>
      {localError && <p className="error">{localError}</p>}
    </div>
  );
}
