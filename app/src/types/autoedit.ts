// Auto-edit 类型 (独立于 workflow-drafts, 数据模型不同)
// 后端路由: /autoedit/* (upload/draft/segment) + /autoedit-runs/* (run/node)

export type SegmentKind = "keep" | "trim" | "drop";
export type AssetKind = "stock" | "none" | null;

export type AutoEditUpload = {
  id: string;
  filename: string;
  size_bytes: number;
  duration_seconds: number;
  width: number;
  height: number;
  container: string;
};

export type AutoEditSegment = {
  id: string;
  position: number;
  start_seconds: number;
  end_seconds: number;
  text: string;
  subtitle: string;
  kind: SegmentKind;
  asset_kind: AssetKind;
  asset_query: string | null;
  broll_url: string | null;
  music_volume: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type AutoEditDraftStatus = "draft" | "confirmed";

export type AutoEditDraft = {
  id: string;
  upload_id: string;
  title: string;
  status: AutoEditDraftStatus;
  version: number;
  language: string;
  duration_seconds: number;
  upload: AutoEditUpload;
  segments: AutoEditSegment[];
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
  transcription_warning?: string | null;
  transcription_source?: string | null;
};

export type AutoEditRunStatus =
  | "queued"
  | "generating_assets"
  | "rendering"
  | "success"
  | "failed";

export type AutoEditNode = {
  id: string;
  segment_id: string | null;
  node_type: string;
  status: string;
  progress: number;
  provider: string | null;
  attempt: number;
  result: unknown;
  message: string | null;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
};

export type AutoEditRun = {
  id: string;
  autoedit_draft_id: string;
  status: AutoEditRunStatus;
  progress: number;
  output_path: string | null;
  message: string | null;
  nodes: AutoEditNode[];
  created_at: string;
  updated_at: string;
  finished_at: string | null;
};

export type SegmentPatchInput = Partial<{
  kind: SegmentKind;
  subtitle: string;
  asset_kind: AssetKind;
  asset_query: string;
  start_seconds: number;
  end_seconds: number;
  music_volume: number;
}>;
