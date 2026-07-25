# Fliki 视频制作还原：移交文档

更新时间：2026-07-25 (rev3: Docker + Remotion 本机端到端验证)

> 给下一个对话或接手开发者使用。不要看截图，不要重新抓站；现有 `research/` 已覆盖当前需要的公开页面、登录态结构和接口行为。

## 1. 项目目标

这是一个本地优先的 Fliki 风格视频创作系统，首批闭环是：

1. `Script to video`：脚本 → 可编辑场景草稿 → 用户确认 → 素材/配音/音乐 → MP4。
2. `Auto edit video`：上传视频 → 自动切分/转写 → 可编辑剪辑草稿 → 用户确认 → MP4。

核心原则：

- 先生成低成本、可编辑的草稿；用户确认前不调用素材、配音、音乐、视频生成或渲染。
- 本地部署优先、CPU 友好、不依赖付费 API 才能完成基础验证。
- 渲染采用 Remotion + 系统 Chrome + FFmpeg。
- 后端采用 FastAPI + REST + SQLite。
- Pexels/Pixabay/Freesound 默认走免费 API；各节点保留手动 Provider 配置入口。
- 数字人和声音克隆作为可选能力：Wav2Lip-ONNX、GPT-SoVITS HTTP 适配器、Edge TTS。
- 所有项目文件放在 `D:\workspace\Fliki视频制作还原`；密钥不写入文档、不提交 Git。

## 2. 当前完成度

### 结论

- 技术底座完成度：约 **84%**。
- 用户从脚本/视频到最终 MP4 的可跑通产品链路：约 **75%**。
- 还不是完整可交付产品，主要短板是前端 Avatar 选择、部署标准化、真实 Provider 的非 Mock 验证和本地数字人模型本身。

### 模块状态

| 模块 | 状态 | 说明 |
|---|---|---|
| 网站抓取与结构分析 | 已完成 | Phase 1-3 已完成；不要重复抓站 |
| FastAPI + SQLite | 已完成 | 启动、建表、兼容增量字段已落地 |
| Remotion + FFmpeg 渲染 | 已完成（含 P5D-7 avatar 浮层参数化）| 已真实生成 MP4；`Main.tsx` Scene 组件在 stock 视频按 `avatarLayout` 指定位置叠 `avatarSrc` 浮层 + fallback 红标 + 字幕避开；`workflow_pipeline._load_avatar_layout` 从 `provider_configs(wav2lip_onnx).extra.avatar_layout` 读全局配置并写入 props.json，`Main.tsx` Scene/Main 用 `resolveLayout(scene, global)` 合并；7 种 position × 3 种 shape × 1280×720/720×1280/720×720 三种 aspect |
| P5A 场景草稿 | 已完成 | 拆场景、编辑、增删、排序、版本、确认锁定和前端页面 |
| P5B 确认后流水线 | 已完成 | Stock → TTS → Music → Render 已闭环 |
| P5C Auto-edit | 已完成 | 上传、ffprobe、Whisper、静音检测、草稿编辑、确认、剪辑渲染已闭环 |
| Env-Check | 已完成 | 启动自检写入 `backend/data/env-check.json`；前端 env-check.html 新增 Wav2Lip-ONNX 明细面板（model / deps / fallback） |
| Voice Gallery | 已完成 | Edge TTS 321 个声音、142 个 locale，可试听 |
| GPT-SoVITS | 适配器完成 | 仅 HTTP 适配器；需要用户自行运行外部服务 |
| Wav2Lip-ONNX | 适配器完成 | 默认关闭；没有模型或依赖时回退静态 Avatar MP4 |
| 前端 Avatar 选择 | 已完成 | drafts 场景卡片加 Avatar 行；avatars.html 选择页 + postMessage avatar_picked；支持清除；新增 GET /avatar-clones/{uuid}/ref-face 预览接口 |
| Docker / 安装清单 | 已完成 (2026-07-25) | image fliki-api:local 3.81GB (Playwright base + Python + Node 22 + Chromium + FFmpeg), 端口 8765, volume fliki-api-data 持久化 /app/data, env_file 注入 .env；关键接口均 200，Remotion 真渲染与缩略图生成通过 |
| Git 基线 | 已完成 (2026-07-25) | commit `4a35904`, 160 文件 / 19549 行, master 分支; .gitignore 已盖 node_modules / data / .env / 测试日志 / 临时脚本 |

## 3. 已验证事实

验证时间：2026-07-24。

- Python 单元测试：`116/116` 通过（2026-07-25 全量回归, 18 个文件; 原 73 + P5D-5 avatar round-trip / 默认 null 2 个 + P5D-6 avatar 节点 + props 入口 3 个 + P5D-7 avatar_layout 顶层 / 缺字段 / 非 dict / 坏 JSON 4 个 + P5D-7b avatar_layout 嵌套在 extra / 缺 extra 2 个 + P5D-7c scene-level 合并 / patch / 校验 13 个 + P5D-8 preview kwarg / 4.919s 4 个 + P5D-8 async 后台化 4 个 + P5D 余项 _validate_image_magic 假 PNG 防御 10 个）。
- Python 编译：`python -m compileall -q .` 通过。
- 前端构建：`npm.cmd run build` 通过。
- 运行环境：Python 3.12.7、Node 24.16.0、FFmpeg 8.1.2、8 逻辑核、约 15.8 GB 内存、Intel Iris Xe、无 CUDA。
- 后端服务端口：`127.0.0.1:8001`。
- 前端开发端口：`127.0.0.1:5180`。
- 30 秒 Auto-edit 真实验证已生成约 30.03 秒 MP4，包含 H.264 视频和 AAC 音频。
- P5B 真实验证已完成 3 场景 Stock + Edge TTS + Freesound + Remotion MP4。
- 测试全部使用 Mock HTTP/ONNX，不连接付费 API，不把测试结果误写成真实外部服务验证。

## 4. 硬件与本地能力边界

当前电脑适合：

- Edge TTS、faster-whisper base、FFmpeg 剪辑、Remotion 渲染。
- Wav2Lip-ONNX 的 CPU 低分辨率测试或静态回退。
- GPT-SoVITS 作为本机或局域网 HTTP 服务的客户端。

当前电脑不适合直接承担：

- SadTalker/MuseTalk 的稳定 GPU 推理：当前无 NVIDIA/CUDA。
- 大型本地文生视频或高分辨率数字人模型。
- 同时运行多个本地大模型和 Remotion 渲染任务。

Env-Check 当前已确认：

- `gpt_sovits_cpu=true`，但 `127.0.0.1:9880` 当前没有运行服务。
- Wav2Lip-ONNX 模型文件尚未放入 `backend/data/models/wav2lip_onnx/wav2lip.onnx`。
- Wav2Lip 依赖尚不完整，缺少 `librosa`；缺模型/依赖时会回退 `static_avatar`。
- Intel GPU 不能替代 NVIDIA CUDA，因此数字人默认必须保持可选和可回退。

## 5. 目录与关键文件

项目根目录：`D:\workspace\Fliki视频制作还原`

| 路径 | 作用 |
|---|---|
| `backend/main.py` | FastAPI 入口、基础路由、渲染任务入口 |
| `backend/workflow_drafts.py` | Script-to-video 草稿 CRUD、编辑、确认锁定 |
| `backend/workflow_pipeline.py` | 确认后的 Stock/TTS/Music/Render 编排 |
| `backend/autoedit.py` | Auto-edit 上传、草稿、片段编辑和确认 |
| `backend/autoedit_pipeline.py` | Auto-edit 节点执行、FFmpeg 合成、重试 |
| `backend/provider_config.py` | Provider 配置 CRUD、默认 Provider、密钥掩码 |
| `backend/providers/` | Provider 抽象及 stock/tts/music/avatar 实现 |
| `backend/providers/tts/gpt_sovits.py` | GPT-SoVITS HTTP 适配器 |
| `backend/providers/avatar/wav2lip_onnx.py` | Wav2Lip-ONNX Avatar 适配器 |
| `backend/wav2lip_prototype.py` | Wav2Lip 推理原型和静态回退 |
| `backend/voice_gallery.py` | Edge TTS 声音列表与试听 |
| `backend/voice_clone_router.py` | 声音克隆资源和预览接口 |
| `backend/avatar_clone_router.py` | Avatar 克隆资源和 Wav2Lip 任务接口 |
| `backend/env_check.py` | Python/Node/FFmpeg/模型/硬件自检 |
| `backend/data/app.db` | 本地 SQLite 数据库 |
| `backend/data/env-check.json` | 最近一次启动自检结果 |
| `backend/db/schema.sql` | 数据库建表和兼容增量逻辑 |
| `backend/workers/remotion_runner.py` | Remotion 子进程、进度、超时、回收 |
| `backend/workers/remotion-project/src/Main.tsx` | 多场景 Remotion Composition |
| `backend/tests/` | 11 个测试模块，共 73 个用例 |
| `app/drafts.html` | Script-to-video 草稿编辑页面 |
| `app/autoedit.html` | Auto-edit 上传/编辑/确认页面 |
| `app/voices.html` | Voice Gallery 页面 |
| `app/env-check.html` | 环境检查页面 |
| `app/src/App.tsx` | 前端主逻辑和声音选择回传 |
| `app/src/api/drafts.ts` | 草稿 API 封装 |
| `research/Fliki结构分析.md` | 已登录网站结构分析 |
| `research/architecture.md` | 技术选型与架构说明 |
| `research/dump/` | 抓取的 API、Schema、样式、角色、渲染数据 |

## 6. 数据库表

当前 `backend/db/schema.sql` 定义 19 张表：

`projects`、`scenes`、`layers`、`jobs`、`provider_configs`、`media_assets`、`characters`、`styles`、`media_samples`、`render_jobs`、`workflow_drafts`、`scene_drafts`、`draft_revisions`、`workflow_runs`、`workflow_nodes`、`scene_assets`、`avatar_clones`、`voice_clones`、`edge_voices`。

草稿、工作流和数字人相关表已经落地，不要再按旧文档重新设计一套重复表结构。

## 7. 主要 API

### 基础与渲染

- `GET /health`
- `GET /styles`
- `GET /media-samples`
- `GET /characters`
- `GET /render.latest`
- `POST /render.create`
- `POST /render.cancel`
- `GET /providers`
- `GET /env-check`

### Provider 配置

- `GET /provider-configs`
- `PUT /provider-configs/{category}/{name}`

当前预置 Provider：

- Stock：`pexels`、`pixabay`
- TTS：`edge_tts`、`gpt_sovits`
- Music：`freesound`、`silence`
- Avatar：`wav2lip_onnx`

API Key 只返回 `has_api_key` 和掩码。长期配置应写入 `backend/.env`；接口传入的 API Key 当前只注入运行进程的环境变量，重启后需确认 `.env` 是否同步更新。

### Script-to-video

- `POST /workflow-drafts`
- `GET /workflow-drafts/{id}`
- `PATCH /workflow-drafts/{id}/scenes/{scene_id}`
- `POST /workflow-drafts/{id}/scenes`
- `DELETE /workflow-drafts/{id}/scenes/{scene_id}`
- `POST /workflow-drafts/{id}/reorder`
- `POST /workflow-drafts/{id}/confirm`
- `POST /workflows/script-to-video/runs/from-draft/{id}`
- `GET /workflows/{id}`
- `POST /workflows/{id}/retry`

### Auto-edit

- `POST /autoedit/uploads`
- `POST /autoedit/uploads/{id}/drafts`
- `GET /autoedit/drafts/{id}`
- `PATCH /autoedit/drafts/{id}/segments/{segment_id}`
- `POST /autoedit/drafts/{id}/reorder`
- `POST /autoedit/drafts/{id}/confirm`
- `POST /autoedit-runs/from-draft/{id}`
- `GET /autoedit-runs/{id}`
- `POST /autoedit-runs/{id}/retry`

### 声音与 Avatar

- Voice Gallery：`/voice-gallery/*`
- 声音克隆：`/voice-clones/*`
- Avatar 克隆：`/avatar-clones/*`（含 `GET /{uuid}/output` MP4 和 `GET /{uuid}/ref-face` 人脸预览图）

以 FastAPI `/docs` 的当前 OpenAPI 为准，不要只依赖旧文档中的路由数量。

### 场景草稿字段

- `scene_drafts.voice` 必填，默认 `zh-CN-XiaoxiaoNeural`，语言不一致时 `confirm` 返回 422。
- `scene_drafts.avatar` 可选，格式 `avatar:<uuid>`；非空时 `workflow_pipeline` 注入 avatar 节点（产物 `local_path`），props.scenes 含 `avatarSrc` / `avatarFallback` / `avatarMode` / `avatarName`。
- 缺模型/依赖时，avatar 节点 status=success, mode=`static_avatar`，前端在 run 面板展示 fallback。
- 已确认草稿的 avatar 字段随 `confirmed_snapshot_json` 持久化，retry run 仍可用。

## 8. Provider 配置与密钥

配置文件：`backend/.env`；模板：`backend/.env.example`。

环境变量名称：

- `PEXELS_API_KEY`
- `PIXABAY_API_KEY`
- `FREESOUND_API_KEY`
- `FLIKI_GPT_SOVITS_URL`
- `FLIKI_WAV2LIP_MODEL`
- `FLIKI_WHISPER_MODEL`
- `RENDER_TIMEOUT_SECONDS`
- `REMOTION_BROWSER_EXECUTABLE`
- `FFMPEG_EXECUTABLE`

用户提供过的 API Key 只保留在本机配置，不复制到移交文档、代码、测试或 Git。更换 API Key 后必须重启后端；付费 API 不属于测试前置条件。

## 9. 启动与验证

### 后端

```powershell
cd D:\workspace\Fliki视频制作还原\backend
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

### 前端

```powershell
cd D:\workspace\Fliki视频制作还原\app
npm.cmd run dev
```

打开：

- `http://127.0.0.1:5180/drafts.html`
- `http://127.0.0.1:5180/autoedit.html`
- `http://127.0.0.1:5180/voices.html`
- `http://127.0.0.1:5180/avatars.html`（P5E Avatar 选择；`?target=<scene_id>` 走 postMessage 回写）
- `http://127.0.0.1:5180/env-check.html`（含 Wav2Lip-ONNX 明细面板）

### 测试

```powershell
cd D:\workspace\Fliki视频制作还原\backend
python -m unittest discover -s tests -q
python -m compileall -q .

cd D:\workspace\Fliki视频制作还原\app
npm.cmd run build
```

当前已验证结果：后端单测 `145/145`、compileall 通过、前端 build 通过（含 `dist/avatars.html`）、Remotion `tsc --noEmit` 通过。

### Docker

```powershell
cd D:\workspace\Fliki视频制作还原\backend
docker compose build
docker compose up -d
```

镜像: fliki-api:local (3.81GB); base: mcr.microsoft.com/playwright:v1.49.0-jammy
端口: 127.0.0.1:8765 (避开 8001 Hyper-V); volume: fliki-api-data -> /app/data
.env 注入: env_file: - .env
已验证 200 endpoints: /health, /docs, /startup-status (state=ready), /env-check, /avatar-clones
已验证 Remotion 真渲染: H.264 + AAC, 1280x720, 1.046 秒, 59,530 bytes；同时生成 full/preview 两张 JPEG 缩略图
已验证持久化: 重启并重建容器后，探针文件与渲染视频仍存在
已验证镜像内测试: `docker run --rm ... python3 -m unittest discover -s tests -q`，`145/145` 全绿

Compose 不挂载宿主源码；Windows node_modules 会覆盖镜像内 Linux 原生依赖并导致 esbuild 平台错误。修改代码后必须重新 `docker compose build`。
Chromium 通过 `/usr/local/bin/fliki-chromium` 稳定软链接注入，避免 Playwright 版本目录变化。

构建耗时: 首次 1-2 小时; 增量 1-3 分钟
本机 Docker Desktop + WSL2 backend 需设 registry-mirrors (如 docker.m.daocloud.io)
Dockerfile 内 pip 用 mirrors.aliyun.com + default-timeout=120, npm 用 registry.npmmirror.com

## 10. 下一阶段实施顺序

### A：补前端 Avatar 选择（已完成 P5D-5）

- `drafts.html` 场景卡片新增 Avatar 行（只读输入框 + 选择 / 更换 / 清除按钮）。
- 新增 `avatars.html`：列出 `GET /avatar-clones`，通过 `postMessage({type:"avatar_picked",...})` 回写；支持 `action: "clear"`。
- 草稿 `scene_drafts.avatar` 字段持久化（`avatar:<uuid>`），确认后随 `confirmed_snapshot_json` 保留。
- `workflow_pipeline.execute_pipeline` 在 tts 后注入 avatar 节点：调用 `Wav2LipONNXAvatarProvider.synthesize(face, tts_audio, mp4)`，自动回退到 `static_avatar`；`rendered_scenes` 新增 `avatarSrc` / `avatarFallback` / `avatarMode` / `avatarName`。
- `env-check.html` 新增 Wav2Lip-ONNX 明细面板：model 路径 / 模型是否存在 / 依赖 / ffmpeg / 是否会回退 / 检测耗时；不可用时给出回退提示。
- `avatar_clone_router` 新增 `GET /{uuid}/ref-face` 用于前端预览人脸图。
- 单测覆盖：`avatar` 字段 round-trip + 创建时默认为 null；`init_db` 兼容迁移同时验证 `voice` 和 `avatar` 列。
- 受影响文件：`backend/db/schema.sql`、`backend/main.py`、`backend/workflow_drafts.py`、`backend/workflow_pipeline.py`、`backend/avatar_clone_router.py`、`backend/tests/test_workflow_drafts.py`、`app/src/types/draft.ts`、`app/src/api/drafts.ts`、`app/src/App.tsx`、`app/vite.config.ts`、`app/index.html`、`app/avatars.html`（新建）、`app/env-check.html`。

### A2：P5D 余项 (已完成 2026-07-25)
- `Main.tsx` `AvatarLayout` 加 `shapeBorderRadii?: { circle?, rounded?, square? }`, `resolveLayout` 重写按 shape 选 radius (shapeBorderRadii[shape] ?? 默认); circle 自动 = max/2, rounded = borderRadiusPx, square = 0. `avatarBoxStyle` 移除 shape if/else 块, 统一用 resolveLayout 算好的 borderRadiusPx.
- `avatar_clone_router.py` 加 `_IMAGE_MAGIC` dict + `_validate_image_magic(path, ext)` 函数, size < 256 之后调用. PNG: 89 50 4E 47 0D 0A 1A 0A; JPEG: FF D8 FF; WebP: RIFF; BMP: BM; GIF: GIF87a/GIF89a. 假 PNG / 扩展名伪造 -> 422.
- 新增 `backend/tests/test_avatar_image_magic.py` (10 case, 0.040s 全绿).
- 受影响文件: `backend/workers/remotion-project/src/Main.tsx`, `backend/avatar_clone_router.py`, `backend/tests/test_avatar_image_magic.py`, `scripts/patch_p5d7c_shape_radius.py`, `scripts/patch_p5d7c_shape_radius_followup.py`, `scripts/patch_avatar_magic_check.py`, `scripts/run_tests.js` (rev3).


### B：修正 Provider 密钥持久化

- 明确区分“接口临时注入”与“本地持久配置”。
- 优先支持 `.env` 或本地加密配置文件，不把明文 API Key 回传给前端。
- 增加重启后配置仍然可用的测试。

### C：完成可交付部署基线

- 建立项目专用 `.venv` 和安装清单。
- 真实验证 Docker compose；补充 Windows 本地启动脚本。
- ~~做首次 Git 基线提交~~ ✅ 已完成 (commit 4a35904): `HANDOFF.md` + `HANDOFF_P5D7_short.md` + `PROJECT_STATUS_AND_PLAN.md` + `README.md` + `Fliki项目交接文档.docx` + `voice-gallery.png` + `backend/` + `app/` + `scripts/` + `research/` + `.gitignore`。历史辅助脚本 (build_handoff_docx.py / check_*.py / write_*.py / reset*.py / rewrite_props*.py / finalize.py / count_p5a.py) 已排除，根级仅保留交付文档 + 项目源码。

### D：按硬件限制补本地 AI

- Wav2Lip-ONNX：先 CPU、低分辨率、短视频验证；模型缺失时保留静态回退。
- GPT-SoVITS：继续保持 HTTP 适配器，不把大模型嵌入主服务。
- SadTalker/MuseTalk：当前 Intel 无 CUDA，不作为本机默认路径；后续可接局域网 GPU 机器或兼容 API。

## 11. 已知风险

- 本机内存可用量较低，运行 Remotion、Whisper 和浏览器时不要同时启动多个 Python 服务。
- Wav2Lip 适配器已完成，不等于模型推理已在本机完成；当前 Env-Check 明确显示模型和依赖缺失。
- GPT-SoVITS 适配器测试是 Mock，不代表 `127.0.0.1:9880` 服务已启动。
- Pexels/Pixabay/Freesound 的密钥配置已预留，但网络、额度、授权和真实下载仍应单独验收。
- 当前 Git 仓库没有首次提交；后续操作前建议先建立基线，避免交接后无法回滚。
- `README.md` 仍保留部分早期阶段描述，本次只更新移交文档和状态计划，后续应统一 README，避免三份进度信息漂移。

## 12. 交接时的固定开场

下一个对话直接执行：

> 读取 `D:\workspace\规矩文档.txt`、`D:\workspace\踩坑日志.txt`、`D:\workspace\Fliki视频制作还原\HANDOFF.md`，进入 `D:\workspace\Fliki视频制作还原`。不要看截图，不要重新抓站。先运行 `python -m unittest discover -s tests -q`，然后从 P5D-5 前端 Avatar 选择和 Provider 密钥持久化开始。


### A + C（P5D-7：avatar 浮层参数化 + 真实端到端 2026-07-24 收尾）

**完成：**
- `Main.tsx` SceneProps 加 `avatarLayout?`、MainProps 加 `aspectRatio` / `avatarLayout`；`resolveLayout(scene, global)` 合并覆盖；`avatarBoxStyle` 按 position 计算 top/left/right/bottom；`subtitleReserve` 让字幕避开浮层；7 position × 3 shape × 3 aspect。
- `workflow_pipeline._load_avatar_layout(connection)` 从 `provider_configs(category="avatar", name="wav2lip_onnx").config_json` 读 `avatar_layout`，优先 `extra.avatar_layout`（PUT `/provider-configs/.../...` 把 extra 整体塞 config_json），fallback 顶层 `config_json.avatar_layout`，非 dict 视作 None。`execute_pipeline` 在 props dict 写 `avatarLayout` 字段。
- 修 bug：`synthesize_scene_avatar` 第一行 `scene.get("avatar")` 在 sqlite3.Row 上 `AttributeError`，已改 `scene["avatar"]`（与项目历史 P5D-6 同坑）。
- 新单测 `tests/test_p5d7_avatar_layout.py`（4 个）+ `tests/test_p5d7b_avatar_layout_extra.py`（2 个）：覆盖顶层字段、字段缺失、非 dict、坏 JSON、extra 嵌套、缺 extra 6 种情况。
- **真实端到端**（run `b11af87ec70244378d3d95c54003f997`）：avatar_clone → workflow_draft → scene PATCH avatar → PUT provider avatar_layout (top-left, 240×240 circle) → confirm → from-draft → 后台渲染 → `7a463d9274b04b4fbb27badd/7a463d9274b04b4fbb27badd.mp4` 1.27 MB 1280×720 H.264 + AAC 3.28s；props.avatarLayout 真传到 props.json。
- 期间发现的输入校验：`avatar-clones` POST 拒绝 < 256B PNG；`wav2lip_prototype._fallback_static` ffmpeg 对假 PNG（header + 1024×0x00）会卡死，对真 PNG（256×256 91 KB）单测 0.33s 完成。

**未做（受硬件/时间限制）：**
- scene 级 avatar_layout 覆盖字段（当前所有 scene 共享 global；SceneProps 已支持，但 ScenePatchBody 没加 avatar_layout）。
- Per-shape border radius 字段（当前固定 shape → borderRadiusPx 映射）。

**影响文件：**
- `backend/workflow_pipeline.py`（加 `_load_avatar_layout` helper + props avatarLayout 字段 + 修 synthesize_scene_avatar Row.get bug）
- `backend/workers/remotion-project/src/Main.tsx`（已在上轮完成：AvatarLayout / AvatarPosition / AvatarShape / AspectRatio / resolveLayout / avatarBoxStyle / subtitleReserve）
- `backend/tests/test_p5d7_avatar_layout.py`（新建 4 个 case）
- `backend/tests/test_p5d7b_avatar_layout_extra.py`（新建 2 个 case）
- `HANDOFF.md`（本文）
- `D:\workspace\踩坑日志.txt`（追加 P5D-7 5 条）


## 13. 本次文档变更

- 更新：`D:\workspace\Fliki视频制作还原\HANDOFF.md`（P5D-7 avatar 浮层参数化 + 真实端到端）
- 更新：`D:\workspace\踩坑日志.txt`（追加 P5D-7 5 条坑）
- 新建：`backend/tests/test_p5d7_avatar_layout.py`（4 个 case）
- 新建：`backend/tests/test_p5d7b_avatar_layout_extra.py`（2 个 case）
- 修改：`backend/workflow_pipeline.py`（helper + props 字段 + Row.get 修复）
- 上轮已修改：`backend/workers/remotion-project/src/Main.tsx`（Main.tsx SceneProps / AspectRatio）
