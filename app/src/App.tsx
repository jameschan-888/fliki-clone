import { useEffect, useRef, useState } from "react";
import type { SceneDraft, WorkflowDraft, WorkflowRun } from "./types/draft";
import { AvatarPicker } from "./components/editor/AvatarPicker";
import { Toast } from "./components/ui/Toast";
import {
  addScene,
  apiAssetUrl,
  confirmDraft,
  createDraft,
  createRun,
  deleteScene,
  getDraft,
  getRenderLatest,
  getRun,
  listAvatarClones,
  outputUrl,
  previewVoice,
  previewCloneVoice,
  reorderScenes,
  retryRun,
  updateScene,
} from "./api/drafts";

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
  const [avatarRefreshKey, setAvatarRefreshKey] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  function rememberDraft(nextDraft: WorkflowDraft | null) {
    setDraft(nextDraft);
    if (nextDraft) localStorage.setItem(savedDraftKey, nextDraft.id);
    else localStorage.removeItem(savedDraftKey);
  }

  async function runDraftAction(action: () => Promise<WorkflowDraft>, success: string) {
    setBusy(true);
    setMessage("");
    try {
      rememberDraft(await action());
      setMessage(success);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败");
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
        setMessage(error instanceof Error ? error.message : "进度读取失败");
      }
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [run]);

  // 拉一次确保 avatar clone 列表变化时 picker 也能刷新（无副作用）
  useEffect(() => { void listAvatarClones().catch(() => undefined); }, [avatarRefreshKey]);

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

  function chooseVoice(scene: SceneDraft) {
    const query = new URLSearchParams({ target: scene.id, current: scene.voice, locale: draft?.language || "" });
    window.open("/voices.html?" + query.toString(), "voice_picker", "width=1200,height=800");
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
      setMessage(error instanceof Error ? error.message : "试听失败");
    }
  }

  async function startGeneration() {
    if (!draft) return;
    setBusy(true);
    setMessage("");
    setOutputFile(null);
    try {
      const nextRun = run?.status === "failed" ? await retryRun(run.id) : await createRun(draft.id);
      setRun(nextRun);
      localStorage.setItem(savedRunKey, nextRun.id);
      if (nextRun.status === "success") {
        const latest = await getRenderLatest(nextRun.id);
        setOutputFile(latest.renderSuccess?.mediaGeneratedId?.file || null);
        setMessage("视频已生成");
      } else {
        setMessage(run?.status === "failed" ? "正在重试失败节点，已成功节点将复用" : "已开始生成素材、配音、音乐和视频");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "启动生成失败");
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
    setDraft(null);
  }

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
            }}>确认草稿</button> : <button className="confirm" disabled={busy || (!!run && !terminalStatuses.has(run.status))} onClick={startGeneration}>{run?.status === "failed" ? "重试失败任务" : "生成视频"}</button>}
            <button className="textButton" type="button" onClick={resetDraft}>新建草稿</button>
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
                  <label className="voiceField">配音声音<div className="voiceRow"><input disabled={draft.status !== "draft"} value={scene.voice} onChange={(event) => changeScene(scene.id, "voice", event.target.value)} /><button type="button" disabled={playingVoice === scene.voice} onClick={() => playVoice(scene)}>{playingVoice === scene.voice ? "播放中" : "🎤 试听"}</button><button type="button" disabled={draft.status !== "draft"} onClick={() => chooseVoice(scene)}>更换</button></div></label>
                  <label className="avatarField">数字人 Avatar<div className="avatarRow"><input disabled readOnly value={scene.avatar || ""} placeholder="未选择（不调用数字人）" /><button type="button" disabled={draft.status !== "draft"} onClick={() => chooseAvatar(scene)}>{scene.avatar ? "更换 Avatar" : "选择 Avatar"}</button>{scene.avatar && draft.status === "draft" && <button type="button" className="secondary" onClick={() => clearAvatar(scene)}>清除</button>}<span className="avatarHint" title={scene.avatar || ""}>{scene.avatar ? `已选 ${shortAvatar(scene.avatar)}` : "保持纯旁白"}</span></div></label>
                </div>
                {draft.status === "draft" && <button className="save" disabled={busy} onClick={() => runDraftAction(() => updateScene(draft.id, scene), "场景 " + (index + 1) + " 已保存")}>保存场景</button>}
              </div>
            </article>
          ))}</div>
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