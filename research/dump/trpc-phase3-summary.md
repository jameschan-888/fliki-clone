# Phase 3 补抓摘要 — Render Pipeline + Preview

> 抓取时间: 2026-07-23 17:23 | 数据源: /api.production.fliki.ai/rpc/render.latest + preview.detail
> playbackId: 6a619e527b6a4072b66692cd

---

## 1. render.latest schema (完整状态机时间线)

### 1.1 请求

GET https://api.production.fliki.ai/rpc/render.latest,render.latest?batch=1&input={"0":{"playbackId":"..."},"1":{"playbackId":"..."}}

### 1.2 响应 schema (4 阶段)

**Phase A: processing start**
{"_id":"<id>","status":"processing","progress":0,"resolution":"720p","extension":"mp4","renderer":"gke","engine":"remotion","createdAt":"<ISO>"}

**Phase D: success (4 阶段最终)**
{
  "_id": "6a61dcceb4653e1359b04d86",
  "status": "success",
  "progress": 100,
  "resolution": "720p",
  "extension": "mp4",
  "renderer": "gke",
  "engine": "remotion",
  "createdAt": "2026-07-23T09:20:14.151Z",
  "mediaGeneratedId": {
    "_id": "6a61dd1bf1db584bb9d9b8a7",
    "type": "video",
    "file": "generated/<uid>/<file>.mp4",
    "filesAssociated": [],
    "thumbnail": "generated/<uid>/<file>_thumb.jpg",
    "thumbnailPreview": "generated/<uid>/<file>_thumbPreview.jpg"
  }
}

实际时间线: 0s(processing) → 30s(progress=93) → 46s(progress=100) → 50s(success+thumb)

### 1.3 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | ObjectId | render job ID |
| status | enum | queued / processing / success / failed |
| progress | int 0-100 | render 进度 (polling 用) |
| resolution | enum | 720p / 1080p (free 仅 720p) |
| extension | enum | mp4 / mov (free 仅 mp4) |
| renderer | enum | gke (Google Kubernetes Engine) |
| engine | enum | **remotion** ← Fliki 用 React 渲染 |
| createdAt | ISO | render job 创建时间 |
| mediaGeneratedId | Object | success 后填充, 含 _id/type/file/thumbnail |

## 2. preview.detail schema (受 free plan 限制)

### 2.1 请求
GET https://api.production.fliki.ai/rpc/preview.detail?batch=1&input={"0":{"playbackId":"..."}}

### 2.2 响应: null
当前 account 是 free plan, UI 显示 "Upgrade your plan to create preview links"
后端返回 {"data":null}

### 2.3 工程映射 (推断)
{
  "_id": "<previewId>",
  "status": "...",
  "playbackId": "<id>",
  "passcode": "<6 digits>",
  "expireAt": "<ISO>",
  "previewUrl": "<share URL>",
  "createdAt": "<ISO>"
}

## 3. 决策冲突 ⚠️

### 3.1 Fliki 用 Remotion + GKE — 用户决策 1 冲突

v5/v6 决策: "Remotion 和 FFmpeg 哪个更经济就用哪个"
Phase 3 发现: Fliki 实际用 engine=remotion + renderer=gke

Remotion 特性: React 组件化 / 浏览器内运行 / 16s 视频渲染 30s (~0.5x 实时)
GKE: Google Kubernetes Engine + Chrome headless + Remotion Lambda

### 3.2 选型对比 (本地化)

| 选项 | 一致性 | 本地部署成本 | RAM |
|------|--------|--------------|-----|
| Remotion (跟 Fliki) | 100% | 中 (Node+Chrome) | 8GB+ |
| FFmpeg | 0% (重写) | 低 (Python+ffmpeg) | 2-4GB |
| 混合: Remotion 骨架 + FFmpeg 字幕 | 50% | 中-高 | 4-8GB |

**推荐 (待你确认)**: 你原始约束是"对电脑要求低" → FFmpeg 路线。但保守起见用 Remotion 跟 Fliki 一致 (后续 bug fix 可对照 Fliki 输出)。

## 4. 数据库 schema 增量

```sql
CREATE TABLE render_jobs (
  _id TEXT PRIMARY KEY,
  playback_id TEXT NOT NULL,
  status TEXT,  -- queued/processing/success/failed
  progress INTEGER DEFAULT 0,
  resolution TEXT,  -- 720p / 1080p
  extension TEXT,  -- mp4 / mov
  renderer TEXT,  -- local / docker / gke
  engine TEXT,  -- ffmpeg / remotion
  media_generated_id TEXT,
  file TEXT,
  thumbnail TEXT,
  thumbnail_preview TEXT,
  created_at TEXT
);
```

## 5. FastAPI endpoint 草案

```python
@app.get("/render/latest")
async def render_latest(playback_id: str):
    job = db.execute("SELECT * FROM render_jobs WHERE playback_id=? ORDER BY created_at DESC LIMIT 1", playback_id).fetchone()
    if not job:
        return {"renderRecent": None, "renderSuccess": None}
    if job.status == "success":
        return {"renderRecent": job, "renderSuccess": job}
    return {"renderRecent": job, "renderSuccess": None}
```

## 6. 已知缺口

- Preview schema 完整版: 需付费 plan
- Failed render schema: 未触发, 推断字段 errorMessage/failedAt/retryable
- 多并发 render: Fliki 是否并行多个未确认
- Free plan 限速策略: 未确认

## 7. 文件位置

- research/dump/render-timeline.jsonl (1758B) — 4 阶段完整时间线
- research/dump/trpc-phase3-summary.md (本文件)
