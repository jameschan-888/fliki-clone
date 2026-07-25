# Fliki 视频制作还原

> Fliki 风格独立视频创作系统，从 0 开始二创。

## 项目目标
- 克隆 fliki.ai 公开 UI / 信息架构
- 按"6 大核心工作流 + 辅助能力"搭建独立产品
- 后续预留作为 GoodJob CRM 的视频模块链接

## 目录
- `research/Fliki结构分析.md` — v4 综合分析（已登录深度抓取，2026-07-23）
- `research/architecture.md` — 技术选型 + 系统架构 v4（含 v4 增量补充 11 节）
- `research/editor-fiber-schema.json` — v3 Composer 编辑器 22 组件 prop
- `research/dump/localStorage-keys.json` — 21 个 localStorage key + size + purpose
- `research/dump/user-data.json` — userAuth/JWT/subscription/fileCreateSettings/usageSummary/recipeList schema
- `research/dump/editor-fiber.json` — v4 React Fiber walk（keyComponents + toolsInEditor + layoutZones）
- `research/dump/api-endpoints.md` — 16 个 tRPC endpoint + auth + CDN
- `research/dump/playback-scene-layer-schema.json` — playback/scene/layer/drive 全字段
- `research/raw/` — 19 份原始抓取（home/features/use-cases/pricing/6 workflows/5 functions）
- `research/raw/app.fliki.ai/` — welcome + 8 framework chunks
- `app/` — 前端（待开发）
- `backend/` — 后端（待开发）
- `docs/` — 项目文档

## 进度
- [x] 2026-07-23 v1: 抓 fliki.ai 4 公开页
- [x] 2026-07-23 v2: 抓 15 公开页 + welcome + chunks
- [x] 2026-07-23 v3: 登录态深度抓取（7 应用页 + 5 工具面板 + Remotion + JSON-RPC + 22 组件 schema）
- [x] 2026-07-23 v4: 11 工具面板完整列表 + Settings 面板 + Media/Audio/Character 面板 + Characters/Files/Playground 主页 + JWT 解码 + Free plan limits + 16 类 credit 计费 + 5 个 Recipe + 67 个角色名单 + 完整 playback/scene/layer/drive schema
- [ ] 工程脚手架搭建
- [ ] Provider 抽象 + Mock defaults
- [ ] Phase 1: backend scaffold + DB + API CRUD
- [ ] Phase 2: 核心 REST APIs + provider config UI + stock + voices
- [x] Phase 3A: Script-to-video 可编辑场景草稿 + 确认闸门 + 最小编辑 UI
- [x] Phase 3B: 确认后素材(Stock)/配音(TTS)/音乐(Music)生成与渲染
- [x] Phase 3C: Auto-edit 视频剪辑 (端到端 30s 真实 mp4)
- [ ] Phase 4: Auto edit video + digital human + voice clone
- [ ] Phase 5: polish + provider config UI + deploy scripts

## v4 关键发现
- **渲染引擎**：Remotion (LoadableComponent + withInteractivitySchema HOC, 1920x1080@30fps)
- **后端协议**：tRPC over HTTP GET (Express + Google CDN)
- **数据模型**：4 级 ID (playbackId/sceneId/layerId/voiceId) + Mongoose
- **UI 库**：Radix UI (Dialog/Tooltip/Popover/DropdownMenu/ScrollArea)
- **状态管理**：Zustand + localStorage cache (21 keys, ~500KB)
- **媒体 CDN**：cdn.fliki.ai (S3 + CloudFront, 3 类: generated/my/stock)
- **JWT**: HS256, claim = { id, isMobile, iat }
- **Free plan**: 180 units/月 + 300 voices + 5min export + 50 scenes
- **角色**: 67 公共 + Clone your voice (paid) + Avatars (paid)
- **AI 模型**: Flux 2 Klein 0.05 credits (image), Runware (video)
- **音频**: 3 类 Music/SFX/YouTube Music + 4 Tab Stock/Library/Generate/Favorites
- **媒体**: 3 类 Video/Image/GIF + 5 Tab Stock/Library/Generate/Favorites/Recent
- **工作流**: 6 主页 + 5 Recipe (Stop-Motion/RawClips/Product/Translate/Marketing)

## 用户决策（已锁定 2026-07-23）
1. 渲染: Remotion（跟 Fliki 一致；Windows 本地使用系统 Chrome，底层由 FFmpeg 编码）
2. 协议: FastAPI + REST (proj_055 已成熟复用)
3. 首批工作流: Script to video + Auto edit video
4. Stock: Pexels/Pixabay 免费默认 + 付费预留
5. 每节点 LLM: 用户手动配置接入
6. 本地化: SadTalker/MuseTalk 数字人 + GPT-SoVITS 声音克隆 + Edge TTS 80+ 语言

## 复用 proj_055
- D:/workspace/proj_055_短视频运营助手/ 后端 (FastAPI + FFmpeg + LLM provider)
- 渲染队列 (render_queue.py)、LLM 抽象 (llm/base.py)、配置加载 (config.py)
- 端口: Fliki 用 8001 (避开 proj_055 的 8000)
- 数据库: 独立 SQLite app.db (不共享)

## 下一步
- Phase 4 渲染基础设施已完成：真实 MP4/JPG、Fliki 风格进度、取消、硬超时和进程树回收
- P5A 已完成：脚本拆分、场景编辑/增删/排序、版本记录、确认锁定和最小前端
- 下一核心缺口：P5B 确认后素材、TTS、音乐和渲染流水线
- Provider API Key 继续保持每节点手动配置
## v5 增量 (2026-07-23 第二轮补抓)
- 抓到了 Subtitles 18 预设 + 完整控件
- 抓到了 Layers + Add layer 8 类菜单
- 抓到了 Copilot + 4 LLM (GLM-5.2/Flash/Gemini 3.5 Flash/Opus 4.8)
- 抓到了 Templates 10+ 分类 + Elements 4 大类 + Record Screen/Webcam/Mic
- 抓到了 Audio Generate tab (Ace Step 1.5 Base) + Media Generate tab (Z Image Turbo + 9 样例)
- 抓到了 Series / Tools / Automation / Voices 4 个付费主页
- 抓到了 Character picker 完整 69 个 + Styles 视觉风格库 29 个
- 新增 dump 文件: character-picker.csv (8KB) + styles.csv (7.5KB)
- 完整 Fliki结构分析.md: 24KB (v3 8.5KB -> v4 12KB -> v5 24KB)

## 决策补充 (v5)
- LLM 默认: DeepSeek + Claude/GPT-4 高级 + Qwen/GLM/Hunyuan 廉价（按 Fliki Copilot 设计）
- Music 模型: MusicGen 本地 / Suno API（Fliki 用 Ace Step 1.5 Base）
- 角色种子: 13 个核心（v1 静态头像, v2+ 补 driving video）
- Style 种子: 5-10 个核心（用 prefix+suffix 拼 prompt）
- Paid features 不做: Series autopublish / Automation Zapier/Make / Voice Clone / AI Avatar


## v6 增量 (2026-07-23 第三轮补抓)
- 抓到了 Playground AI 视频模型完整 14 个 (Seedance/P-Video/PixVerse/LTX/Kling/HappyHorse/Veo) — v5 只说 "Stock 优先"，实际 v5 漏的 AI video 模型
- 抓到了 Playground AI 音乐模型完整 2 个 (Ace Step 1.5 Base + **MiniMax Music 2.6**)
- 抓到了 Editor Download dialog (Resolution 720p + Format mp4 + Start export)
- 抓到了 Editor Share preview dialog (Create link 按钮)
- 抓到了 Editor Add scene 流程 (无菜单直接加空 scene，默认 1.0s Sara + Blank media)
- 抓到了 Editor Scene options 菜单 (Rename/Custom duration/Hide/Copy 4 项)
- 抓到了完整 tRPC batch response (46KB JSONL, 7 endpoint 一次合并)
- 抓到了 playback/scene/layer/media/subtitle/transcription 完整字段 schema
- 抓到了 drive/workflow/voice 完整 schema
- **关键发现**: Fliki 数字人走 D-ID service (clips-presenters.d-id.com)，付费第三方
- **关键发现**: AI 图像默认 runware-z-image-turbo (v5 推测的 Flux 2 Klein 错)
- **关键发现**: 场景拆解用 gemini-2.5-flash-lite (v5 写的 GLM-5.2 错)
- 新增 dump 文件: trpc-batch-summary.md (19KB 完整 schema 摘要)
- 新增主文档第 17 节 v6 增量补充 (5.2KB 追加到 Fliki结构分析.md v6 = 30KB)


---

## Phase 2 增量 (2026-07-23)

完成 style 库 + 100 条 sample 记录完整抓取。

- 新增文件 research/dump/style-list-full.jsonl (74KB) — 29 个 style 完整 schema
- 新增文件 research/dump/samples-image-v2-full.jsonl (70KB) — 50 image prompt
- 新增文件 research/dump/samples-video-v2-full.jsonl (54KB) — 50 video samples（47 条有 prompt，3 条 OmniHuman 无 prompt）
- 新增摘要 research/dump/trpc-phase2-summary.md (15KB) — 决策影响 + 工程落地

### 关键发现
- 2 个 style 有非空 imagePromptDirection: Cinematic + Golden age
- Image 默认模型 = runware-z-image-turbo (43/50 = 86%)
- Video 9 个 model 频次平均
- 数字人专用 model: p-video-avatar (4) + omnihuman-1-5 (3)
- TTS 标签 <umm> <chuckle> <sigh> 嵌入 dialogue 引号内
- SFX 行出现在所有 prompt
- 角色一致性提示在 video sample

### 决策影响
- sceneBreakdownModel = gemini-2.5-flash-lite
- aiModel = runware-z-image-turbo
- videoModel = runware-kling-3-pro (9 选 1)
- avatarModel = runware-p-video-avatar (本地化换 SadTalker/MuseTalk)
- TTS 标签 SSML 转换预处理
- providers/image 默认 1536x1024 (16:9)
- 新增 styles + media_samples 表


---

## Phase 3 增量 (2026-07-23)

完成 render pipeline + preview 完整抓取（含 4 状态时间线）。

- 新增文件 research/dump/render-timeline.jsonl (1.7KB) - render 4 阶段完整 response
- 新增摘要 research/dump/trpc-phase3-summary.md (4KB) - schema + 决策冲突

### 关键发现
- Fliki 渲染 engine = **Remotion + GKE** (Google Kubernetes Engine)
- 16s 视频渲染 50s (Remotion 0.5x 实时)
- render.latest 返回 renderRecent (最新) + renderSuccess (上次成功) 两个字段
- 4 阶段状态机: processing → processing(100%) → success+thumb → success(完成)
- resolution 只支持 720p (free plan)
- mediaGeneratedId 含 file + thumbnail + thumbnailPreview

### 渲染决策（已确认）
- 采用 **Remotion** 跟 Fliki 保持一致
- Windows 本地由 Remotion 调系统 Chrome 截帧，再调用 FFmpeg 编码 MP4
- runner 优先读取 `REMOTION_BROWSER_EXECUTABLE`，未配置时自动查找 Chrome / Edge
- 缩略图优先读取 `FFMPEG_EXECUTABLE`，未配置时从 PATH 查找 FFmpeg
- Remotion 下载的 headless shell 在本机不可执行时不再阻塞渲染

### 工程决策（已确认）
- render_jobs 表 (level/poll 同 Fliki)
- render.latest FastAPI endpoint 4s 轮询
- 渲染 worker 用 docker-compose 起 Remotion container (GKE 替代)
- Preview schema 受 free plan 限制, 推断按 UI 描述


---

## Phase 4 - 工程实施 (2026-07-23)

完成 backend 骨架与 Phase 2/3 数据层实施。

### 新增文件 (D:/workspace/Fliki视频制作还原/backend/)
- main.py - FastAPI 路由与 Fliki 字段映射
- requirements.txt - fastapi 0.115, uvicorn 0.30, pydantic 2.10
- docker-compose.yml - api + renderer 2 services
- workers/remotion_runner.py - Python subprocess 调 Remotion
- workers/remotion-project/ - 4 个 Remotion 源文件
- db/seed_styles.sql - 29 styles 已 seed
- db/seed_characters.sql - 69 characters 已 seed
- db/seed_media_samples.sql - 100 media samples 已 seed
- tests/test_characters.py - /characters 回归测试
- tests/test_remotion_runner.py - 浏览器、FFmpeg、缩略图和帧进度回归测试
- tests/test_render_progress.py - worker 事件写入 SQLite 回归测试
- IMPLEMENTATION.md - 4KB 实施文档

### 验证端点
| Endpoint | 状态 |
|----------|------|
| /health | OK |
| /styles | OK 29 个返回 |
| /media-samples | OK 100 条（50 image + 50 video） |
| /characters | OK 69 个角色，可按 gender 筛选 |
| /render.latest | OK 4 阶段 (跟 Fliki Phase 3 一致) |
| /render.create | OK POST 200 OK + jobId |
| /render.cancel | OK 主动取消 + 进程树回收 |
| /providers | OK 8 类 |

### 当前状态
- OK Schema 增量 (styles + media_samples + render_jobs + message 列)
- OK FastAPI 路由 + Pydantic aliased fields
- OK 29 styles 数据导入验证
- OK 69 characters 数据导入验证
- OK 100 media samples 数据导入验证（97 条有 prompt，3 条 OmniHuman 源数据无 prompt）
- OK Node 24 + Windows 真实 Remotion 渲染：API 任务 success，MP4 + 1280×720 thumbnail + 320×180 thumbnailPreview 全部落盘
- OK Fliki 风格进度：processing 0→…→87→93→100，最后 success 100
- OK render.cancel：API 返回 cancelled，render.latest 保持 failed + Cancelled by user
- OK 硬超时：RENDER_TIMEOUT_SECONDS 默认 900 秒，超时后任务 failed 且进程树归零

### 启动 (Local)
ffmpeg -version
$env:RENDER_TIMEOUT_SECONDS='900'
cd backend; python -m uvicorn main:app --host 127.0.0.1 --port 8001

### 启动 (Docker)
cd backend; docker-compose up

### 端口
8001 (避开 proj_055 的 8000)



## Wav2Lip-ONNX 本地模型

1. 默认路径 `backend/data/models/wav2lip/wav2lip.onnx` (与 Env-Check `FLIKI_WAV2LIP_MODEL` 默认值一致).
2. 安装 CPU 推理依赖: `python -m pip install -r backend/requirements-wav2lip.txt`.
3. 自动下载: 在 `backend/.env` 设置 `FLIKI_WAV2LIP_AUTO_DOWNLOAD=1`, 系统会在合成时尝试从 Hugging Face / GitHub / ModelScope 任一可达源拉取.
4. 手动安装 (Windows): `scripts\install_wav2lip.cmd`. 失败时把本地 wav2lip.onnx 拷到 `backend\data\models\wav2lip\wav2lip.onnx` 即可.
5. Env-Check: 启动后访问 `app/env-check.html` → Wav2Lip-ONNX 面板查看 `ok / model_present / dependency_warnings`; 模型、Python 依赖和 FFmpeg 全部存在时 `ok=True`, 否则自动回退 `static_avatar`.
