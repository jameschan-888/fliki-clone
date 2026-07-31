import type {
  AutoEditDraft,
  AutoEditRun,
  AutoEditUpload,
  SegmentPatchInput,
} from "../types/autoedit";
import { API, formatApiError } from "./drafts";
import type { ApiError } from "./drafts";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
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
  return r.json();
}

// 上传 (multipart, 走 XHR 拿进度)
export function uploadVideoXhr(
  file: File,
  onProgress: (loaded: number, total: number) => void,
): Promise<AutoEditUpload> {
  return new Promise((resolve, reject) => {
    const fd = new FormData();
    fd.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", API + "/autoedit/uploads");
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded, event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject({ status: xhr.status, message: "上传响应解析失败", hint: "", details: {} });
        }
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject({
            status: xhr.status,
            message: body?.message || body?.detail || "上传失败",
            hint: body?.hint || "",
            details: body?.details || {},
          });
        } catch {
          reject({ status: xhr.status, message: "上传失败", hint: "", details: {} });
        }
      }
    };
    xhr.onerror = () =>
      reject({ status: 0, message: "网络错误", hint: "检查网络/后端", details: {} });
    xhr.send(fd);
  });
}

// 把 ApiError / Error / string 翻译成中文 (复用 drafts 的 helper)
export { formatApiError };

export const createDraftFromUpload = (uploadId: string, language = "zh-CN") =>
  request<AutoEditDraft>(`/autoedit/uploads/${encodeURIComponent(uploadId)}/drafts?language=${encodeURIComponent(language)}`, {
    method: "POST",
  });

export const getDraft = (draftId: string) =>
  request<AutoEditDraft>(`/autoedit/drafts/${encodeURIComponent(draftId)}`);

export const patchSegment = (draftId: string, segmentId: string, body: SegmentPatchInput) =>
  request<AutoEditDraft>(
    `/autoedit/drafts/${encodeURIComponent(draftId)}/segments/${encodeURIComponent(segmentId)}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );

export const deleteSegment = (draftId: string, segmentId: string) =>
  request<AutoEditDraft>(
    `/autoedit/drafts/${encodeURIComponent(draftId)}/segments/${encodeURIComponent(segmentId)}`,
    { method: "DELETE" },
  );

export const confirmDraft = (draftId: string, language?: string) =>
  request<AutoEditDraft>(
    `/autoedit/drafts/${encodeURIComponent(draftId)}/confirm`,
    { method: "POST", body: JSON.stringify(language ? { language } : {}) },
  );

// /autoedit-runs/* (独立前缀)
export const createRun = (draftId: string) =>
  request<AutoEditRun>(`/autoedit-runs/from-draft/${encodeURIComponent(draftId)}`, {
    method: "POST",
  });

export const getRun = (runId: string) =>
  request<AutoEditRun>(`/autoedit-runs/${encodeURIComponent(runId)}`);

export const retryRun = (runId: string) =>
  request<AutoEditRun>(`/autoedit-runs/${encodeURIComponent(runId)}/retry`, {
    method: "POST",
  });

// 视频 src: vanilla JS 用 /autoedit-runs/{id}/output (后端无此端点, 已坏).
// React 版改走 /outputs/{file} 静态路径, 与 src/api/drafts.ts outputUrl 风格一致.
// 若 output_path 含目录前缀, 取 basename 后再 encode, 防止路径穿越.
export function outputUrl(outputPath: string | null | undefined): string | null {
  if (!outputPath) return null;
  const base = outputPath.split(/[\\/]/).pop() || outputPath;
  return API + "/outputs/" + encodeURIComponent(base);
}
