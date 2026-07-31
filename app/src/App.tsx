import { useEffect, useRef, useState } from "react";
import type { SceneDraft, WorkflowDraft, WorkflowRun } from "./types/draft";
import { AvatarPicker } from "./components/editor/AvatarPicker";
import { Toast } from "./components/ui/Toast";
import {
  addScene,
  apiAssetUrl,
  fullUploadUrl,
  confirmDraft,
  createDraft,
  createRun,
  deleteScene,
  getDraft,
  getRenderLatest,
  getRun,
  listRuns,
  listRunsPage,
  listAvatarClones,
  uploadLocalFile,
  outputUrl,
  previewVoice,
  previewCloneVoice,
  reorderScenes,
  rerenderRun,
  retryRun,
  updateScene,
  copyDraftAsTemplate,
} from "./api/drafts";
import { formatApiError } from "./api/drafts";
import type { TemplateMeta } from "./api/drafts";
import { Composer, computeTemplateCompletion, findNextIncompleteScene } from "./components/editor/Composer";
import { getTemplateCatalogSnapshot, loadTemplateCatalogWithRetry, subscribeTemplateCache } from "./api/templateCache";

const sample = "一条好视频，先从清晰的脚本开始。系统会把脚本拆成可编辑场景。你可以修改旁白、画面、声音和时长。只有确认后，才会调用素材、配音、音乐和渲染，避免浪费接口额度和算力。";
const savedDraftKey = "fliki-current-workflow-draft";
const savedRunKey = "fliki-current-workflow-run";
const terminalStatuses = new Set(["success", "failed"]);

export default function App() {
  const [title, setTitle] = useState("我的视频草稿");
  const [script, setScript] = useState(sample);
  const [language, setLanguage] = useState("zh-CN");
  const [draft, setDraft] = useState<WorkflowDraft | null>(null);
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [outputFile, setOutputFile] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [playingVoice, setPlayingVoice] = useState("");
  const [avatarPickerScene, setAvatarPickerScene] = useState<SceneDraft | null>(null);
  const [stockUploadingScene, setStockUploadingScene] = useState<string | null>(null);
  const [stockError, setStockError] = useState("");
  const stockInputRef = useRef<HTMLInputElement | null>(null);
  const [avatarRefreshKey, setAvatarRefreshKey] = useState(0);
  // P0-2: Composer 折叠面板
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerFocusSceneId, setComposerFocusSceneId] = useState<string | null>(null);
  const [templateCatalog, setTemplateCatalog] = useState<TemplateMeta[]>(() => getTemplateCatalogSnapshot().templates);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // Composer 保存防抖: 500ms 合并连续输入, 单次 PATCH; 失败回滚
  type ComposerSaveStatus = "idle" | "saving" | "saved" | "failed";
  const [composerSaveStatus, setComposerSaveStatus] = useState<Record<string, ComposerSaveStatus>>({});
  const composerTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const composerPendingRef = useRef<Record<string, { baseline: SceneDraft; patch: Partial<SceneDraft> }>>({});
  // B-6: 任务历史
  const [runHistory, setRunHistory] = useState<WorkflowRun[]>([]);
  const [runHistoryLoading, setRunHistoryLoading] = useState(false);
  // P2-Pagination: 翻页状态
  const [runsPage, setRunsPage] = useState(1);
  const [runsHasMore, setRunsHasMore] = useState(false);
  const [runsTotal, setRunsTotal] = useState(0);
  const [runsStatusFilter, setRunsStatusFilter] = useState<string>("");
  const [historyOpen, setHistoryOpen] = useState(false);


  function rememberDraft(nextDraft: WorkflowDraft | null) {
    setDraft(nextDraft);
    if (nextDraft) localStorage.setItem(savedDraftKey, nextDraft.id);
    else localStorage.removeItem(savedDraftKey);
  }

  // P0-2-2: onFailure 可选 rollback, 让 fire-and-forget 调用方失败时回滚 UI 状态.
  async function runDraftAction(
    action: () => Promise<WorkflowDraft>,
    success: string,
    onFailure?: () => void,
  ): Promise<boolean> {
    setBusy(true);
    setMessage("");
    try {
      rememberDraft(await action());
      setMessage(success);
      return true;
    } catch (error) {
      setMessage(formatApiError(error, "操作失败"));
      if (onFailure) {
        try {
          onFailure();
        } catch (rollbackErr) {
          console.warn("runDraftAction rollback failed", rollbackErr);
        }
      }
      return false;
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const savedDraftId = localStorage.getItem(savedDraftKey);
    if (!savedDraftId) return;
    void (async () => {
      try {
        const restoredDraft = await getDraft(savedDraftId);
        rememberDraft(restoredDraft);
        const savedRunId = localStorage.getItem(savedRunKey);
        if (!savedRunId) return;
        const restoredRun = await getRun(savedRunId);
        if (restoredRun.workflow_draft_id !== restoredDraft.id) {
          localStorage.removeItem(savedRunKey);
          return;
        }
        setRun(restoredRun);
        if (restoredRun.status === "success") {
          const latest = await getRenderLatest(restoredRun.id);
          setOutputFile(latest.renderSuccess?.mediaGeneratedId?.file || null);
        }
      } catch {
        localStorage.removeItem(savedDraftKey);
        localStorage.removeItem(savedRunKey);
      }
    })();
  }, []);

  useEffect(() => {
    function receiveVoice(event: MessageEvent) {
      if (event.origin !== window.location.origin || !draft || draft.status !== "draft") return;
      const data = event.data as { type?: string; target?: string; voice?: string };
      if (data.type !== "voice_picked" || !data.target || !data.voice) return;
      const scene = draft.scenes.find((item) => item.id === data.target);
      if (!scene) return;
      void runDraftAction(
        () => updateScene(draft.id, { ...scene, voice: data.voice as string }),
        "声音已选择并保存",
      );
    }
    window.addEventListener("message", receiveVoice);
    return () => window.removeEventListener("message", receiveVoice);
  }, [draft]);

  useEffect(() => {
    function receiveTemplate(event: MessageEvent) {
      if (event.origin !== window.location.origin || !draft || draft.status !== "draft") return;
      const data = event.data as { type?: string; target?: string; template_id?: string | null; fields?: Record<string, string> | null; action?: string };
      if (data.type !== "template_picked" || !data.target) return;
      const scene = draft.scenes.find((item) => item.id === data.target);
      if (!scene) return;
      if (data.action === "clear") {
        void runDraftAction(
          () => updateScene(draft.id, { ...scene, template_id: null, template_fields: null }),
          "模板已清除",
        );
        return;
      }
      if (!data.template_id) return;
      const beforeTemplate = scene.template_id;
      const beforeFields = scene.template_fields;
      void runDraftAction(
        () => updateScene(draft.id, { ...scene, template_id: data.template_id, template_fields: data.fields || {} }),
        "模板已选择并保存",
        () => {
          const rolled = { ...scene, template_id: beforeTemplate, template_fields: beforeFields };
          rememberDraft({ ...draft, scenes: draft.scenes.map(s => s.id === scene.id ? rolled : s) });
        },
      );
    }
    window.addEventListener("message", receiveTemplate);
    return () => window.removeEventListener("message", receiveTemplate);
  }, [draft]);

  useEffect(() => {
    if (!run || terminalStatuses.has(run.status)) return;
    const timer = window.setTimeout(async () => {
      try {
        const nextRun = await getRun(run.id);
        setRun(nextRun);
        if (nextRun.status === "success") {
          const latest = await getRenderLatest(nextRun.id);
          setOutputFile(latest.renderSuccess?.mediaGeneratedId?.file || null);
          setMessage("视频生成完成");
        } else if (nextRun.status === "failed") {
          setMessage(nextRun.message || "视频生成失败");
        }
      } catch (error) {
        setMessage(formatApiError(error, "进度读取失败"));
      }
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [run]);

  // B-6: 当前 run 状态变化时刷新历史
  useEffect(() => {
    let cancelled = false;
    setRunHistoryLoading(true);
    listRunsPage(1, 10, runsStatusFilter || undefined)
      .then((page) => {
        if (cancelled) return;
        setRunHistory(page.items || []);
        setRunsPage(1);
        setRunsHasMore(page.has_more);
        setRunsTotal(page.total);
      })
      .catch(() => {
        if (cancelled) return;
        setRunHistory([]);
        setRunsHasMore(false);
        setRunsTotal(0);
      })
      .finally(() => { if (!cancelled) setRunHistoryLoading(false); });
    return () => { cancelled = true; };
  }, [run?.status, runsStatusFilter]);

  // P2-Pagination: 加载下一页 runs
  async function loadMoreRuns() {
    if (!runsHasMore || runHistoryLoading) return;
    setRunHistoryLoading(true);
    try {
      const next = runsPage + 1;
      const page = await listRunsPage(next, 10, runsStatusFilter || undefined);
      setRunHistory((prev) => [...prev, ...(page.items || [])]);
      setRunsPage(next);
      setRunsHasMore(page.has_more);
      setRunsTotal(page.total);
    } catch (e) {
      setMessage(formatApiError(e, "加载更多失败"));
    } finally {
      setRunHistoryLoading(false);
    }
  }

  // 拉一次确保 avatar clone 列表变化时 picker 也能刷新（无副作用）
  useEffect(() => { void listAvatarClones().catch(() => undefined); }, [avatarRefreshKey]);

  useEffect(() => {
    const unsubscribe = subscribeTemplateCache((snapshot) => {
      setTemplateCatalog(snapshot.templates);
    });
    loadTemplateCatalogWithRetry();
    return unsubscribe;
  }, []);

  function changeScene(id: string, field: keyof SceneDraft, value: string | number | null) {
    setDraft((current) => current ? {
      ...current,
      scenes: current.scenes.map((scene) => scene.id === id ? { ...scene, [field]: value } : scene),
    } : current);
  }

  async function move(index: number, direction: -1 | 1) {
    if (!draft) return;
    const target = index + direction;
    if (target < 0 || target >= draft.scenes.length) return;
    const ids = draft.scenes.map((scene) => scene.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    await runDraftAction(() => reorderScenes(draft.id, ids), "顺序已保存");
  }

  // P0-2: Composer 拖拽重排
  async function composerReorder(fromIndex: number, toIndex: number) {
    if (!draft) return;
    if (fromIndex < 0 || toIndex < 0 || fromIndex >= draft.scenes.length || toIndex >= draft.scenes.length) return;
    const ids = draft.scenes.map((scene) => scene.id);
    const [moved] = ids.splice(fromIndex, 1);
    ids.splice(toIndex, 0, moved);
    await runDraftAction(() => reorderScenes(draft.id, ids), "顺序已保存");
  }

  // Composer 编辑带防抖: 乐观更新 UI, 500ms 内连续输入合并成一次 PATCH; 失败回滚到 baseline
  function flushComposerPatch(sceneId: string) {
    const pending = composerPendingRef.current[sceneId];
    delete composerPendingRef.current[sceneId];
    delete composerTimersRef.current[sceneId];
    if (!pending || !draft) return;
    const merged = { ...pending.baseline, ...pending.patch };
    setBusy(true);
    updateScene(draft.id, merged)
      .then((nextDraft) => {
        rememberDraft(nextDraft);
        setMessage("场景设置已保存");
        setComposerSaveStatus((prev) => ({ ...prev, [sceneId]: "saved" }));
      })
      .catch((error) => {
        // 回滚到 baseline, 不依赖 runDraftAction 传播失败
        setDraft((current) => current ? {
          ...current,
          scenes: current.scenes.map((item) => item.id === sceneId ? pending.baseline : item),
        } : current);
        setComposerSaveStatus((prev) => ({ ...prev, [sceneId]: "failed" }));
        setMessage(formatApiError(error, "场景设置保存失败"));
      })
      .finally(() => setBusy(false));
  }
  function composerPatchScene(scene: SceneDraft, patch: Partial<SceneDraft>) {
    if (!draft) return;
    // 1. 乐观更新 UI
    const nextScene = { ...scene, ...patch };
    setDraft((current) => current ? {
      ...current,
      scenes: current.scenes.map((item) => item.id === scene.id ? nextScene : item),
    } : current);
    // 2. 合并到 pending (用 baseline 作为回滚锚点)
    const existing = composerPendingRef.current[scene.id];
    composerPendingRef.current[scene.id] = {
      baseline: existing ? existing.baseline : scene,
      patch: { ...(existing ? existing.patch : {}), ...patch },
    };
    // 3. 标记 saving + 安排防抖
    setComposerSaveStatus((prev) => ({ ...prev, [scene.id]: "saving" }));
    const timer = composerTimersRef.current[scene.id];
    if (timer) clearTimeout(timer);
    composerTimersRef.current[scene.id] = setTimeout(() => flushComposerPatch(scene.id), 500);
  }

  function composerApplyTemplate(scene: SceneDraft, template: TemplateMeta) {
    if (!draft) return;
    const templateFields = Object.fromEntries((template.fields || []).map((field) => {
      if (field.default != null && String(field.default) !== "") return [field.key, field.default];
      if (field.key.includes("title")) return [field.key, scene.title];
      if (field.key.includes("desc") || field.key === "description") return [field.key, scene.subtitle_display || scene.subtitle];
      if (field.key === "quote") return [field.key, scene.subtitle_display || scene.narration];
      if (field.key === "author") return [field.key, "视频作者"];
      if (field.required) return [field.key, scene.title];
      return [field.key, ""];
    }));
    const nextScene = { ...scene, template_id: template.id, template_fields: templateFields };
    void runDraftAction(
      () => updateScene(draft.id, nextScene),
      "已把“" + template.name + "”套用到 " + scene.title,
      () => rememberDraft(draft),
    );
  }

  function chooseVoice(scene: SceneDraft) {
    const query = new URLSearchParams({ target: scene.id, current: scene.voice, locale: draft?.language || "" });
    window.open("/voices.html?" + query.toString(), "voice_picker", "width=1200,height=800");
  }

  function chooseTemplate(scene: SceneDraft) {
    const query = new URLSearchParams({ target: scene.id, current: scene.template_id || "" });
    window.open("/templates.html?" + query.toString(), "template_picker", "width=1200,height=800");
  }

  function clearTemplate(scene: SceneDraft) {
    if (!draft) return;
    void runDraftAction(() => updateScene(draft.id, { ...scene, template_id: null, template_fields: null }), "模板已清除");
  }

  // P2: 草稿"复制为模板" — 调后端 /templates/from-draft/{draft_id}?scene_id=xxx, 自管 busy + message (无 401 重试)
  async function copyAsTemplate(scene: SceneDraft) {
    if (!draft) return;
    setBusy(true);
    setMessage("");
    try {
      const newTemplate = await copyDraftAsTemplate(draft.id, scene.id);
      setMessage("已复制为模板: " + (newTemplate.name || newTemplate.id));
    } catch (error) {
      setMessage(formatApiError(error, "复制为模板失败"));
    } finally {
      setBusy(false);
    }
  }

  function chooseAvatar(scene: SceneDraft) {
    setAvatarPickerScene(scene);
  }

  async function pickAvatar(value: string | null) {
    if (!avatarPickerScene || !draft) return;
    const scene = avatarPickerScene;
    setAvatarPickerScene(null);
    if (value === null) {
      await runDraftAction(() => updateScene(draft.id, { ...scene, avatar: null }), "Avatar 已清除");
      return;
    }
    await runDraftAction(() => updateScene(draft.id, { ...scene, avatar: value }), "Avatar 已选择并保存");
  }

  function clearAvatar(scene: SceneDraft) {
    void runDraftAction(() => updateScene(draft!.id, { ...scene, avatar: null }), "Avatar 已清除");
  }

  function shortAvatar(token: string | null | undefined): string {
    if (!token) return "";
    if (token.startsWith("avatar:")) return token.slice("avatar:".length, "avatar:".length + 8);
    return token.slice(0, 12);
  }

  async function onStockPicked(scene: SceneDraft, e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f || !draft) return;
    setStockUploadingScene(scene.id);
    setStockError("");
    try {
      const up = await uploadLocalFile(f);
      await runDraftAction(() => updateScene(draft.id, { ...scene, stock_url: up.url }), "Stock 已上传");
    } catch (err) {
      setStockError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setStockUploadingScene(null);
      if (e.target) e.target.value = "";
    }
  }
  function clearStock(scene: SceneDraft) {
    if (!draft) return;
    void runDraftAction(() => updateScene(draft.id, { ...scene, stock_url: null }), "Stock 已清除");
  }

  async function playVoice(scene: SceneDraft) {
    setPlayingVoice(scene.voice);
    try {
      const audioUrl = scene.voice.startsWith("clone:")
        ? (await previewCloneVoice(scene.voice.slice("clone:".length))).preview_url
        : (await previewVoice(scene.voice, scene.narration.slice(0, 120) || "你好，这是声音试听。")).audio_url;
      audioRef.current?.pause();
      const audio = new Audio(apiAssetUrl(audioUrl) + "?v=" + Date.now());
      audioRef.current = audio;
      audio.onended = () => setPlayingVoice("");
      await audio.play();
    } catch (error) {
      setPlayingVoice("");
      setMessage(formatApiError(error, "试听失败"));
    }
  }

  async function rerenderOnly() {
    if (!run) return;
    setBusy(true);
    setMessage("");
    setOutputFile(null);
    try {
      const nextRun = await rerenderRun(run.id);
      setRun(nextRun);
      localStorage.setItem(savedRunKey, nextRun.id);
      setMessage("已重新渲染（复用素材）");
    } catch (error) {
      setMessage(formatApiError(error, "重新渲染失败"));
    } finally {
      setBusy(false);
    }
  }

  async function startGeneration() {
    if (!draft) return;
    setBusy(true);
    setMessage("");
    setOutputFile(null);
    try {
      const nextRun = run?.status === "failed" ? await retryRun(run.id) : await createRun(draft.id, run?.status === "success");
      setRun(nextRun);
      localStorage.setItem(savedRunKey, nextRun.id);
      if (nextRun.status === "success") {
        const latest = await getRenderLatest(nextRun.id);
        setOutputFile(latest.renderSuccess?.mediaGeneratedId?.file || null);
        setMessage("视频已生成");
      } else {
        setMessage(run?.status === "failed" ? "正在重试失败节点，已成功节点将复用" : run?.status === "success" ? "已开始重新生成视频" : "已开始生成素材、配音、音乐和视频");
      }
    } catch (error) {
      setMessage(formatApiError(error, "启动生成失败"));
    } finally {
      setBusy(false);
    }
  }

  async function confirmAndContinue() {
    if (!draft) return;
    await runDraftAction(() => confirmDraft(draft.id), "草稿已确认，开始生成");
  }

  function resetDraft() {
    if (!window.confirm("新建草稿将清空当前所有内容，确定？")) return;
    localStorage.removeItem(savedDraftKey);
    localStorage.removeItem(savedRunKey);
    setRun(null);
    setOutputFile(null);
    setComposerFocusSceneId(null);
    setDraft(null);
  }

  const templateLookup = new Map<string, TemplateMeta>(templateCatalog.map((template) => [template.id, template]));
  const nextTemplateGap = draft ? findNextIncompleteScene(draft.scenes, templateLookup) : null;
  const incompleteTemplateSceneCount = draft
    ? draft.scenes.filter((scene) => {
      const completion = computeTemplateCompletion(scene, templateLookup);
      return Boolean(scene.template_id && !completion.isComplete);
    }).length
    : 0;

  return (
    <main>
      {!draft && (
        <section className="creator">
          <span className="eyebrow">CREATE</span>
          <h1>让脚本先变成可编辑的草稿</h1>
          <p>粘贴或撰写一段文字脚本，AI 会自动拆分成场景，每个场景都可以独立调整旁白、声音、画面、字幕和时长。</p>
          <label>视频标题<input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
          <label>语言<input value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="zh-CN" /></label>
          <label>脚本<textarea rows={10} value={script} onChange={(e) => setScript(e.target.value)} /></label>
          <div className="creatorFoot">
            <span>确认后系统会开始调用素材、配音、音乐和渲染。</span>
            <button disabled={busy} onClick={async () => {
              setBusy(true);
              try {
                rememberDraft(await createDraft(script, title, language));
                setMessage("草稿已生成");
              } catch (e) {
                setMessage(e instanceof Error ? e.message : "草稿生成失败");
              } finally {
                setBusy(false);
              }
            }}>生成草稿</button>
          </div>
        </section>
      )}
      {draft && (
        <section className="workspace">
          <div className="toolbar">
            <div>
              <span className="eyebrow">DRAFT</span>
              <h2>{draft.title} <span className={"status " + draft.status}>{draft.status}</span></h2>
            </div>
            {draft.status === "draft" ? <button className="confirm" disabled={busy} onClick={async () => {
              try { await confirmAndContinue(); } catch {}
            }}>确认草稿</button> : (<>
              <button className="confirm" disabled={busy || (!!run && !terminalStatuses.has(run.status))} onClick={startGeneration}>{run?.status === "failed" ? "重试失败任务" : run?.status === "success" ? "重新生成视频" : "生成视频"}</button>
              <button className="textButton" type="button" disabled={busy || (!!run && !terminalStatuses.has(run.status))} onClick={rerenderOnly}>仅重新渲染</button>
            </>)}
            <button className="textButton" type="button" onClick={resetDraft}>新建草稿</button>
            <button className="textButton" type="button" onClick={() => setComposerOpen((v) => {
              if (v) setComposerFocusSceneId(null);
              return !v;
            })}>{composerOpen ? "收起 Composer" : "🎬 展开 Composer"}</button>
            {incompleteTemplateSceneCount > 0 && nextTemplateGap && (
              <button
                className="textButton templateCompleteButton"
                type="button"
                data-testid="global-template-complete"
                onClick={() => {
                  setComposerFocusSceneId(nextTemplateGap.sceneId);
                  setComposerOpen(true);
                }}
              >📋 模板补完 ({incompleteTemplateSceneCount})</button>
            )}
            <button className="textButton" type="button" onClick={() => setHistoryOpen((v) => !v)}>{historyOpen ? "收起历史" : "📜 历史"}</button>
            <button className="textButton" type="button" disabled={busy || draft.status !== "draft" || draft.scenes.length >= 50} onClick={async () => {
              if (!draft) return;
              try { rememberDraft(await addScene(draft.id)); setMessage("已新增场景"); } catch (e) { setMessage(e instanceof Error ? e.message : "新增失败"); }
            }}>+ 新增场景</button>
          </div>
          <div className="sceneList">{draft.scenes.map((scene, index) => (
            <article className="scene" key={scene.id}>
              <div className="sceneNumber">{String(index + 1).padStart(2, "0")}</div>
              <div className="sceneBody">
                <div className="sceneTop">
                  <input className="sceneTitle" disabled={draft.status !== "draft"} value={scene.title} onChange={(event) => changeScene(scene.id, "title", event.target.value)} />
                  <div className="actions">
                    <button disabled={index === 0 || busy || draft.status !== "draft"} onClick={() => move(index, -1)}>上移</button>
                    <button disabled={index === draft.scenes.length - 1 || busy || draft.status !== "draft"} onClick={() => move(index, 1)}>下移</button>
                    <button disabled={draft.status !== "draft" || busy || draft.scenes.length === 1} onClick={() => runDraftAction(() => deleteScene(draft.id, scene.id), "场景已删除")}>删除</button>
                  </div>
                </div>
                <div className="grid">
                  <label>旁白<textarea disabled={draft.status !== "draft"} value={scene.narration} onChange={(event) => changeScene(scene.id, "narration", event.target.value)} /></label>
                  <label>画面意图<textarea disabled={draft.status !== "draft"} value={scene.visual_intent} onChange={(event) => changeScene(scene.id, "visual_intent", event.target.value)} /></label>
                  <label>字幕<textarea disabled={draft.status !== "draft"} value={scene.subtitle} onChange={(event) => changeScene(scene.id, "subtitle", event.target.value)} /></label>
                  <label className="duration">预计时长（秒）<input type="number" min="0.5" step="0.5" disabled={draft.status !== "draft"} value={scene.duration_seconds} onChange={(event) => changeScene(scene.id, "duration_seconds", Number(event.target.value))} /></label>
                  <label className="cameraMotion">运镜<select disabled={draft.status !== "draft"} value={scene.camera_motion || "zoom-in"} onChange={(event) => changeScene(scene.id, "camera_motion", event.target.value)}><option value="zoom-in">推近</option><option value="zoom-out">拉远</option><option value="pan-left">向左平移</option><option value="pan-right">向右平移</option><option value="pan-up">向上平移</option><option value="pan-down">向下平移</option><option value="none">无运镜</option></select></label>
                  <label className="voiceField">配音声音<div className="voiceRow"><input disabled={draft.status !== "draft"} value={scene.voice} onChange={(event) => changeScene(scene.id, "voice", event.target.value)} /><button type="button" disabled={playingVoice === scene.voice} onClick={() => playVoice(scene)}>{playingVoice === scene.voice ? "播放中" : "🎤 试听"}</button><button type="button" disabled={draft.status !== "draft"} onClick={() => chooseVoice(scene)}>更换</button></div></label>
                  <label className="avatarField">数字人 Avatar<div className="avatarRow"><input disabled readOnly value={scene.avatar || ""} placeholder="未选择（不调用数字人）" /><button type="button" disabled={draft.status !== "draft"} onClick={() => chooseAvatar(scene)}>{scene.avatar ? "更换 Avatar" : "选择 Avatar"}</button>{scene.avatar && draft.status === "draft" && <button type="button" className="secondary" onClick={() => clearAvatar(scene)}>清除</button>}<span className="avatarHint" title={scene.avatar || ""}>{scene.avatar ? `已选 ${shortAvatar(scene.avatar)}` : "保持纯旁白"}</span></div></label>
                  <label className="templateField">视频模板<div className="templateRow"><input disabled readOnly value={scene.template_id || ""} placeholder="未选模板（按 narration 渲染）" /><button type="button" disabled={draft.status !== "draft"} onClick={() => chooseTemplate(scene)}>{scene.template_id ? "更换模板" : "🧩 选模板"}</button>{scene.template_id && draft.status === "draft" && <button type="button" className="secondary" onClick={() => clearTemplate(scene)}>清除</button>}<span className="templateHint" title={scene.template_id || ""}>{scene.template_id ? `已选 ${scene.template_id}（${Object.keys(scene.template_fields || {}).length} 字段）` : "保持默认画面"}</span></div></label>
                    <label className="stockField">本地上传素材<div className="stockRow">{scene.stock_url ? (<><video className="stockPreview" src={fullUploadUrl(scene.stock_url)} muted playsInline preload="metadata" /><input disabled readOnly value={scene.stock_url} title={scene.stock_url} /></>) : (<input disabled readOnly value="" placeholder="未上传（默认走 Pexels/Pixabay）" />)}<button type="button" disabled={draft.status !== "draft" || stockUploadingScene === scene.id} onClick={() => stockInputRef.current?.click()}>{stockUploadingScene === scene.id ? "上传中…" : scene.stock_url ? "🔄 替换" : "📤 上传"}</button><input ref={stockInputRef} type="file" accept="video/mp4,video/quicktime,video/webm,image/png,image/jpeg" hidden onChange={(e) => onStockPicked(scene, e)} />{scene.stock_url && draft.status === "draft" && <button type="button" className="secondary" onClick={() => clearStock(scene)}>清除</button>}<span className="stockHint" title={scene.stock_url || ""}>{scene.stock_url ? `已选 ${scene.stock_url.split("/").pop()}` : "保持默认搜索"}</span>{stockError && <span className="error">{stockError}</span>}</div></label>
                </div>
                {draft.status === "draft" && <button className="save" disabled={busy} onClick={() => runDraftAction(() => updateScene(draft.id, scene), "场景 " + (index + 1) + " 已保存")}>保存场景</button>}
              </div>
            </article>
          ))}</div>
          {composerOpen && draft && (
            <Composer
              scenes={draft.scenes}
              onReorder={composerReorder}
              onPickTemplate={chooseTemplate}
              onClearTemplate={clearTemplate}
              onCopyAsTemplate={copyAsTemplate}
              onUpdateScene={composerPatchScene}
              onApplyTemplate={composerApplyTemplate}
              saveStatusByScene={composerSaveStatus}
              disabled={draft.status !== "draft"}
              focusSceneId={composerFocusSceneId}
            />
          )}
        </section>
      )}

{historyOpen && (
        <section className="runHistory">
          <div className="runHistoryHead">
            <span className="eyebrow">HISTORY</span>
            <h3>最近任务（{runHistory.length} / 共 {runsTotal}）{runHistoryLoading ? " 加载中…" : ""}</h3>
            <select
              aria-label="状态过滤"
              data-testid="run-status-filter"
              value={runsStatusFilter}
              onChange={(e) => setRunsStatusFilter(e.target.value)}
              disabled={runHistoryLoading}
            >
              <option value="">全部</option>
              <option value="queued">queued</option>
              <option value="running">running</option>
              <option value="success">success</option>
              <option value="failed">failed</option>
            </select>
          </div>
          {runHistory.length === 0 ? (
            <p className="empty">暂无历史任务。生成视频后此处会列出最近 10 次。</p>
          ) : (
            <>
            <ul className="runHistoryList">
              {runHistory.map((row) => (
                <li className={"runHistoryItem status-" + row.status} key={row.id}>
                  <div className="runHistoryId">
                    <code>{row.id.slice(0, 8)}</code>
                    <span className="runHistoryDraft">draft {row.workflow_draft_id.slice(0, 8)}</span>
                  </div>
                  <div className="runHistoryMeta">
                    <span className={"status " + row.status}>{row.status}</span>
                    <span className="progress">{row.progress}%</span>
                    <span className="time">{row.created_at.replace("T", " ").slice(0, 19)}</span>
                  </div>
                  <div className="runHistoryActions">
                    <button type="button" disabled={busy} onClick={async () => {
                      try { setRun(await getRun(row.id)); setMessage("已打开历史任务"); localStorage.setItem(savedRunKey, row.id); }
                      catch (e) { setMessage(formatApiError(e, "打开失败")); }
                    }}>打开</button>
                    {row.status === "success" && (
                      <button type="button" disabled={busy} onClick={async () => {
                        try { const latest = await getRenderLatest(row.id); setOutputFile(latest.renderSuccess?.mediaGeneratedId?.file || null); setRun(await getRun(row.id)); setMessage("已加载历史任务视频"); }
                        catch (e) { setMessage(formatApiError(e, "加载视频失败")); }
                      }}>下载视频</button>
                    )}
                    {row.status === "failed" && (
                      <button type="button" disabled={busy} onClick={async () => {
                        try { setRun(await retryRun(row.id)); setMessage("已重新入队失败任务"); }
                        catch (e) { setMessage(formatApiError(e, "重试失败")); }
                      }}>重试</button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            {runsHasMore && (
              <button
                type="button"
                className="runHistoryLoadMore"
                data-testid="run-load-more"
                disabled={runHistoryLoading}
                onClick={() => loadMoreRuns().catch((e) => setMessage(formatApiError(e, "加载更多失败")))}
              >
                {runHistoryLoading ? "加载中…" : "加载更多"}
              </button>
            )}
            </>
          )}
        </section>
      )}
      {run && (
        <section className="runPanel">
          <div className="runHeading"><div><span className="eyebrow">GENERATION</span><h2>生成进度</h2></div><strong>{run.status} · {run.progress}%</strong></div>
          <progress value={run.progress} max={100} />
          <div className="nodes">{run.nodes.map((node) => (
            <div className={"node " + node.status} key={node.id}>
              <span>{node.node_type}</span>
              <span>{node.provider || "等待"}</span>
              <strong>{node.status}</strong>
            </div>
          ))}</div>
          {run.message && <p className="error">{run.message}</p>}
          {outputFile && <div className="result"><video controls src={outputUrl(outputFile)} /><a href={outputUrl(outputFile)} target="_blank" rel="noreferrer">打开生成视频</a></div>}
        </section>
      )}

      <AvatarPicker
        open={!!avatarPickerScene}
        current={avatarPickerScene?.avatar ?? null}
        onPick={pickAvatar}
        onClose={() => setAvatarPickerScene(null)}
        onAfterChange={() => setAvatarRefreshKey((k) => k + 1)}
      />
      <Toast message={message} />
    </main>
  );
}