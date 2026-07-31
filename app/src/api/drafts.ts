import type { RenderLatest, SceneDraft, WorkflowDraft, WorkflowRun } from "../types/draft";

export const API = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5181").replace(/\/$/, "");

export type ApiError = {
  status: number;
  error_code?: string;
  message: string;
  hint: string;
  details: Record<string, unknown>;
};

export type TemplateField = {
  key: string;
  type?: string;
  label?: string;
  required?: boolean;
  default?: string | number | null;
  max_length?: number;
  pattern?: string;
  help?: string;
};

export type TemplateMeta = {
  id: string;
  name: string;
  category: string;
  description: string;
  builtin: boolean;
  enabled: boolean;
  created_at?: string;
  fields?: TemplateField[];
  structure?: Record<string, unknown>;
};

export type TemplateCategory = {
  category: string;
  count: number;
};

export function formatApiError(error: unknown, fallback: string): string {
  if (error == null) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message || fallback;
  if (typeof error === "object") {
    const e = error as Partial<ApiError> & { detail?: unknown };
    const message = e.message || (typeof e.detail === "string" ? e.detail : "");
    if (!message) return fallback;
    return e.hint ? `${message}（${e.hint}）` : message;
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string> | undefined) };
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!isFormData && init?.body && typeof init.body === "string" && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const r = await fetch(API + path, { ...init, headers });
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    const enriched: ApiError = {
      status: r.status,
      error_code: body?.error_code,
      message: body?.message || body?.detail || "请求失败",
      hint: body?.hint || "",
      details: body?.details || {},
    };
    throw enriched;
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
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
    body: JSON.stringify(scene),
  });

export const reorderScenes = (draftId: string, sceneIds: string[]) =>
  request<WorkflowDraft>("/workflow-drafts/" + encodeURIComponent(draftId) + "/scenes/reorder", {
    method: "POST",
    body: JSON.stringify({ scene_ids: sceneIds }),
  });

export const addScene = (draftId: string) =>
  request<WorkflowDraft>("/workflow-drafts/" + encodeURIComponent(draftId) + "/scenes", { method: "POST" });

export const deleteScene = (draftId: string, sceneId: string) =>
  request<WorkflowDraft>("/workflow-drafts/" + encodeURIComponent(draftId) + "/scenes/" + encodeURIComponent(sceneId), {
    method: "DELETE",
  });

export const confirmDraft = (draftId: string) =>
  request<WorkflowDraft>("/workflow-drafts/" + encodeURIComponent(draftId) + "/confirm", { method: "POST" });

export const createRun = (draftId: string, force = false) =>
  request<WorkflowRun>("/workflow-runs/from-draft/" + encodeURIComponent(draftId) + (force ? "?force=true" : ""), { method: "POST" });

export const getRun = (runId: string) =>
  request<WorkflowRun>("/workflow-runs/" + encodeURIComponent(runId));

export type RunListPage = {
  items: WorkflowRun[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
};

export const listRuns = (limit = 20) =>
  request<WorkflowRun[]>("/workflow-runs?limit=" + encodeURIComponent(String(limit)));

// P2-Pagination: listRunsPage 返 wrapper {items, total, page, limit, has_more}
// 后端 page>=1 走 wrapper; page=0 走 list 向后兼容
export const listRunsPage = (page: number, limit = 10, status?: string) => {
  const params = new URLSearchParams({ page: String(Math.max(1, page)), limit: String(limit) });
  if (status) params.set("status", status);
  return request<RunListPage>("/workflow-runs?" + params.toString());
};

export const retryRun = (runId: string) =>
  request<WorkflowRun>("/workflow-runs/" + encodeURIComponent(runId) + "/retry", { method: "POST" });

export const rerenderRun = (runId: string) =>
  request<WorkflowRun>("/workflow-runs/" + encodeURIComponent(runId) + "/rerender", { method: "POST" });

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

export const fullUploadUrl = (path: string) => API + path;

export const uploadLocalFile = (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return request<{ id: string; url: string; filename: string; size_bytes: number }>("/api/uploads", {
    method: "POST",
    body: fd,
  });
};

export const listTemplates = (enabledOnly = true, includeConfig = true) =>
  request<TemplateMeta[]>("/templates?enabled_only=" + (enabledOnly ? "true" : "false") + (includeConfig ? "&include_config=true" : ""));

export const listTemplateCategories = () =>
  request<TemplateCategory[]>("/templates/categories");

export const deleteAvatarClone = (uuid: string) =>
  request("/avatar-clones/" + encodeURIComponent(uuid), { method: "DELETE" });

export const copyDraftAsTemplate = (draftId: string, sceneId?: string) =>
  request<{ id: string; name: string }>("/workflow-drafts/" + encodeURIComponent(draftId) + "/copy-as-template", {
    method: "POST",
    body: sceneId ? JSON.stringify({ scene_id: sceneId }) : undefined,
  });

export type AvatarMetaPatch = { avatar_name?: string; enabled?: boolean };

export const updateAvatarMeta = (uuid: string, patch: AvatarMetaPatch) =>
  request<{ uuid: string; avatar_name: string; enabled: boolean }>("/avatar-clones/" + encodeURIComponent(uuid), {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const uploadAvatarFace = (uuid: string, file: File) => {
  const fd = new FormData(); fd.append("file", file);
  return request<{ ref_face_path: string }>("/avatar-clones/" + encodeURIComponent(uuid) + "/ref-face", {
    method: "POST",
    body: fd,
  });
};

export const uploadAvatarAudio = (uuid: string, file: File) => {
  const fd = new FormData(); fd.append("file", file);
  return request<{ ref_audio_path: string }>("/avatar-clones/" + encodeURIComponent(uuid) + "/ref-audio", {
    method: "POST",
    body: fd,
  });
};