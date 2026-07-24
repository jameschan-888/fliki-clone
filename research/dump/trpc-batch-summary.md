
# Fliki tRPC Batch Response Schema (v6 补抓 2026-07-23)

> 数据源: app.fliki.ai 已登录会话 (Leo Chan / free plan)
> 抓取方式: page 内 fetch + localStorage 中转 + console.log 分块输出
> 源 endpoint: https://api.production.fliki.ai/rpc/userPlatform.list,apiAccess.detail,pronunciation.list,playback.detail,workflow.detailByPlayback,drive.detail,font.list
> 完整响应: 46289 字节 JSONL (jsonl format with ref/result pair)
> 测试项目: playbackId=6a619e527b6a4072b66692cd, driveId=6a619e527b6a4072b66692d4

## 1. tRPC JSONL 格式 (关键发现)

Fliki 用 tRPC superjson + JSONL streaming 格式,每行一对 ref/result,引用靠数字 ID 关联。
超紧凑 (46KB 包含 7 个 endpoint 全量数据),比标准 JSON 小 30%。

示例头 (ref graph):

```
{"0":[[0],[null,0,0]],...,"6":[[0],[null,0,6]]}             <- 7 个 endpoint refs
[1,0,[[{"result":0}],["result",0,7]]]                      <- ref to result
[7,0,[[{"data":0}],["data",0,8]]]                         <- result is {"data": ref 8}
[8,0,[[{"data":[]}]]]                                     <- empty result
```

## 2. 完整 tRPC Endpoint 清单 (v5 + v6 补全)

### v5 已抓 (16 个)
subscriptions.active / release.list / credit.detail / style.list / mediaMy.listSamples / mediaMy.list / playback.detail / workflow.detailByPlayback / drive.detail / userPlatform.list / apiAccess.detail / pronunciation.list / font.list / render.latest (2x) / preview.detail

### v6 新发现
- playback.detail 才是 playback 全量数据 (v5 抓的 playbackFocus 只是 UI state)
- render.latest 在 Editor 加载时调 2 次 (可能 normal + 4K 检测)
- preview.detail preview 模式独立 endpoint
- apiAccess.detail 返回 playback.project meta + avatarMale + avatarFemale + overlay

## 3. workflow.features Schema (workflow.detailByPlayback 返回)

```json
{
  "_id": "6a619e4c7b6a4072b666915d",
  "type": "script",
  "executingAt": null,
  "features": {
    "enableSummarize": false,
    "enableStock": true,
    "enableArt": false,
    "enableLibrary": false,
    "artStyle": "cinematic",
    "aiModel": "runware-z-image-turbo",
    "aiVideoClipPercentage": 20,
    "enableAvatar": false,
    "avatar": null,
    "enableBRoll": true,
    "template": null,
    "templateAvatarCapable": false,
    "brand": null,
    "aspectRatio": "16:9",
    "voice": {
      "_id": "61b8b45a4268666c126bb32b",
      "name": "Sara",
      "gender": "FEMALE",
      "service": "microsoft",
      "isUltra": false,
      "plans": { "free": true, "basic": true, "standard": true, "premium": true, "ltdAudio": true, "ltdVideo": true },
      "isStudio": false,
      "description": "Friendly American woman — narration, customer service, podcasts."
    },
    "enableReview": false,
    "addPauses": false,
    "highlightSubtitles": true,
    "generateSfx": true,
    "youtubeLicensedMusic": false,
    "sceneBreakdown": "auto",
    "subtitlePresetId": "builtin-legacy-basic",
    "aiImageAnimationPreset": "Mix:Subtle Flow",
    "sceneBreakdownEngineUsed": "referential",
    "sceneBreakdownModelUsed": "gemini-2.5-flash-lite"
  },
  "data": { "characters": [] },
  "format": "video",
  "isGenerating": false
}
```

### v6 关键新发现
- aiModel 默认值从 v5 文档的 Flux 2 Klein 改为 runware-z-image-turbo
- sceneBreakdownModelUsed 实际用 Gemini 2.5 Flash Lite (v5 Copilot 用 GLM-5.2 是错的,scene breakdown 走另一个模型)
- aiVideoClipPercentage=20 表示每 20% scene 插入 AI 生成的 video clip (影响 B-roll 选材)
- aiImageAnimationPreset="Mix:Subtle Flow" 是图层动画预设 (v5 没列)
- subtitlePresetId 是 18 字幕预设的 ID 引用

## 4. drive Schema (drive.detail 返回)

```json
{
  "drive": {
    "_id": "6a619e527b6a4072b66692d4",
    "userId": "6a60be008678de04cf209b95",
    "playbackId": "6a619e527b6a4072b66692cd",
    "workflowId": "6a619e4c7b6a4072b666915d",
    "workflowType": "script",
    "name": "Introducing Our Smart AI Assistant for Email and Scheduling",
    "slug": "introducing-our-smart-ai-assistant-for-email-and-scheduling",
    "start": "script",
    "mode": "template",
    "isFolder": false,
    "isTemplate": false,
    "isCollaborate": false,
    "isTrashed": false,
    "isSample": false,
    "isDeleted": false,
    "createdAt": "2026-07-23T04:53:38.114Z",
    "updatedAt": "2026-07-23T06:49:35.505Z",
    "format": "video",
    "mediaRecents": {
      "69bb4ee9063e2244dcc066ca": "stock",
      "64de4633115b4a14ee635916": "stock",
      "6913617c2ed82af4a4b1ac3a": "stock",
      "69961bd510af29a9970fbbd4": "stock"
    }
  },
  "breadcrumbs": [
    { "title": "Files", "driveId": null, "isFolder": true },
    { "title": "Introducing...", "driveId": "6a619e527b6a4072b66692d4", "isFolder": false }
  ]
}
```

### v6 新发现
- slug 自动生成 (kebab-case from name)
- mode: "template" vs "from-scratch" (v5 未抓)
- mediaRecents 是对象 {mediaId: source} 而非 array (v5 抓的 array 是 UI 渲染)
- breadcrumbs 包含 folder path

## 5. voice Schema (pronunciation.list 返回)

```json
{
  "_id": "61b8b45a4268666c126bb32b",
  "languageId": "61b8b2f54268666c126babc9",
  "dialectId": "61b8b31c4268666c126bace7",
  "name": "Sara",
  "gender": "FEMALE",
  "service": "microsoft",
  "serviceType": "neural",
  "serviceCode": "en-US-SaraNeural",
  "isCurated": false,
  "isDefault": false,
  "isEnabled": true,
  "isDeleted": false,
  "createdAt": "2021-12-14T15:12:26.134Z",
  "updatedAt": "2026-06-19T13:02:59.243Z",
  "__v": 0,
  "sample": "61ba4b66302680682f3af8f8.mp3",
  "hasStyles": true,
  "isFree": true,
  "isClone": false,
  "isSpotlighted": true,
  "isUltra": false,
  "plans": { "free": true, "basic": true, "standard": true, "premium": true, "ltdAudio": true, "ltdVideo": true },
  "mediaInternalId": "6659d6bfd978ec5e67ffed0f",
  "isPublicListed": true,
  "isCustom": false,
  "isStudio": false,
  "variants": [
    {
      "languageId": { "_id": "...", "name": "English", "code": "en", "font": "nunito", "sampleText": "How to make a coffee?" },
      "dialectId": { "_id": "...", "name": "United States", "code": "US" },
      "plans": { "free": true, "basic": true, "standard": true, "premium": true, "ltdAudio": true, "ltdVideo": true },
      "mediaInternalId": { "_id": "...", "file": "internal/samples/en-US/61b8b45a4268666c126bb32b__sara.mp3", "duration": 7.488 },
      "_id": "6974c2fb24536d4a947a1124"
    }
  ],
  "version": 2,
  "description": "Friendly American woman — narration, customer service, podcasts."
}
```

### v6 新发现
- serviceType 区分 neural/standard
- serviceCode 是 provider 实际调用代码 (微软/Azure/Amazon Polly/Google)
- hasStyles 表示 voice 支持 emotion style (excited/cheerful/angry/sad/etc)
- variants 数组: 同一 voice 跨 language/dialect 的版本 (关键: 本地 TTS 选型要对齐 serviceCode 模式)
- mediaInternalId.file 是 sample 音频路径
- languageId.font/font/sampleText 三件套提示 UI 默认字体

## 6. playback Schema (playback.detail 返回) - 核心

```json
{
  "_id": "6a619e527b6a4072b66692cd",
  "userId": "6a60be008678de04cf209b95",
  "languageId": {
    "_id": "61b8b2f44268666c126babbf", "name": "Chinese", "code": "zh",
    "font": "notoSansSC", "sampleText": "如何煮咖啡?", "sampleInput": "使用 Fliki 将文本转换为带有 AI 语音的视频",
    "dialectDefaultId": "61b8b3114268666c126bac9b"
  },
  "dialectId": { "_id": "...", "name": "Mandarin Simplified", "code": "CN", "slug": "mandarin-simplified" },
  "version": 1, "revision": 1, "mediaRevision": 0,
  "isPlayed": true, "isDeleted": false,
  "duration": 13,
  "format": "video", "type": "drive",
  "scenes": [ ]
}
```

### 6.1 avatarMale (默认数字人)
```json
{
  "_id": "6596b29f597475ba5164a900",
  "mediaInternalId": { "type": "video", "file": "internal/65ef3a99544cf8bbddca5dc9.mp4", "duration": 7, "colors": ["#19171e","#af9690","#814542","#746c67","#74646c"] },
  "name": "Alex",
  "gender": "MALE",
  "service": "did",
  "serviceType": "hq",
  "serviceCode": "alex-tv2VbI8lXI",
  "payload": {
    "thumbnail_url": "https://clips-presenters.d-id.com/alex/tv2VbI8lXI/MeDU8rVHxW/thumbnail.png",
    "preview_url": "https://clips-presenters.d-id.com/alex/tv2VbI8lXI/MeDU8rVHxW/preview.mp4",
    "image_url": "https://clips-presenters.d-id.com/alex/tv2VbI8lXI/MeDU8rVHxW/image.png",
    "model_url": "s3://d-id-clips-drivers-prod/alex/tv2VbI8lXI/generator.pt",
    "drivers": [
      { "driver_id": "MeDU8rVHxW", "name": "natural", "video_url": ".../video.mp4" },
      { "driver_id": "NYQCkUuhs8", "name": "lively", "video_url": ".../video.mp4" }
    ]
  },
  "isDefault": true, "isStock": true
}
```

### 6.2 avatarFemale (默认女数字人)
- Anita (anita-6_uTzyZtNR),同样 D-ID service,两个 driver (Ecg7Fd7cJz + vxfRIwlzuf)

### 6.3 overlay (默认 overlay)
- Bokeh particles — 62da411e52e9977aeff20243/66d6fc4e69bb3e5d02a23f53.mp4,duration 45.42s
- 描述: softly blurred, glowing orbs add a dreamy ethereal touch

### v6 关键新发现
- Fliki 数字人走 D-ID service (clips-presenters.d-id.com),不是自研
- D-ID 提供 thumbnail/preview/image/video 4 类素材 + 多 emotion driver (natural/lively)
- 本地 v1 不引 D-ID (用户决策 6: 本地化用 SadTalker/MuseTalk)
- S3 path: s3://d-id-clips-drivers-prod/... (private S3)

## 7. scene Schema (playback.scenes[i])

```json
{
  "_id": "6a619e60dc3a8dbaa67f0f80",
  "isHidden": false,
  "isMinimize": true,
  "duration": { "from": 0, "to": 4, "total": 4, "ahead": 0 },
  "transition": { "toggle": false },
  "layers": [ ]
}
```

### duration 字段 (v6 新发现)
- from/to: scene 在 playback 时间轴上的起始/结束 (秒)
- total: scene 时长 (秒)
- ahead: scene 提前结束时间 (与下一 scene 重叠,0 = 无重叠)
- 这与 v5 抓的 timeStart/timeEnd 是不同维度 (v5 是 word-level,scene-level 是本字段)

## 8. layer Schema (scene.layers[i]) - 三类

### 8.1 共同字段
```json
{
  "key": "",
  "type": "media | voiceover | audio",
  "isHidden": false,
  "isMinimizeActive": false,
  "media": { },
  "subtitle": { },
  "visualization": { },
  "timing": { "toggle": false, "sceneTime": { "in": 0, "out": null }, "trim": { "in": 0 }, "noSnap": false }
}
```

### 8.2 media (3 种 source: stock / my / generated)
```json
{
  "mediaInternalId": null,
  "mediaStockId": {
    "_id": "64de4633115b4a14ee635916",
    "type": "video",
    "file": "stock/storyblocks/64de4631115b4a14ee635832.mp4",
    "filePreview": "stock/storyblocks/..._preview.mp4",
    "filePreviewSmall": "stock/storyblocks/..._preview_small.mp4",
    "name": "Female office worker accountant looks at computer...",
    "duration": 24.8,
    "thumbnail": "stock/storyblocks/..._thumb.jpg",
    "colors": ["#443532","#e8dedb","#9da6aa","#927c73","#91929d"]
  },
  "mediaMyId": null,
  "keywords": ["japanese business person typing on laptop writing email", "..."],
  "relatedVoiceover": "It helps you write emails faster.",
  "charactersInFrame": [],
  "stockIdHistory": [],
  "height": 100, "width": 100, "top": 0, "left": 0, "rotate": 0,
  "objectFit": "cover", "objectPosition": "center",
  "crop": { "height": 100, "width": 100, "top": 0, "left": 0 },
  "opacity": 100, "blur": 0, "volume": 0, "speed": 100,
  "borderRadius": 0, "borderWidth": 0, "blurBackground": false,
  "colorBorder": "#010101", "colorBackground": "#000000", "colorFill": "#FFFFFE",
  "mixBlendMode": "normal", "size": "medium", "closeUp": false, "transparent": false,
  "animationAudio": { "toggle": false },
  "animationVisual": { "toggle": false, "list": [] },
  "startFrom": 0, "loop": false, "hideOn": [], "cut": []
}
```

### 8.3 subtitle (18 预设对应)
```json
{
  "content": "Introducing our latest product, a smart AI assistant.",
  "keywords": "minimalist, futuristic",
  "useGlobalTranscription": false,
  "transcription": { },
  "toggle": true,
  "height": 10, "width": 70, "top": 75, "left": 15, "rotate": 0,
  "textAlign": "center", "textAlignVertical": "end",
  "fontFamily": "notoSansSC",
  "fontSize": 30, "fontWeight": 700,
  "letterSpacing": 0, "lineHeight": 0, "strokeWidth": 0, "padding": 0,
  "colorForeground": "#FEFEFE",
  "colorBackground": "#000000ad",
  "colorStroke": "#010101ff",
  "colorHighlight": "#ffdf00ff",
  "colorHighlightBackground": "#ffdf00ff",
  "colorHighlightKeyword": "#eafc31f9",
  "colorUnderline": "#ffdf00ff",
  "borderRadius": 30,
  "textDisplay": "phrase",
  "captionAnimation": "none",
  "textTransform": "none",
  "backgroundFit": "box",
  "textEffect": { "fill": true },
  "animationVisual": { "toggle": false, "list": [] }
}
```

### 8.4 transcription (word-level timing)
```json
{
  "text": "Introducing our latest product, a smart AI assistant.",
  "words": [
    { "word": "Introducing", "offset": 0, "timeStart": 0, "timeEnd": 20 },
    { "word": "our", "offset": 0, "timeStart": 20, "timeEnd": 25 },
    { "word": "latest", "offset": 0, "timeStart": 25, "timeEnd": 32 },
    { "word": "product,", "offset": 0, "timeStart": 32, "timeEnd": 47 },
    { "word": "a", "offset": 0, "timeStart": 55, "timeEnd": 59 },
    { "word": "smart", "offset": 0, "timeStart": 59, "timeEnd": 66 },
    { "word": "AI", "offset": 0, "timeStart": 66, "timeEnd": 74 },
    { "word": "assistant.", "offset": 0, "timeStart": 74, "timeEnd": 88 }
  ]
}
```

### 8.5 visualization (data chart overlay)
```json
{
  "toggle": false,
  "height": 13, "width": 80, "top": 43, "left": 10, "rotate": 0,
  "alignItems": "center", "size": "medium",
  "colorForeground": "#e91e63ff",
  "animationVisual": { "toggle": false, "list": [] }
}
```

### 8.6 voiceover layer 特有的 media 字段
```json
{
  "mediaGeneratedId": {
    "_id": "6a619e64dc3a8dbaa67f1161",
    "type": "audio",
    "file": "generated/6a60be008678de04cf209b95/6a619e62dc3a8dbaa67f1038.mp3",
    "duration": 2.688,
    "colors": []
  },
  "voiceId": { 完整 voice schema },
  "voiceStyleId": null,
  "volume": 100,
  "speed": 100
}
```

## 9. 与 v5 schema 对比增量

| 维度 | v5 | v6 (新增/修正) |
| ---- | -- | -------------- |
| AI 图像默认模型 | Flux 2 Klein | runware-z-image-turbo (Playground/Editor 实际) |
| 场景拆解模型 | GLM-5.2 | gemini-2.5-flash-lite (sceneBreakdownModelUsed) |
| aiVideoClipPercentage | 无 | 20 (每 20% scene 插 AI video) |
| aiImageAnimationPreset | 无 | Mix:Subtle Flow |
| subtitlePresetId | 无 | builtin-legacy-basic (18 预设 ID) |
| media.relatedVoiceover | 无 | string (媒体关联的 voiceover 文本) |
| media.charactersInFrame | 无 | [] (数字人 id 列表) |
| subtitle.keywords | 无 | minimalist, futuristic |
| subtitle.colorHighlightKeyword | 无 | #eafc31f9 |
| scene.duration.{from,to,total,ahead} | partial | full |
| voice.variants | 无 | 完整数组 (跨语言版本) |
| voice.serviceType/serviceCode | 无 | neural/en-US-SaraNeural |
| 数字人 provider | 自研 (v5 推测) | D-ID service (clips-presenters.d-id.com) |
| 数字人 driver | 无 | natural/lively 2 套 emotion |
| overlay | 无 | Bokeh particles (45.42s mp4) |
| drive.slug/mode/mediaRecents | partial | full |
| tRPC JSONL 格式 | 未识别 | superjson + ref/result pair |

## 10. 决策影响

### 用户决策 5 (每节点 LLM 手动配置)
本地 v1 需要为以下节点预留 provider 配置:
- scene breakdown: 默认 Gemini 2.5 Flash Lite,本地 v1 用 DeepSeek/Mock
- AI image gen: 默认 runware-z-image-turbo,本地 v1 用 Stable Diffusion/Flux
- AI video gen: 默认 Kling 3.0 Pro (Playground 14 选 1),本地 v1 用 SVD/Mock
- AI music gen: 默认 Ace Step 1.5 Base + MiniMax Music 2.6,本地 v1 用 MusicGen/Mock
- Copilot: GLM-5.2/Flash/Gemini 3.5 Flash/Opus 4.8 4 选,本地 v1 用 DeepSeek/Qwen
- TTS: Microsoft/Amazon/Google 三家 + 自研 voice clone (本地 v1 用 Edge TTS + GPT-SoVITS)

### 用户决策 6 (本地化数字人)
- 不引 D-ID (clips-presenters.d-id.com 是付费第三方)
- 用 SadTalker/MuseTalk (本地 v1 静态头像 + 字幕替代)
- drivingVideo mp4 本地 v1 不实现,用 1 张静态头像 + 字幕

## 11. 已知缺口 (Phase 2 需补)

- [ ] render.latest response — 当前是 2 个并行调用,response 是 render job 还是空?需抓
- [ ] preview.detail response — 完整 schema 待抓
- [ ] release.list — release notes 列表
- [ ] credit.detail — credit 余额 + 16 类计费项
- [ ] style.list (Playground) — 风格 ID vs name 映射
- [ ] mediaMy.listSamples — Playground 50+ 样本完整 prompt
- [ ] character.picker (新) — 完整 69 角色 stock id + driving video URL
- [ ] pronunciation.list.list — 自定义发音字典
- [ ] font.list 完整 — 字体 dropdown 列表

## 12. Phase 2 工程落地映射

新增 4 张表 (来自 v6 batch):

```sql
-- 数字人 provider 配置 (替代 D-ID)
CREATE TABLE avatar_drivers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  provider TEXT NOT NULL,
  driver_url TEXT,
  thumbnail_url TEXT,
  gender TEXT,
  is_default INTEGER DEFAULT 0,
  created_at TEXT
);

-- Overlay 装饰效果
CREATE TABLE overlays (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  file_path TEXT NOT NULL,
  preview_image_path TEXT,
  duration REAL,
  is_enabled INTEGER DEFAULT 1
);

-- workflow features 配置 (per project)
CREATE TABLE project_features (
  project_id TEXT PRIMARY KEY,
  ai_image_model TEXT,
  ai_video_model TEXT,
  ai_video_clip_percentage INTEGER DEFAULT 20,
  scene_breakdown_model TEXT,
  scene_breakdown_engine TEXT,
  ai_image_animation_preset TEXT,
  subtitle_preset_id TEXT,
  art_style TEXT,
  enable_avatar INTEGER DEFAULT 0,
  enable_b_roll INTEGER DEFAULT 1,
  enable_sfx INTEGER DEFAULT 1,
  highlight_subtitles INTEGER DEFAULT 1,
  updated_at TEXT
);

-- TTS variant (跨语言版本)
CREATE TABLE voice_variants (
  id TEXT PRIMARY KEY,
  voice_id TEXT NOT NULL,
  language_code TEXT NOT NULL,
  dialect_code TEXT NOT NULL,
  service_code TEXT NOT NULL,
  sample_file_path TEXT,
  duration REAL,
  is_enabled INTEGER DEFAULT 1
);

-- Layer transcription (word-level timing)
CREATE TABLE layer_transcriptions (
  layer_id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  words_json TEXT NOT NULL,
  updated_at TEXT
);
```

## 13. 抓取方法笔记

### Page 内 fetch + localStorage 中转
- evaluate_script 一次返回最大 ~16KB JSON (再大被截断标 N chars truncated)
- 解决: 先 fetch 完整 -> 存 localStorage -> 多次 evaluate_script substring 取块
- console.log 分块输出 4000 字符/块也完整,但 list_console_messages 也可能截断
- 最佳: 把 fetch + store + return meta 合并成一次 evaluate_script

### Chrome MCP workspace 限制
- 只允许写入 2 个 root: CWD + visualizations UUID
- 中文+空格 CWD canonical 失败 (即使路径正确也 access denied)
- 解决: 先用 shell_command 确认路径存在,shell+Node 写 D:\workspace
- get_network_request responseFilePath 也受限 -> 改用 page fetch + localStorage 兜底

### tRPC JSONL 格式
- response header trpc-accept: application/jsonl
- 每行 ref/result pair,引用靠数字 ID (紧凑 ~30% 优于 JSON)
- 解析需 superjson 解码器 (v5 schema 没识别)
