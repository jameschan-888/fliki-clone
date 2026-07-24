# Fliki 还原 MVP 技术选型与架构 v4

> 基于用户 6 条决策（2026-07-23）
> 项目根：D:\workspace\Fliki视频制作还原\
> 复用基础：D:\workspace\proj_055_短视频运营助手\ 后端 + FFmpeg 渲染队列

---

## 1. 用户决策（已锁定）

| # | 决策点 | 用户选择 |
| --- | --- | --- |
| 1 | 渲染引擎 | 更经济 + 更高质量 + 电脑要求更低 |
| 2 | 后端协议 | 更简单 + 更经济 + 部署更方便 + 本地部署 |
| 3 | 首批工作流 | Script to video + Auto edit video |
| 4 | Stock 素材 | Pexels/Pixabay 免费 + 预留付费 API |
| 5 | 各节点 LLM | 用户手动配置接入 |
| 6 | 本地化 | 数字人 + 声音克隆 + 80+ 语言 |

---

## 2. 技术选型决策

### 2.1 渲染引擎：FFmpeg 主 + Remotion 辅

对比表（经济 / 质量 / 电脑要求）：

| 引擎 | 经济 | 视频质量 | 动画/字幕 | 数字人/特效 | 电脑要求 | 本地部署 |
| --- | --- | --- | --- | --- | --- | --- |
| FFmpeg | 极优（单 binary 0 成本） | 高（H.264/H.265） | 中（drawtext/ass 字幕） | 弱（无原生） | 极低（2-4 核够） | 极简（一个 exe） |
| Remotion | 中（Node + Chromium + React） | 高 | 极高（React 组件化） | 中（需自定义） | 高（需 GPU 加速） | 复杂（npm install + 浏览器） |
| OpenCV/Pillow | 高 | 中（适合图像） | 低 | 中（合成） | 中 | 简单 |

结论：
- MVP 主渲染：FFmpeg（proj_055 已用，验证过）
- 字幕用 FFmpeg + ASS（高级字幕样式）+ Pillow 生成 PNG 烧入
- 数字人/转场特效：未来可挂 Remotion 子模块（按需）
- 本期不引入 Remotion

### 2.2 后端协议：FastAPI + REST

对比表：

| 协议 | 实现难度 | 性能 | 类型安全 | 本地部署 | 项目已有 |
| --- | --- | --- | --- | --- | --- |
| FastAPI + REST | 极简（@app.get） | 高（异步） | 强（Pydantic） | 极简（uvicorn 一行） | proj_055 已在用 |
| JSON-RPC batch | 中（需 router 框架） | 高 | 中 | 中 | 无 |
| GraphQL | 高（schema + resolver） | 中（查询优化） | 强 | 中 | 无 |
| tRPC | 中（需 Node） | 高 | 强 | 中（要 Node 进程） | 无 |
| gRPC | 高（protobuf） | 极高 | 强 | 复杂 | 无 |

结论：FastAPI + REST（proj_055 已用，复用 0 成本）

### 2.3 Stock 素材：Pexels 默认 + Pixabay + 预留付费

默认实现：
- Pexels API：免 key 有 rate limit（200/h 限制）
- Pixabay API：免 key 申请简单
- StockProvider 抽象类（Strategy 模式）

预留接口：
- GettyProvider（API key 付费）
- ShutterstockProvider（API key 付费）
- 本地素材库（上传的 user media）

### 2.4 LLM/TTS/Provider 注册表模式

用户手动配置；所有 Provider 实现标准接口；通过 config.json 启用。

节点类型：

| 节点 | 默认 Provider | 备选 Provider |
| --- | --- | --- |
| 文本生成（脚本/标题/描述） | Mock / DeepSeek | MiniMax / OpenAI / Ollama / 智谱 / 通义 |
| TTS 配音 | Edge TTS（本地免费，80+ 语言） | OpenAI TTS / ElevenLabs / GPT-SoVITS（声音克隆） |
| 音乐 | 本地 MusicGen | Suno / Udio |
| 图片生成 | 本地 Mock / Pexels 图片 | Flux / DALL-E / Stable Diffusion |
| 视频生成 | Stock 视频拼接 | Pika / Runway / Veo / Kling / Seedance / AnimateDiff |
| 数字人 | 本地 SadTalker | HeyGen / D-ID |
| 声音克隆 | GPT-SoVITS（本地） | ElevenLabs / OpenVoice |
| 翻译 | DeepSeek / OpenAI | Ollama 本地 |

配置文件：provider_config.json（UI 可编辑）

### 2.5 本地化数字人 / 声音克隆 / 80+ 语言

数字人（口型同步）：
- 首选本地：SadTalker / MuseTalk（开箱即用）
- 备选付费：HeyGen API / D-ID
- 输入：静态头像图 + TTS 音频 → 视频

声音克隆：
- 首选本地：GPT-SoVITS（中文最好，30 秒样本即可训练）
- 备选付费：ElevenLabs / OpenVoice

80+ 语言：
- 默认：Edge TTS（微软免费，80+ 语言 100+ 口音，0 成本）
- Edge TTS 内置 200+ 声音，无需 key
- 翻译节点：DeepSeek/OpenAI（多语言）
- Lip-sync：MuseTalk 多语言支持有限，复杂场景走 HeyGen

---

## 3. 系统架构

┌─────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite + Radix UI + Tailwind)            │
│  /                       Home: 6 工作流 + 3 tab              │
│  /files                  项目列表                            │
│  /characters             数字人库 + 声音克隆                  │
│  /templates              模板库                              │
│  /playground             AI 试用场                           │
│  /editor/<playbackId>    Composer 三栏                       │
│  /settings/providers     Provider 配置 UI                    │
└─────────────────────────────────────────────────────────────┘
                              │ REST + JSON
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend (FastAPI + SQLite + FFmpeg)                         │
│  /api/projects        CRUD 项目                              │
│  /api/projects/<id>/script                                          │
│  /api/projects/<id>/generate  触发生成                       │
│  /api/projects/<id>/render    触发渲染                       │
│  /api/providers      LLM/TTS/Image/Video Provider            │
│  /api/voices         TTS 声音库                              │
│  /api/characters     数字人 + 声音克隆                       │
│  /api/stock/search   Pexels/Pixabay 搜索                     │
│  /api/stock/import   下载素材到本地                          │
│  /api/media/upload   用户上传素材                            │
│  /api/jobs           渲染任务队列状态                        │
└─────────────────────────────────────────────────────────────┘
       │              │            │            │
       ▼              ▼            ▼            ▼
┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────┐
│ SQLite  │ │  FFmpeg      │ │ Provider │ │  File System │
│ (项目/  │ │  (渲染队列)  │ │ Plugins  │ │  (素材/输出) │
│ 任务)   │ │              │ │          │ │              │
└──────────┘ └──────────────┘ └──────────┘ └──────────────┘
                                  │
                                  ▼
                  ┌─────────────────────────────┐
                  │  LLM / TTS / Image / Video │
                  │  - DeepSeek / OpenAI / Ollama
                  │  - Edge TTS / GPT-SoVITS   │
                  │  - Pexels / Pixabay / Flux │
                  │  - Suno / MuseTalk / HeyGen│
                  └─────────────────────────────┘

---

## 4. 项目结构

D:\workspace\Fliki视频制作还原\
├── research/                          # 调研资料
│   ├── Fliki结构分析.md               # v3 文档
│   ├── architecture.md                # 本文档 v4
│   ├── editor-fiber-schema.json       # 22 组件 prop
│   └── raw/                           # 原始 HTML/chunks
├── backend/                           # 后端（新建）
│   ├── main.py                        # FastAPI 入口
│   ├── config.py                      # 配置（合并 proj_055）
│   ├── db/                            # SQLite 模型
│   ├── api/                           # REST API
│   ├── providers/                     # Provider 注册表
│   │   ├── base.py                    # 抽象类
│   │   ├── text/                      # 文本生成
│   │   ├── tts/                       # TTS
│   │   ├── image/                     # 图片生成
│   │   ├── video/                     # 视频生成
│   │   ├── music/                     # 音乐
│   │   ├── avatar/                    # 数字人
│   │   └── stock/                     # Stock 素材
│   ├── workflows/                     # 工作流编排
│   ├── render/                        # 渲染层（接 proj_055）
│   ├── jobs/                          # 任务队列
│   ├── data/                          # 运行时数据
│   └── provider_config.json           # 用户配置
├── app/                               # 前端
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                    # 路由
│   │   ├── pages/                     # 7 个页面
│   │   ├── components/                # 业务组件
│   │   │   ├── layout/
│   │   │   ├── editor/                # Composer 子组件
│   │   │   └── ui/
│   │   ├── api/
│   │   ├── styles/                    # Tailwind
│   │   └── types/
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
├── docs/                              # 项目文档
│   ├── api.md
│   └── providers.md
├── start_backend.bat
├── start_frontend.bat
└── README.md

---

## 5. 复用 proj_055 的代码（避免重复造轮）

直接复用：
- proj_055/backend/main.py：FastAPI 启动方式、middleware、CORS
- proj_055/backend/db/：SQLite 模型 + schema（accounts/topics/videos 等）
- proj_055/backend/render_queue.py：渲染任务队列（async + SQLite）
- proj_055/backend/llm/base.py：LLMProvider 抽象类
- proj_055/backend/llm/deepseek.py：DeepSeek 实现
- proj_055/backend/llm/mock.py：Mock 实现（默认）
- proj_055/backend/config.py：配置加载 + 环境变量
- proj_055/requirements.txt：依赖清单

改造方式：
- 在 Fliki 后端 import proj_055 模块（sys.path 注入）
- 或直接复制必要文件到 Fliki 后端，修改 namespace
- 数据库独立（Fliki 用 app.db，不与 proj_055 共享）

---

## 6. 数据模型（SQLite Schema）

```sql
-- 项目（视频作品）
CREATE TABLE projects (
  id TEXT PRIMARY KEY,                    -- playbackId 风格
  title TEXT NOT NULL,
  workflow TEXT,                          -- script|auto_edit|empty
  format TEXT DEFAULT 'video',            -- video|audio
  aspect_ratio TEXT DEFAULT '16:9',       -- 16:9|9:16|1:1
  status TEXT DEFAULT 'draft',            -- draft|generating|ready|rendering|rendered|failed
  config_json TEXT,                       -- 项目配置（节点选择/Provider 选择）
  created_at INTEGER,
  updated_at INTEGER
);

-- 场景
CREATE TABLE scenes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  text TEXT NOT NULL,
  text_html TEXT,                         -- 富文本（关键词高亮）
  voice_id TEXT,
  voice_provider TEXT,                    -- edge_tts/gpt_sovits/openai_tts
  audio_path TEXT,
  media_provider TEXT,                    -- stock/pexels/image_gen/upload
  media_query TEXT,
  media_path TEXT,
  duration_seconds REAL,
  transition TEXT,                        -- fade/slide/cut
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Layer（图层）
CREATE TABLE layers (
  id TEXT PRIMARY KEY,
  scene_id TEXT NOT NULL,
  type TEXT NOT NULL,                     -- text|image|video|audio|character
  src TEXT,
  trim_before REAL DEFAULT 0,
  trim_after REAL,
  volume REAL DEFAULT 1,
  playback_rate REAL DEFAULT 1,
  x REAL, y REAL, width REAL, height REAL,
  style_json TEXT,                        -- 字体/颜色/对齐等
  z_index INTEGER DEFAULT 0,
  FOREIGN KEY (scene_id) REFERENCES scenes(id)
);

-- 任务（渲染/生成）
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  type TEXT,                              -- script_generate|tts_generate|render|video_generate
  status TEXT,                            -- queued|running|succeeded|failed|cancelled
  progress REAL DEFAULT 0,
  message TEXT,
  attempt INTEGER DEFAULT 1,
  result_json TEXT,
  started_at INTEGER,
  finished_at INTEGER,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Provider 配置
CREATE TABLE provider_configs (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,                 -- text|tts|image|video|music|avatar|stock
  name TEXT NOT NULL,                     -- edge_tts/deepseek
  enabled INTEGER DEFAULT 1,
  is_default INTEGER DEFAULT 0,
  config_json TEXT,                       -- API key 等敏感信息加密存
  priority INTEGER DEFAULT 0
);

-- 用户素材
CREATE TABLE media_assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,                     -- video|image|audio
  filename TEXT NOT NULL,
  path TEXT NOT NULL,
  size_bytes INTEGER,
  duration_seconds REAL,
  width INTEGER,
  height INTEGER,
  meta_json TEXT,
  created_at INTEGER
);

-- 数字人/声音克隆
CREATE TABLE characters (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,                     -- avatar|voice_clone
  image_path TEXT,
  voice_sample_path TEXT,
  provider TEXT,                          -- sadtalker/gpt_sovits/heygend_id
  meta_json TEXT,
  created_at INTEGER
);
```

---

## 7. Provider 接口规范

```python
# providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ProviderResult:
    ok: bool
    data: any;             # Provider 特定输出
    error: str = '';
    credits: float = 0;    # 计费（0 = 免费）

class TextProvider(ABC):
    name: str = 'base';
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> ProviderResult: ...

class TTSProvider(ABC):
    name: str = 'base';
    @abstractmethod
    async def synth(self, text: str, voice_id: str, lang: str = 'zh', **kwargs) -> ProviderResult: ...
    @abstractmethod
    async def list_voices(self, lang: str = '') -> list[dict]: ...

class ImageProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> ProviderResult: ...

class VideoProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, duration: int = 5, **kwargs) -> ProviderResult: ...

class MusicProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, duration: int = 30, **kwargs) -> ProviderResult: ...

class AvatarProvider(ABC):
    @abstractmethod
    async def speak(self, image_path: str, audio_path: str, **kwargs) -> ProviderResult: ...

class StockProvider(ABC):
    @abstractmethod
    async def search(self, query: str, kind: str = 'video', page: int = 1) -> ProviderResult: ...
    @abstractmethod
    async def download(self, stock_id: str, dest_path: str) -> ProviderResult: ...
```

---

## 8. 工作流编排

Script to video 流程：

```
[脚本输入] -> [LLM 切分场景] -> [TTS 配音] -> [Stock 配图] -> [字幕生成] -> [FFmpeg 合成]
                  ↓                ↓            ↓              ↓              ↓
              text          tts (edge_tts)  stock (pexels)  subtitle     render
```

Auto edit video 流程：

```
[上传视频] -> [FFprobe 元数据] -> [静音检测] -> [智能粗剪] -> [字幕烧入] -> [背景音乐] -> [渲染]
                ↓
          ffprobe
```

---

## 9. 实施阶段（建议 4 周）

### Phase 1：骨架（3 天）
- 复制 proj_055 后端基础结构
- SQLite schema 创建
- Provider 抽象类 + Mock 默认实现
- FastAPI 启动脚本
- 前端 Vite + React 19 + Tailwind + Radix UI 初始化

### Phase 2：核心 API（5 天）
- /api/projects CRUD
- /api/providers CRUD + 配置 UI
- /api/stock/search (Pexels)
- /api/voices (Edge TTS 声音列表)
- /api/media/upload（用户素材）
- /api/jobs（任务状态）

### Phase 3：Script to video（7 天）
- LLM Provider：mock + deepseek
- TTS Provider：edge_tts（80+ 语言）
- Stock Provider：pexels
- Workflow：脚本 -> 场景 -> TTS -> 配图 -> 字幕 -> 渲染
- FFmpeg 渲染管线（复用 proj_055）
- 前端：Home + Script dialog + Composer 三栏

### Phase 4：Auto edit video + 数字人（7 天）
- FFprobe + 静音检测（已有）
- 字幕烧入（已有）
- 数字人：SadTalker/MuseTalk 集成
- 声音克隆：GPT-SoVITS 集成
- 前端：Auto edit dialog + Characters 页

### Phase 5：打磨 + 配置 UI（5 天）
- Provider 配置 UI（页面）
- Project 列表 + 文件夹
- Templates 库
- Playground
- 部署文档 + 启动脚本

---

## 10. 待客户确认（开工前）

1. 后端 Python 版本：3.12（proj_055 已用）？
2. 是否复用 proj_055 数据库：独立新 DB 还是共享？
3. 前端端口：5188（仿 proj_055）？
4. Stock 缓存目录：D:\workspace\Fliki视频制作还原\backend\data\stock\？
5. Provider 默认值：LLM=mock, TTS=edge_tts, Stock=pexels, Music=stock, Avatar=sadtalker（如有模型），可以吗？
6. 数字人模型权重：用户自己下载 SadTalker/MuseTalk 权重（约 2-5GB），系统检测到自动启用？还是先 stub（占位）？
7. GPT-SoVITS 集成：是否在 Phase 4 接入？还是要更早？
8. 是否要导出 MP4 之外格式：MOV（剪映/PR 友好）、GIF（预览）？

---

## 11. 下一步（立刻可做）

1. 复制 proj_055 后端代码 -> D:\workspace\Fliki视频制作还原\backend\
2. 初始化 SQLite schema（按上面 §6）
3. 创建 Provider 抽象类 + Mock
4. 搭前端 Vite 骨架 + Home 页（6 大工作流卡片）
5. 本地启动验证：后端 8001（避 proj_055 8000）+ 前端 5188

---

## 11. v4 增量补充 (2026-07-23 已登录深度抓取后)

### 11.1 来自 Leo Chan 账号的真实数据 (free plan)

- **JWT claim**: `{"id":"<24-hex>","isMobile":false,"iat":<ts>}` — 我们的后端用同样的 token payload 即可（不需要 Mongoose user model）
- **本地数据缓存策略（参考 Fliki）**: `userAuth` / `subscriptionActive` / `fileCreateSettings` / `playbackFocus` / `driveList` / `usageSummary` / `recipeList` / `stock-character-picker` 等缓存到 localStorage，每页 onMount 校验陈旧度
- **角色 CDN 路径**: `cdn.fliki.ai/image/character-stock/<dir>/<id>.jpg`
- **生成 TTS 路径**: `cdn.fliki.ai/media.v2/generated/<userId>/<audioId>.mp3`
- **Stock 缩略图**: `cdn.fliki.ai/media.v2/stock/storyblocks/<id>_thumb.jpg`

### 11.2 Free plan limits 表 (我们的 quota 默认值)

| 资源 | Free | Premium (Fliki) | 本地推荐 |
| ---- | ---- | --------------- | -------- |
| units/月 | 180 | (paid 5K-50K) | 9999（本地无限制，但记录） |
| voices | 300 | unlimited | 9999 |
| exportLength | 5 min | 60 min | 无限制 |
| sceneSize | 50 | unlimited | 999 |

### 11.3 Credit 计费项 (16 类，本地可简化)

Fliki 计费粒度:
generateAvatar / generateAudio / generateImage / generateVideo / generateScript / generateVoiceover / generateVoiceCustom / removeBackground / render / publish / translate / workflow / summarizeMedia / stockDownload / copilot / creditAdditional / creditDeduct

本地简化（v1 推荐 6 类）:
- tts (字符数计费)
- image (次)
- video (秒)
- music (次)
- render (秒)
- stock_download (次)

### 11.4 Recipe 工作流模板 (5 个，Fliki 已实现)

| Recipe | plan | 描述 | 本地优先级 |
| ------ | ---- | ---- | ---------- |
| Stop-Motion Story Video Generator | premium | 停格动画 + 羊毛毡 | P3 |
| Raw Clips to Final Video | free | 原始片段 → 自动剪辑 | **P0 = AutoEditVideo 工作流直接对应** |
| Product Image to Ad Creative | free | 产品图 → 3 张广告 | P2 |
| Translate Audio/Video | basic | 翻译 + 配音 + 字幕 | **P0 = 复用 AutoEdit pipeline 加字幕覆盖** |
| Product Image to Marketing Video | standard | 产品图 → 营销视频 | P2 |

### 11.5 公共角色名单 (Fliki 67 个，本地 v1 推荐 13 个核心 + 后续扩展)

**核心女声 (7)**: Chloe / Emma / Mia / Maya / Camila / Sophie / Ava
**核心男声 (6)**: Noah / James / Arjun / Ethan / Andre / Ryan
**小孩 (3)**: Leila / Sunita / Marco
**扩展 (51)**: 剩余 51 个作为可选下拉

本地实现:
- 每个角色 seed 一张头像 (来自 unsplash + 风格化提示词)
- 配套 TTS 声音 (Edge TTS 选 13 个对应性别/口音)
- 数字人: 先用静态头像 + 字幕，后期可挂 SadTalker/MuseTalk

### 11.6 Editor 11 个工具面板 (前端 UI 规划)

| # | 工具 | 实现难度 | v1 是否做 |
| - | ---- | -------- | -------- |
| 1 | Copilot | 高 (需 LLM agent) | v2 |
| 2 | Media | 中 (Stock provider 已设计) | **v1** |
| 3 | Character | 中 (复用角色库) | **v1** |
| 4 | Subtitles | 中 (FFmpeg + ASS) | **v1** |
| 5 | Audio | 中 (Stock + upload) | **v1** |
| 6 | Elements | 高 (图标 + 形状库) | v2 |
| 7 | Record | 高 (WebRTC 录屏) | v3 |
| 8 | Templates | 中 (模板 JSON) | v2 |
| 9 | Layers | 中 (v1 简化) | **v1** |
| 10 | Settings | 低 (单页表单) | **v1** |
| 11 | (hidden) | - | - |

v1 编辑器 UI 选 6 个工具 (Media/Character/Subtitles/Audio/Layers/Settings) + 4 个 v2/v3 占位。

### 11.7 Audio Stock 标签 (v1 推荐种子)

Fliki 真实标签: Scifi / Horror / Alarms / Cartoon / Ambient
本地 v1 标签 (简化): Music: Happy/Sad/Energetic/Calm/Corporate  SFX: whoosh/pop/click/notification/nature

### 11.8 CDN 缓存策略 (本地变体)

Fliki: S3 + CloudFront + signed URL
本地:
- stock/ 目录 (D:/workspace/Fliki视频制作还原/backend/data/stock/)
- 每次 stock search 命中先查本地，本地 miss 才下载 Pexels/Pixabay
- 下载后保留 7 天 (LRU)
- 文件命名: `<source>_<id>.<ext>`

### 11.9 数据模型增量 (复用 v3 schema)

```sql
-- 在 projects/scenes/layers/jobs/provider_configs/media_assets/characters 之上新增
CREATE TABLE recipes (
  id TEXT PRIMARY KEY,
  slug TEXT UNIQUE,
  name TEXT NOT NULL,
  description TEXT,
  plan TEXT DEFAULT free,
  cost_credits REAL DEFAULT 0,
  pipeline_json TEXT NOT NULL,  -- 节点编排 JSON
  icon TEXT, color TEXT,
  is_enabled INTEGER DEFAULT 1,
  created_at TEXT, updated_at TEXT
);

CREATE TABLE voice_clones (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  language TEXT,
  ref_audio_path TEXT NOT NULL,    -- 30 秒样本
  model_path TEXT,                  -- 训练后的 SoVITS 模型
  is_public INTEGER DEFAULT 0,
  created_at TEXT
);

CREATE TABLE avatars (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  thumbnail_path TEXT NOT NULL,
  avatar_type TEXT,                -- stock | mine | generated
  ref_image_path TEXT,             -- 数字人参考图
  audio_path TEXT,                 -- 默认音频
  tags TEXT,                        -- JSON array
  is_paid INTEGER DEFAULT 0,
  created_at TEXT
);
```

### 11.10 与 Fliki 后端的 API 兼容层 (可选)

如果未来用户想导入 Fliki 旧项目，可加个 `migration/fliki_to_local.py`:
- 读 Fliki 的 `playback.json`
- 转换 scene/layer/media schema → 本地
- 重新下载 stock 素材到本地
- 创建本地 project 记录

### 11.11 现状 (2026-07-23 v4 阶段)

- [x] research/Fliki结构分析.md v4
- [x] research/architecture.md v4
- [x] research/editor-fiber-schema.json v3
- [x] research/dump/localStorage-keys.json
- [x] research/dump/user-data.json
- [x] research/dump/editor-fiber.json
- [x] research/dump/api-endpoints.md
- [x] research/dump/playback-scene-layer-schema.json
- [ ] backend/main.py (TODO)
- [ ] backend/providers/base.py (TODO)
- [ ] backend/api/* (TODO 9 个文件)
- [ ] backend/workflows/script_to_video.py (TODO)
- [ ] backend/workflows/auto_edit_video.py (TODO)
- [ ] app/src/* (TODO 前端)

下一阶段目标 (Phase 1 收尾): 1-2 天内完成 backend scaffold + provider abstract + Mock defaults