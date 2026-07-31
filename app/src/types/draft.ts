export type CameraMotion = "none" | "zoom-in" | "zoom-out" | "pan-left" | "pan-right" | "pan-up" | "pan-down";

export type TemplateFieldValue = string | number;

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
  template_id?: string | null;
  template_fields?: Record<string, TemplateFieldValue> | null;
  stock_url?: string | null;
  camera_motion: CameraMotion;
  // P0-5: media 宽高 (默认 1280x720)
  media_width: number;
  media_height: number;
  // P0-4: subtitle 双轨 (display=屏幕显示, spoken=TTS 朗读)
  subtitle_display: string;
  subtitle_spoken: string;
  // P1-7: VideoAspect / VideoTransitionMode (Pixelle 审计)
  video_aspect: "16:9" | "9:16" | "1:1";
  video_transition_mode: "none" | "fade" | "cut" | "slide-left" | "slide-right" | "slide-up" | "slide-down";
};

// P0-4: Scene 创建/更新 body 加双轨字段 + P0-5 加媒体宽高
export type ScenePatchInput = Partial<{
  title: string;
  narration: string;
  visual_intent: string;
  subtitle: string;
  duration_seconds: number;
  voice: string;
  avatar: string | null;
  avatar_layout: Record<string, unknown> | null;
  template_id: string | null;
  template_fields: Record<string, TemplateFieldValue> | null;
  stock_url: string | null;
  camera_motion: CameraMotion;
  media_width: number;
  media_height: number;
  subtitle_display: string;
  subtitle_spoken: string;
  video_aspect: "16:9" | "9:16" | "1:1";
  video_transition_mode: "none" | "fade" | "cut" | "slide-left" | "slide-right" | "slide-up" | "slide-down";
}>;

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
