import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AutoEditDraft,
  AutoEditRun,
  AutoEditSegment,
  AutoEditUpload,
  SegmentKind,
  SegmentPatchInput,
} from "../types/autoedit";
import {
  confirmDraft,
  createDraftFromUpload,
  createRun,
  formatApiError,
  getRun,
  outputUrl,
  patchSegment,
  uploadVideoXhr,
} from "../api/autoedit";
import { API } from "../api/drafts";
import { ToastContainer, makeToast, type ToastItem, type ToastKind } from "../components/ui/ToastContainer";
import { InlineError } from "../components/ui/InlineError";
import { UploadProgress } from "../components/ui/UploadProgress";

// ────────────── 子组件 ──────────────

function ApiStatus() {
  const [state, setState] = useState<"checking" | "ok" | "down">("checking");
  useEffect(() => {
    fetch(API + "/health")
      .then((r) => r.json())
      .then((j) => setState(j.status === "ok" ? "ok" : "down"))
      .catch(() => setState("down"));
  }, []);
  const label = state === "ok" ? "API: ok" : state === "down" ? "API: 连接失败" : "API: --";
  return <span className="autoeditApiStatus">· {label}</span>;
}

function UploadPanel(props: {
  uploading: boolean;
  progress: { loaded: number; total: number };
  upload: AutoEditUpload | null;
  error: unknown;
  onPick: (file: File) => void;
  onCreateDraft: () => void;
  creatingDraft: boolean;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) props.onPick(f);
  };
  return (
    <div className="autoeditPanel">
      <div className="autoeditRow">
        <input ref={inputRef} type="file" accept="video/*" onChange={onChange} disabled={props.uploading} />
        {props.uploading && <span className="autoeditMuted">上传中…</span>}
      </div>
      {props.uploading && (
        <UploadProgress loaded={props.progress.loaded} total={props.progress.total} label="上传中" />
      )}
      {props.upload && !props.uploading && (
        <div className="autoeditUploadInfo">
          <strong>{props.upload.filename}</strong> · {props.upload.size_bytes} B · {props.upload.duration_seconds}s · {props.upload.width}x{props.upload.height} ({props.upload.container})
        </div>
      )}
      <InlineError error={props.error} fallback="上传失败" />
      {props.upload && !props.uploading && (
        <div className="autoeditRow" style={{ marginTop: 10 }}>
          <button className="autoeditBtn" onClick={props.onCreateDraft} disabled={props.creatingDraft}>
            {props.creatingDraft ? "生成草稿中…" : "生成可编辑草稿"}
          </button>
        </div>
      )}
    </div>
  );
}

function SegmentRow(props: {
  segment: AutoEditSegment;
  disabled: boolean;
  onSave: (segId: string, body: SegmentPatchInput) => void;
}) {
  const [subtitle, setSubtitle] = useState(props.segment.subtitle || "");
  const [kind, setKind] = useState<SegmentKind>(props.segment.kind);
  const dirty = subtitle !== (props.segment.subtitle || "") || kind !== props.segment.kind;
  return (
    <div className={"autoeditSeg" + (props.segment.kind === "drop" ? " autoeditSeg-drop" : "")}>
      <div className="autoeditSegMeta">
        #{props.segment.position} [{props.segment.start_seconds}s → {props.segment.end_seconds}s]
        <span className={"autoeditTag autoeditTag-" + props.segment.kind}>{props.segment.kind}</span>
        <span className="autoeditTag">{props.segment.asset_kind || "none"}</span>
        <span className="autoeditMuted">music={props.segment.music_volume}</span>
      </div>
      <div className="autoeditCol">
        <label className="autoeditLabel">字幕</label>
        <textarea
          value={subtitle}
          onChange={(e) => setSubtitle(e.target.value)}
          disabled={props.disabled}
          rows={2}
        />
      </div>
      <div className="autoeditRow" style={{ marginTop: 6 }}>
        <select value={kind} onChange={(e) => setKind(e.target.value as SegmentKind)} disabled={props.disabled}>
          <option value="keep">keep 保留</option>
          <option value="trim">trim 精简</option>
          <option value="drop">drop 删除</option>
        </select>
        <button
          className="autoeditBtn autoeditBtn-secondary"
          disabled={props.disabled || !dirty}
          onClick={() => props.onSave(props.segment.id, { subtitle, kind })}
        >
          保存
        </button>
      </div>
    </div>
  );
}

function DraftPanel(props: {
  draft: AutoEditDraft;
  onSave: (segId: string, body: SegmentPatchInput) => void;
  onConfirm: () => void;
  confirming: boolean;
}) {
  const disabled = props.draft.status !== "draft";
  return (
    <div className="autoeditPanel">
      <div className="autoeditRow" style={{ marginBottom: 12 }}>
        <span className={"autoeditStatus autoeditStatus-" + props.draft.status}>{props.draft.status}</span>
        <span className="autoeditMuted">v{props.draft.version} · {props.draft.segments.length} segs · {props.draft.duration_seconds}s{props.draft.transcription_source ? " · 转写=" + props.draft.transcription_source : ""}</span>
      </div>
      {props.draft.transcription_warning && (
        <div className="autoeditWarning" data-testid="autoedit-transcription-warning">
          <strong>⚠️ 转写提示：</strong>{props.draft.transcription_warning}
        </div>
      )}
      {props.draft.segments.map((seg) => (
        <SegmentRow key={seg.id} segment={seg} disabled={disabled} onSave={props.onSave} />
      ))}
      {props.draft.status === "draft" && (
        <div className="autoeditRow" style={{ marginTop: 12 }}>
          <button className="autoeditBtn" onClick={props.onConfirm} disabled={props.confirming}>
            {props.confirming ? "确认中…" : "确认草稿 → 生成"}
          </button>
        </div>
      )}
    </div>
  );
}

function RunPanel(props: { run: AutoEditRun; onRetry: () => void }) {
  const nodes = props.run.nodes || [];
  const processing = nodes.filter((n) => n.status === "processing");
  const last = nodes.length ? nodes[nodes.length - 1] : null;
  let currentLabel = "初始化…";
  if (props.run.status === "success") currentLabel = "完成 ✓";
  else if (props.run.status === "failed") currentLabel = "失败 ✗";
  else if (processing.length)
    currentLabel = processing.map((n) => n.node_type + (n.segment_id ? " (" + n.segment_id.slice(0, 6) + ")" : "")).join(", ");
  else if (last) currentLabel = last.node_type + " (" + last.status + ")";

  const videoSrc = outputUrl(props.run.output_path);

  return (
    <div className="autoeditPanel">
      <div className="autoeditRow" style={{ justifyContent: "space-between", marginBottom: 6 }}>
        <span className="autoeditMuted">当前节点</span>
        <strong>{currentLabel}</strong>
      </div>
      <progress value={props.run.progress} max={100} className="autoeditProgress" />
      <div className="autoeditRow" style={{ justifyContent: "space-between", fontSize: 11, color: "var(--color-text-tertiary)" }}>
        <span>status={props.run.status}</span>
        <span>{props.run.progress}%</span>
      </div>
      <div className="autoeditLog">
        {nodes.map((n) => (
          <div key={n.id} className={"autoeditNode autoeditNode-" + n.status}>
            [{n.node_type}] {n.segment_id ? "seg=" + n.segment_id.slice(0, 8) : ""} {n.status}
            {n.provider ? " · " + n.provider : ""}
            {n.message ? " · " + n.message.slice(0, 80) : ""}
          </div>
        ))}
      </div>
      {props.run.message && <InlineError error={{ message: props.run.message }} fallback="生成失败" />}
      {props.run.status === "success" && videoSrc && (
        <div className="autoeditOutput">
          <div className="autoeditMuted">{props.run.output_path}</div>
          <video controls src={videoSrc} className="autoeditVideo" />
        </div>
      )}
      {props.run.status === "failed" && (
        <button className="autoeditBtn" style={{ marginTop: 8 }} onClick={props.onRetry}>
          重试
        </button>
      )}
    </div>
  );
}

// ────────────── 主组件 ──────────────

export function AutoEditPage() {
  const [upload, setUpload] = useState<AutoEditUpload | null>(null);
  const [draft, setDraft] = useState<AutoEditDraft | null>(null);
  const [run, setRun] = useState<AutoEditRun | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState({ loaded: 0, total: 0 });
  const [uploadError, setUploadError] = useState<unknown>(null);
  const [creatingDraft, setCreatingDraft] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismissToast = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);
  const pushToast = useCallback((kind: ToastKind, text: string) => {
    setToasts((t) => [...t, makeToast(kind, text)]);
  }, []);

  // 上传文件
  const handleUpload = useCallback(
    async (file: File) => {
      setUploadError(null);
      setUpload(null);
      setDraft(null);
      setRun(null);
      setUploading(true);
      setProgress({ loaded: 0, total: file.size });
      try {
        const r = await uploadVideoXhr(file, (loaded, total) => setProgress({ loaded, total }));
        setUpload(r);
        pushToast("ok", "上传完成");
      } catch (e) {
        setUploadError(e);
        pushToast("error", formatApiError(e, "上传失败"));
      } finally {
        setUploading(false);
      }
    },
    [pushToast],
  );

  // 创建草稿
  const handleCreateDraft = useCallback(async () => {
    if (!upload) return;
    setCreatingDraft(true);
    try {
      const d = await createDraftFromUpload(upload.id, "zh-CN");
      setDraft(d);
      pushToast("ok", "草稿已生成");
    } catch (e) {
      pushToast("error", formatApiError(e, "生成草稿失败"));
    } finally {
      setCreatingDraft(false);
    }
  }, [upload, pushToast]);

  // 保存 segment
  const handleSaveSegment = useCallback(
    async (segId: string, body: SegmentPatchInput) => {
      if (!draft) return;
      try {
        const d = await patchSegment(draft.id, segId, body);
        setDraft(d);
        pushToast("ok", "已保存");
      } catch (e) {
        pushToast("error", formatApiError(e, "保存失败"));
      }
    },
    [draft, pushToast],
  );

  // 轮询 run
  const startPolling = useCallback(
    (runId: string) => {
      const tick = async () => {
        try {
          const r = await getRun(runId);
          setRun(r);
          if (r.status === "success" || r.status === "failed") {
            pushToast(r.status === "success" ? "ok" : "error", r.status === "success" ? "渲染完成" : "渲染失败: " + (r.message || "未知"));
            return;
          }
        } catch (e) {
          pushToast("warning", formatApiError(e, "轮询失败"));
        }
        pollTimerRef.current = setTimeout(tick, 3000);
      };
      tick();
    },
    [pushToast],
  );

  // 确认 + 创建 run
  const handleConfirm = useCallback(async () => {
    if (!draft) return;
    setConfirming(true);
    try {
      const confirmed = await confirmDraft(draft.id);
      setDraft(confirmed);
      const r = await createRun(confirmed.id);
      setRun(r);
      pushToast("ok", "已开始生成");
      startPolling(r.id);
    } catch (e) {
      pushToast("error", formatApiError(e, "启动生成失败"));
    } finally {
      setConfirming(false);
    }
  }, [draft, pushToast, startPolling]);

  const handleRetry = useCallback(async () => {
    if (!run) return;
    try {
      const r = await fetch(API + "/autoedit-runs/" + encodeURIComponent(run.id) + "/retry", { method: "POST" }).then((r) => r.json());
      setRun(r);
      pushToast("ok", "已重新入队");
      startPolling(run.id);
    } catch (e) {
      pushToast("error", formatApiError(e, "重试失败"));
    }
  }, [run, pushToast, startPolling]);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, []);

  return (
    <div className="autoeditPage">
      <header className="autoeditHeader">
        <h1>🎬 Auto-edit 视频剪辑 <ApiStatus /></h1>
      </header>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      <section className="autoeditCard">
        <h2 className="autoeditCardTitle">① 上传视频</h2>
        <UploadPanel
          uploading={uploading}
          progress={progress}
          upload={upload}
          error={uploadError}
          onPick={handleUpload}
          onCreateDraft={handleCreateDraft}
          creatingDraft={creatingDraft}
        />
      </section>

      {draft && (
        <section className="autoeditCard">
          <h2 className="autoeditCardTitle">② 草稿</h2>
          <DraftPanel draft={draft} onSave={handleSaveSegment} onConfirm={handleConfirm} confirming={confirming} />
        </section>
      )}

      {run && (
        <section className="autoeditCard">
          <h2 className="autoeditCardTitle">③ 生成进度</h2>
          <RunPanel run={run} onRetry={handleRetry} />
        </section>
      )}
    </div>
  );
}
