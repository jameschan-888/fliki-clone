-- Fliki 还原 SQLite Schema v1
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  workflow TEXT,
  format TEXT DEFAULT 'video',
  aspect_ratio TEXT DEFAULT '16:9',
  status TEXT DEFAULT 'draft',
  config_json TEXT,
  thumbnail_path TEXT,
  created_at INTEGER,
  updated_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);

CREATE TABLE IF NOT EXISTS scenes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  text TEXT NOT NULL,
  text_html TEXT,
  voice_id TEXT,
  voice_provider TEXT,
  audio_path TEXT,
  audio_duration REAL,
  media_provider TEXT,
  media_query TEXT,
  media_path TEXT,
  media_kind TEXT,
  duration_seconds REAL,
  transition TEXT,
  config_json TEXT,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_scenes_project ON scenes(project_id, idx);

CREATE TABLE IF NOT EXISTS layers (
  id TEXT PRIMARY KEY,
  scene_id TEXT NOT NULL,
  type TEXT NOT NULL,
  src TEXT,
  trim_before REAL DEFAULT 0,
  trim_after REAL,
  volume REAL DEFAULT 1,
  playback_rate REAL DEFAULT 1,
  x REAL,
  y REAL,
  width REAL,
  height REAL,
  style_json TEXT,
  z_index INTEGER DEFAULT 0,
  FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  type TEXT,
  status TEXT DEFAULT 'queued',
  progress REAL DEFAULT 0,
  message TEXT,
  attempt INTEGER DEFAULT 1,
  result_json TEXT,
  pid INTEGER,
  started_at INTEGER,
  finished_at INTEGER,
  created_at INTEGER,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS provider_configs (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  name TEXT NOT NULL,
  enabled INTEGER DEFAULT 1,
  is_default INTEGER DEFAULT 0,
  config_json TEXT,
  priority INTEGER DEFAULT 0,
  created_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_provider_cat ON provider_configs(category, enabled);

CREATE TABLE IF NOT EXISTS media_assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  filename TEXT NOT NULL,
  path TEXT NOT NULL,
  size_bytes INTEGER,
  duration_seconds REAL,
  width INTEGER,
  height INTEGER,
  meta_json TEXT,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS characters (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  image_path TEXT,
  voice_sample_path TEXT,
  voice_id TEXT,
  provider TEXT,
  meta_json TEXT,
  created_at INTEGER
);


-- ===== Phase 2 增量 (styles + media_samples) =====

CREATE TABLE IF NOT EXISTS styles (
  _id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  key TEXT UNIQUE NOT NULL,
  prefix TEXT,
  suffix TEXT,
  character_prompt TEXT,
  composition TEXT,
  image_prompt_direction TEXT,
  video_prompt_direction TEXT,
  thumbnail TEXT,
  is_enabled INTEGER DEFAULT 1,
  created_at TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_styles_key ON styles(key);
CREATE INDEX IF NOT EXISTS idx_styles_enabled ON styles(is_enabled);

CREATE TABLE IF NOT EXISTS media_samples (
  _id TEXT PRIMARY KEY,
  type TEXT,                       -- image / video
  file_path TEXT,
  name TEXT,
  duration REAL,
  thumbnail TEXT,
  aspect_ratio TEXT,
  quality TEXT,
  model TEXT,
  style TEXT,
  prompt TEXT,
  is_playground_generated INTEGER DEFAULT 0,
  collected_at TEXT,
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_samples_type ON media_samples(type);
CREATE INDEX IF NOT EXISTS idx_samples_model ON media_samples(model);
CREATE INDEX IF NOT EXISTS idx_samples_ar ON media_samples(aspect_ratio);

-- ===== Phase 3 增量 (render_jobs) =====

CREATE TABLE IF NOT EXISTS render_jobs (
  _id TEXT PRIMARY KEY,
  playback_id TEXT NOT NULL,
  status TEXT,                     -- queued / processing / success / failed
  progress INTEGER DEFAULT 0,
  resolution TEXT,                 -- 720p / 1080p
  extension TEXT,                  -- mp4 / mov
  renderer TEXT,                   -- local / docker / gke
  engine TEXT,                     -- ffmpeg / remotion
  message TEXT,
  media_generated_id TEXT,
  file TEXT,
  thumbnail TEXT,
  thumbnail_preview TEXT,
  user_id TEXT,
  created_at TEXT,
  finished_at TEXT
  -- FK 懒激活: playback_id 自动创建对应 project (render_create handler 中)
);
CREATE INDEX IF NOT EXISTS idx_render_playback ON render_jobs(playback_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_render_status ON render_jobs(status);

-- ===== Phase 5A: editable workflow drafts =====

CREATE TABLE IF NOT EXISTS workflow_drafts (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  source_script TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'zh-CN',
  status TEXT NOT NULL DEFAULT 'draft',
  version INTEGER NOT NULL DEFAULT 1,
  confirmed_snapshot_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  confirmed_at TEXT,
  user_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_workflow_drafts_status ON workflow_drafts(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS scene_drafts (
  id TEXT PRIMARY KEY,
  workflow_draft_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  title TEXT NOT NULL,
  narration TEXT NOT NULL,
  visual_intent TEXT NOT NULL,
  subtitle TEXT NOT NULL,
  duration_seconds REAL NOT NULL,
  voice TEXT NOT NULL DEFAULT 'zh-CN-XiaoxiaoNeural',
  avatar TEXT,
  avatar_layout TEXT,
  template_id TEXT,
  template_fields TEXT,
  stock_url TEXT,
  camera_motion TEXT NOT NULL DEFAULT 'zoom-in',
  video_aspect TEXT NOT NULL DEFAULT '16:9',
  video_transition_mode TEXT NOT NULL DEFAULT 'fade',
  media_width INTEGER NOT NULL DEFAULT 1280,
  media_height INTEGER NOT NULL DEFAULT 720,
  subtitle_display TEXT,
  subtitle_spoken TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(workflow_draft_id) REFERENCES workflow_drafts(id) ON DELETE CASCADE,
  UNIQUE(workflow_draft_id, position)
);
CREATE INDEX IF NOT EXISTS idx_scene_drafts_workflow ON scene_drafts(workflow_draft_id, position);

CREATE TABLE IF NOT EXISTS draft_revisions (
  id TEXT PRIMARY KEY,
  workflow_draft_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(workflow_draft_id) REFERENCES workflow_drafts(id) ON DELETE CASCADE,
  UNIQUE(workflow_draft_id, version)
);
CREATE INDEX IF NOT EXISTS idx_draft_revisions_workflow ON draft_revisions(workflow_draft_id, version DESC);


-- ===== 同步 provider 配置 (Phase 2 决策) =====

-- image 默认 runware-z-image-turbo (43/50 = 86%)
UPDATE provider_configs SET config_json = json_set(IFNULL(config_json, '{}'), '$.default_model', 'runware-z-image-turbo') WHERE category = 'image' AND name = 'mock';

-- video 默认 runware-kling-3-pro (7/50 多模型并列第一)
INSERT OR IGNORE INTO provider_configs (id, category, name, enabled, is_default, priority, config_json) VALUES
  ('provider_video_runware', 'video', 'runware_kling3pro', 0, 1, 5, '{"default_model": "runware-kling-3-pro", "alt_models": ["runware-seedance-pro-fast", "runware-pixverse-v5-fast", "runware-p-video", "runware-happyhorse-v1", "runware-ltx-2-fast", "runware-p-video-avatar", "runware-omnihuman-1-5", "runware-kling-2.5-turbo"]}');

-- avatar 本地化 driver
INSERT OR IGNORE INTO provider_configs (id, category, name, enabled, is_default, priority, config_json) VALUES
  ('provider_avatar_runware', 'avatar', 'runware_avatar', 0, 1, 5, '{"models": ["runware-p-video-avatar", "runware-omnihuman-1-5"], "local_drivers": ["sadtalker", "musetalk", "animatediff"]}');


-- ===== Phase 5B: confirmed generation pipeline =====

CREATE TABLE IF NOT EXISTS workflow_runs (
  id TEXT PRIMARY KEY,
  workflow_draft_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  progress INTEGER NOT NULL DEFAULT 0,
  render_job_id TEXT,
  output_path TEXT,
  message TEXT,
  user_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  finished_at TEXT,
  FOREIGN KEY(workflow_draft_id) REFERENCES workflow_drafts(id)
);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_draft ON workflow_runs(workflow_draft_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS workflow_nodes (
  id TEXT PRIMARY KEY,
  workflow_run_id TEXT NOT NULL,
  scene_draft_id TEXT,
  node_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  progress INTEGER NOT NULL DEFAULT 0,
  provider TEXT,
  attempt INTEGER NOT NULL DEFAULT 1,
  input_json TEXT,
  result_json TEXT,
  message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  finished_at TEXT,
  FOREIGN KEY(workflow_run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_workflow_nodes_run ON workflow_nodes(workflow_run_id, node_type, status);

CREATE TABLE IF NOT EXISTS scene_assets (
  id TEXT PRIMARY KEY,
  workflow_run_id TEXT NOT NULL,
  scene_draft_id TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  provider TEXT NOT NULL,
  source_url TEXT,
  local_path TEXT NOT NULL,
  duration_seconds REAL,
  attribution_json TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(workflow_run_id, scene_draft_id, asset_type),
  FOREIGN KEY(workflow_run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_scene_assets_run ON scene_assets(workflow_run_id, scene_draft_id);



-- ===== P5E Avatar Clones (Wav2Lip-ONNX / static fallback) =====
CREATE TABLE IF NOT EXISTS avatar_clones (
  id TEXT PRIMARY KEY,
  uuid TEXT UNIQUE NOT NULL,
  avatar_name TEXT NOT NULL,
  ref_face_path TEXT NOT NULL,
  ref_audio_path TEXT NOT NULL DEFAULT '',
  default_audio_path TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'zh',
  permission_note TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_avatar_clones_uuid ON avatar_clones(uuid);
CREATE INDEX IF NOT EXISTS idx_avatar_clones_enabled ON avatar_clones(enabled);

-- ===== P5D-3 Voice Clones (GPT-SoVITS / zero-shot) =====
CREATE TABLE IF NOT EXISTS voice_clones (
  id TEXT PRIMARY KEY,
  uuid TEXT UNIQUE NOT NULL,
  cloned_name TEXT NOT NULL,
  ref_audio_path TEXT NOT NULL,
  ref_text TEXT NOT NULL DEFAULT '',
  sample_text TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'zh',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_voice_clones_uuid ON voice_clones(uuid);
CREATE INDEX IF NOT EXISTS idx_voice_clones_enabled ON voice_clones(enabled);

-- ===== P5D-2 Voice Gallery =====
CREATE TABLE IF NOT EXISTS edge_voices (
  ShortName TEXT PRIMARY KEY,
  Gender TEXT,
  Locale TEXT,
  FriendlyName TEXT,
  SuggestedCodec TEXT,
  Status TEXT,
  VoiceType TEXT,
  fetched_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edge_voices_locale_gender ON edge_voices(Locale, Gender);
CREATE INDEX IF NOT EXISTS idx_edge_voices_friendly_name ON edge_voices(FriendlyName);

-- ===== P7-1 MiniMax Voice Clones (cloud clone, persistent) =====
CREATE TABLE IF NOT EXISTS minimax_voice_clones (
    id TEXT PRIMARY KEY,
    uuid TEXT UNIQUE NOT NULL,
    cloned_name TEXT NOT NULL,
    ref_audio_path TEXT NOT NULL,
    ref_audio_sha256 TEXT NOT NULL,
    ref_text TEXT NOT NULL DEFAULT '',
    sample_text TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'zh',
    voice_id TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT 'speech-02-turbo',
    provider TEXT NOT NULL DEFAULT 'minimax',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_minimax_voice_clones_sha256 ON minimax_voice_clones(ref_audio_sha256);
CREATE INDEX IF NOT EXISTS idx_minimax_voice_clones_uuid ON minimax_voice_clones(uuid);
CREATE INDEX IF NOT EXISTS idx_minimax_voice_clones_enabled ON minimax_voice_clones(enabled);

-- ===== P7C-B Local Video Templates (intro / outro / list / quote / data) =====
CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    builtin INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category, enabled);
CREATE INDEX IF NOT EXISTS idx_templates_enabled ON templates(enabled);

-- ===== rev24 stage C #8: multi-tenant FK =====
-- Indexes for user_id are created dynamically in main.init_db() so legacy
-- databases without the user_id column are upgraded safely.
