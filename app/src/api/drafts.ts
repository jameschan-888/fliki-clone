import type { RenderLatest, SceneDraft, WorkflowDraft, WorkflowRun } from "../types/draft";

export const API = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ message: "请求失败" }));
    throw new Error(body.message || body.detail || "请求失败");
  }
  return response.json();
}

export const createDraft = (sourceScript: string, title: string, language: string) =>
  request<WorkflowDraft>("/workflow-drafts", {
    method: "POST",
    body: JSON.stringify({ source_script: sourceScript, title, language }),
  });

export const getDraft = (draftId: string) =>
  request<WorkflowDraft>("/workflow-drafts/" + encodeURIComponent(draftId));

export const updateScene = (draftId: string, scene: SceneDraft) =>
  request<WorkflowDraft>("/workflow-drafts/" + encodeURIComponent(draftId) + "/scenes/" + encodeURIComponent(scene.id), {
    method: "PATCH",
    body: JSON.stringify({
      title: scene.title,
      narration: scene.narration,
      visual_intent: scene.visual_intent,
      subtitle: scene.subtitle,
      duration_seconds: scene.duration_seconds,
      voice: scene.voice,
      avatar: scene.avatar ?? null,
      avatar_layout: scene.avatar_layout ?? undefined,
    }),
  });

export const reorderScenes = (draftId: string, sceneIds: string[]) =>
  request<WorkflowDraft>("/workflow-drafts/" + encodeURIComponent(draftId) + "/reorder", {
    method: "POST",
    body: JSON.stringify({ scene_ids: sceneIds }),
  });

export const addScene = (draftId: string) =>
  request<WorkflowDraft>("/workflow-drafts/" + encodeURIComponent(draftId) + "/scenes", {
    method: "POST",
    body: JSON.stringify({
      title: "新场景",
      narration: "请输入旁白",
      visual_intent: "请输入画面意图",
      voice: "zh-CN-XiaoxiaoNeural",
      avatar: null,
    }),
  });

export const deleteScene = (draftId: string, sceneId: string) =>
  request<WorkflowDraft>("/workflow-drafts/" + encodeURIComponent(draftId) + "/scenes/" + encodeURIComponent(sceneId), {
    method: "DELETE",
  });

export const confirmDraft = (draftId: string) =>
  request<WorkflowDraft>("/workflow-drafts/" + encodeURIComponent(draftId) + "/confirm", { method: "POST" });

export const createRun = (draftId: string) =>
  request<WorkflowRun>("/workflow-runs/from-draft/" + encodeURIComponent(draftId), { method: "POST" });

export const getRun = (runId: string) =>
  request<WorkflowRun>("/workflow-runs/" + encodeURIComponent(runId));

export const retryRun = (runId: string) =>
  request<WorkflowRun>("/workflow-runs/" + encodeURIComponent(runId) + "/retry", { method: "POST" });

export const getRenderLatest = (runId: string) =>
  request<RenderLatest>("/render.latest?playback_id=" + encodeURIComponent("workflow-" + runId));

export const previewVoice = (voice: string, text: string) =>
  request<{ audio_url: string }>("/voices/" + encodeURIComponent(voice) + "/preview?text=" + encodeURIComponent(text));

export const previewCloneVoice = (uuid: string) =>
  request<{ preview_url: string }>("/voice-clones/" + encodeURIComponent(uuid) + "/preview", { method: "POST" });

export const listAvatarClones = () =>
  request<Array<{ uuid: string; avatar_name: string; ref_face_path: string; enabled: boolean }>>("/avatar-clones");

export const previewAvatarUrl = (uuid: string) => API + "/avatar-clones/" + encodeURIComponent(uuid) + "/ref-face";

export const previewAudioUrl = (path: string) => API + path;

export const apiAssetUrl = (path: string) => API + path;

export const outputUrl = (file: string) =>
  API + "/outputs/" + file.split("/").map(encodeURIComponent).join("/");
