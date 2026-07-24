export type SceneDraft = {
  id: string;
  position: number;
  title: string;
  narration: string;
  visual_intent: string;
  subtitle: string;
  duration_seconds: number;
  voice: string;
  avatar?: string | null;
  avatar_layout?: Record<string, unknown> | null;
};

export type WorkflowDraft = {
  id: string;
  title: string;
  source_script: string;
  language: string;
  status: "draft" | "confirmed";
  version: number;
  duration_seconds: number;
  scenes: SceneDraft[];
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
};

export type WorkflowNode = {
  id: string;
  scene_draft_id: string | null;
  node_type: string;
  status: string;
  progress: number;
  provider: string | null;
  attempt: number;
  result: unknown;
  message: string | null;
};

export type WorkflowRun = {
  id: string;
  workflow_draft_id: string;
  status: string;
  progress: number;
  render_job_id: string | null;
  message: string | null;
  nodes: WorkflowNode[];
  created_at: string;
  updated_at: string;
  finished_at: string | null;
};

type RenderMedia = {
  file: string | null;
};

export type RenderLatest = {
  renderRecent: { status: string; progress: number; mediaGeneratedId: RenderMedia | null } | null;
  renderSuccess: { status: string; progress: number; mediaGeneratedId: RenderMedia | null } | null;
};
