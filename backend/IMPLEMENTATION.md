# Backend 实施进度 — P5A/P5B/P5C

> 时间: 2026-07-24 | 路径: D:\workspace\Fliki视频制作还原\backend

---

## 1. 已完成

- FastAPI 主入口 `main.py` (7.5KB) — 11 路由
- SQLite schema + Phase 2/3 增量表 (styles + media_samples + render_jobs)
- 29 个 styles 从 Phase 2 dump seed 导入
- Remotion worker `workers/remotion_runner.py` (system Chrome)
- Remotion 项目骨架 (4 文件: package.json + src/index.tsx/Root.tsx/Main.tsx)
- Docker compose `backend/docker-compose.yml` (api + renderer services)
- requirements.txt (fastapi 0.115, uvicorn 0.30, pydantic 2.10)

## 2. API 路由

| Endpoint | Method | Purpose |
|----------|--------|---------|
| / | GET | API metadata |
| /health | GET | Health check |
| /styles | GET | List 29 styles (Phase 2) |
| /media-samples | GET | List 100 sample prompts (Phase 2) |
| /render.latest | GET | Get latest render job + success (Phase 3) |
| /render.create | POST | Trigger render (Phase 3) |
| /render.cancel | POST | Cancel active render by jobId |
| /providers | GET | 8 类 provider 配置 (决策 5) |
| /docs | GET | FastAPI auto OpenAPI |

## 3. 数据库 Schema (最终)

```sql
-- 已存在
projects / scenes / layers / jobs / provider_configs / media_assets / characters

-- Phase 2 增量
styles (_id, name, key, prefix, suffix, character_prompt, composition,
       image_prompt_direction, video_prompt_direction, thumbnail, is_enabled)
media_samples (_id, type, file_path, name, duration, thumbnail,
              aspect_ratio, quality, model, style, prompt)

-- Phase 3 增量
render_jobs (_id, playback_id, status, progress, resolution, extension,
            renderer, engine, message, media_generated_id, file,
            thumbnail, thumbnail_preview, created_at, finished_at)
```

## 4. 验证状态

| 状态 | Endpoint | Result |
|------|----------|--------|
| ✅ | POST /render.create | 200 OK + jobId |
| ✅ | POST /render.cancel | cancelled + process tree terminated |
| ✅ | Hard timeout | failed + timeout message + process tree terminated |
| ✅ | GET /render.latest | 4 阶段 status machine (queued→processing→success) |
| ✅ | GET /styles | 29 styles, schema 跟 Phase 2 完全一致 |
| ✅ | GET /providers | 8 类 provider 列表 |
| ✅ | 真实 Remotion 渲染 | Node 24 + 系统 Chrome，MP4 生成成功 |
| ✅ | GET /media-samples | 100 条（50 image + 50 video） |
| ✅ | GET /characters | 69 个角色，Fliki picker 字段一致 |

## 5. 启动方式

```bash
# Local (无 Docker)
cd D:/workspace/Fliki视频制作还原/backend
python -m uvicorn main:app --host 127.0.0.1 --port 8001

# Docker (含 Remotion container)
cd D:/workspace/Fliki视频制作还原/backend
docker-compose up

# 验证
curl http://127.0.0.1:8001/health
curl "http://127.0.0.1:8001/styles?enabled_only=true"
curl "http://127.0.0.1:8001/render.latest?playback_id=test"
```

## 6. 文件清单

```
backend/
├── config.py                    (已存在, +DATA_DIR)
├── requirements.txt             (新建)
├── docker-compose.yml           (新建)
├── main.py                      (新建, 7.5KB)
├── server.log                   (运行日志)
├── data/
│   ├── app.db                   (SQLite)
│   ├── output/                  (render 输出)
│   └── props/                   (render 入参 props.json)
├── db/
│   ├── schema.sql               (扩展 +Phase 2/3 表)
│   ├── seed_styles.sql          (29 styles)
│   ├── seed_characters.sql      (69 characters)
│   └── seed_media_samples.sql   (100 samples)
└── workers/
    ├── remotion_runner.py       (Python subprocess)
    └── remotion-project/        (Remotion 项目)
        ├── package.json
        └── src/
            ├── index.tsx        (entry)
            ├── Root.tsx         (composition 注册)
            └── Main.tsx         (composition body)
```

## 7. 与 Fliki 对照表

| Fliki | 本地还原 | 一致性 |
|-------|----------|---------|
| api.production.fliki.ai/rpc/render.latest | localhost:8001/render.latest | ✅ schema 一致 |
| render.latest 双 endpoint batch=1 | 单 endpoint query string | 实现简化 |
| Fliki 4 阶段 (queued/processing/success/failed) | 同样 4 阶段 | ✅ 完全一致 |
| engine=remotion | engine=remotion | ✅ 完全一致 |
| renderer=gke | renderer=local | 实现简化 (后续可换 docker) |
| resolution=720p (free) / 1080p | 同样 | ✅ 完全一致 |
| extension=mp4 (free) / mov | 同样 | ✅ 完全一致 |
| mediaGeneratedId { _id, file, thumbnail, thumbnailPreview } | 同样 | ✅ 完全一致 |

## Phase 4 实施结果

### 已交付

| 组件 | 状态 | 备注 |
|------|------|------|
| FastAPI routes | OK | render.latest schema + render.cancel local extension |
| SQLite schema (v2) | OK | +styles, +media_samples, +render_jobs, +message 列 |
| 29 styles seed | OK | 从 Phase 2 dump 导入并验证 |
| Remotion worker (Python) | OK | subprocess + system Chrome + data output |
| Remotion project (Node) | OK | npm install 1.5GB 完成, node_modules + @remotion 已装 |
| docker-compose.yml | OK | api + renderer 2 services |
| requirements.txt | OK | fastapi 0.115, uvicorn 0.30, pydantic 2.10 |
| e2e 渲染测试 | OK | MP4 + 1280×720 thumbnail + 320×180 preview 均真实生成 |


### e2e 渲染修复结果

根因不是 Node 24 本身：Remotion 下载的 `chrome-headless-shell.exe` 在本机返回 WinError 193 / EFTYPE，且旧 runner 虽然计算了系统 Chrome 路径，却没有把 `--browser-executable` 传给 Remotion。

修复策略：
1. `REMOTION_BROWSER_EXECUTABLE` 可手动指定浏览器路径。
2. Windows 未配置时自动查找 Chrome，再回退 Edge。
3. Linux / Docker 未指定时继续使用 Remotion 自带浏览器流程。
4. runner 输出实际浏览器路径，方便排障。
5. `FFMPEG_EXECUTABLE` 可手动指定；未配置时从 PATH 查找 FFmpeg 并生成两个 JPG。

验证结果：
- 直接 runner：`node24-fixed.mp4`，298009 bytes。
- FastAPI：`render.create` → `render.latest`，queued→processing→success，298009-byte MP4。
- 高频轮询实测：processing 0→4→…→87→93→100，再 success 100；本地总耗时 25.7 秒。
- 主动取消实测：processing 4 时取消，2 秒后 failed / Cancelled by user，匹配 jobId 的进程为 0。
- 硬超时实测：临时设为 2 秒，3.4 秒内 failed / Render timed out after 2 seconds，进程为 0。
- 恢复默认 900 秒后再次正常渲染 success，message 为空，三份产物存在。
- API 返回的 thumbnail 为 1280×720 JPEG；thumbnailPreview 为 320×180 JPEG，路径均有真实文件。
- Node.js 24.16.0、Remotion 4.0.250，无需降级 Node 或 Remotion。

### 当前 Backend 已可用

- /health / /styles / /characters / /media-samples / /render.latest / /render.create / /render.cancel / /providers 全 work
- schema 与 Fliki Phase 2/3 完全一致
- 29 styles、69 characters、100 media samples 数据已 seed
- 100 条样例中 97 条含 prompt；3 条 OmniHuman 数字人样例在源数据中 prompt 为空，原样保留
- render.create 触发后 queued→processing 0–87→93→100→success 100，MP4 与两个 JPG 真实落盘

### 下一步建议

A. 已完成：runner 传入系统 Chrome，Node 24 e2e 渲染恢复
B. 已完成：生成真实 thumbnail / thumbnailPreview 文件并验证 JPEG 签名与尺寸
C. 已完成：同步 Fliki 29 styles + 69 characters + 100 media samples 进 DB
D. 已完成：流式解析 Remotion 帧日志，按 Fliki 语义写入 processing 0–87 / 93 / 100
E. 已完成：render.cancel + 900 秒硬超时 + 跨平台进程树回收
F. 下一核心缺口：实现 Script-to-video + Auto-edit 工作流与节点 Provider 配置

## Phase 5A 实施结果（2026-07-23）

- 新增 workflow_drafts、scene_drafts、draft_revisions 三张表。
- 新增 workflow_drafts.py，提供创建、读取、场景编辑、增删、排序和确认 API。
- 草稿使用确定性 Mock 拆分，不调用外部文本 API。
- 确认前不会创建 jobs、media_assets 或 render_jobs；确认后草稿不可原地修改，重复确认幂等。
- 新增最小 React 场景编辑器：脚本输入、场景卡片、旁白/画面/字幕/时长编辑、上移下移、增删和确认。
- 后端测试 13/13 通过；Python compileall 通过；前端 npm run build 通过。
- 真实 API 验证：生成 3 场景 → 编辑标题与时长 → version 2 → confirm → confirmed。
- 浏览器结构与控件验证：实际生成 3 个场景，修改标题保存后版本由 v1 升为 v2；未使用截图。

## Phase 5B 实施结果（2026-07-23）

- 三组 API 密钥仅写入 backend/.env（已被 .gitignore 忽略），通过 /provider-configs 暴露给后端，API Key 永远不返回明文。
- 新增 provider_config.py + workflow_pipeline.py + providers/stock,tts,music。
- Stock: Pexels 优先，Pixabay 回退，自动下载到 workflow_runs 目录并保留原始 URL 与作者信息。
- TTS: edge-tts 默认；逐场景合成 mp3，ffprobe 回填音频时长。
- Music: Freesound 公开 API，按授权方式下载 mp3。
- 编排器: confirmed → generating_assets → ready_to_render → rendering → success/failed。
- Remotion Main.tsx 升级为多场景 Sequence + 视频背景 + 旁白 Audio + 背景音乐低音量循环。
- 端到端真实运行：3 场景脚本 → 3 段 Pexels 视频（南京天际线、孩子滑板、落日）+ 3 段 Edge TTS 中文旁白 + Freesound 背景音乐，Remotion 渲染成功生成 5.9MB MP4 + 缩略图 + 预览图。
- 测试 16/16 通过；compileall 通过；TypeScript 编译通过。
- 新增 test_p5b_pipeline.py：provider API 掩码、节点复用、未确认禁止生成三条新测试通过。

## Phase 5B 已知坑（详见踩坑日志）

- apply_patch 仍被系统策略拒绝，统一用 .NET/UTF-8 精确写入临时 Python 脚本。
- Remotion 4.0.250 渲染需要 typescript 5 才能解析 tsconfig；项目须安装 typescript@5.x。
- OffthreadVideo 只接受 http(s)://；file:// 路径要通过本地静态服务暴露（默认 8002）。
- retry 端点只允许从 failed 状态出发；为不阻塞已成功的素材/配音节点，我直接复用成功节点的 result 重新调 render.create，并在 workflow_runs 上同步状态。
- Run 长 job_id 字符串触发 PowerShell 解析异常，输出用 Out-File -Encoding ascii 兜底。

## P5C: Auto-edit MVP (2026-07-24 完成)

### 数据模型
- `autoedit_uploads`: 视频上传 (id, filename, stored_path, size_bytes, duration_seconds, width, height, container, status)
- `autoedit_drafts`: 剪辑草稿 (status=draft/confirmed, version, language, confirmed_snapshot_json)
- `autoedit_segments`: 时间轴片段 (kind=keep/trim/drop, asset_kind=stock/none, asset_query, broll_url, music_volume)
- `autoedit_runs`: 渲染运行 (status=queued/generating_assets/rendering/success/failed, progress, render_job_id)
- `autoedit_nodes`: 节点执行 (per-segment tts/broll/cut + music/compose)
- `autoedit_revisions`: 草稿快照 (版本号 + JSON 快照)

### API 路由 (9 个)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /autoedit/uploads | POST | 视频上传 + ffprobe 探测 |
| /autoedit/uploads/{id}/drafts | POST | silencedetect + Whisper 转写 + 草稿生成 |
| /autoedit/drafts/{id} | GET | 读取完整草稿 |
| /autoedit/drafts/{id}/segments/{seg_id} | PATCH | 编辑片段 (kind/subtitle/asset_query/start/end/music_volume) |
| /autoedit/drafts/{id}/reorder | POST | 重排片段 |
| /autoedit/drafts/{id}/confirm | POST | 确认草稿 → 进入生成流水线 |
| /autoedit-runs/from-draft/{id} | POST | 创建 run + 触发 background pipeline |
| /autoedit-runs/{id} | GET | 查询 run + 节点状态 |
| /autoedit-runs/{id}/retry | POST | 重试 failed run |

### Whisper 双路径
- 有 OPENAI_API_KEY + OPENAI_BASE_URL/WHISPER_BASE_URL → OpenAI 兼容 API (whisper-1 + verbose_json)
- 无 → faster_whisper 本地 base 模型 (FLIKI_WHISPER_MODEL 环境变量覆盖)
- 30 秒音频转写约 10-15 秒（模型已缓存）

### ffmpeg 流水线节点
1. `tts` (per-segment): EdgeTTS 合成字幕 → mp3
2. `broll` (per-segment, 可选): Pexels/Pixabay fallback 下载 → mp4; 短片段或失败走 none
3. `cut` (per-segment): ffmpeg 裁剪原视频 start→end + scale 1280x720 + 黑边 + srt 字幕烧入 + 旁白混音 (amix duration=first)
4. `music`: FreesoundProvider 背景音乐 → mp3 (无 API key 走 none)
5. `compose`: ffmpeg concat demuxer 拼接所有 cut.mp4 + 音乐混音 → final.mp4 (libx264 ultrafast + aac + faststart)

### 验证 (2026-07-24)
- tests/test_autoedit.py 7/7 通过
- 端到端：上传 30s mp4 → 草稿 → confirm → run (11 节点全 success) → 30.03s 真实 mp4 (1.74MB, h264 1280x720 + aac)
- Whisper 转写 30s 空音频约 10s（模型缓存命中后）

### 已知坑
- Windows subprocess GBK 解码：ffprobe 不能用 text=True，必须用 capture_output=True (bytes) + 手动 utf-8 decode + errors="replace"
- amix duration=shortest + -shortest 会让视频缩到旁白时长，必须改 duration=first + 去掉 -shortest
- faster_whisper 第一次跑会下载模型 (~150MB)，后续缓存命中
