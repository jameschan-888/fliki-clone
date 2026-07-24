# Fliki 结构分析 v4 (2026-07-23)

> 数据源：app.fliki.ai 已登录会话 (账号 Leo Chan / chanleo1210@gmail.com / free plan)
> 抓取方式：chrome_devtools MCP + React Fiber walk + localStorage dump + Network 监听
> 排除：截图（按用户规则不输出截图）

## 摘要

Fliki 是一个基于 **Remotion 视频引擎 + tRPC 后端 + Next.js App Router 前端** 的 SaaS 视频生成器。
本地克隆推荐使用 **FFmpeg 主渲染 + React/Next.js 前端 + FastAPI 后端**，见 architecture.md。

关键事实：

| 维度 | Fliki 真实实现 | 本地克隆方案 |
| ---- | -------------- | ------------ |
| 视频引擎 | Remotion (React composition 1920x1080@30fps) | FFmpeg compose (Python) — 用户决策 |
| 前端框架 | Next.js App Router + Radix UI + Turbopack | Vite + React 19 + Radix UI |
| 后端协议 | tRPC over HTTP GET (Express) | FastAPI + REST (proj_055 已成熟) |
| 状态管理 | Zustand store + localStorage cache | Zustand store + localStorage cache |
| 数据模型 | Mongoose (4 级 ID: playback/scene/layer/voice) | SQLite + 同构 ID |
| 媒体存储 | cdn.fliki.ai (S3 + CloudFront) | 本地 D:/workspace/.../data/{media,stock,tts,avatar,music} |
| TTS | 80+ 语言 (第三方 API 集成) | Edge TTS (默认免费) + Azure/Google (付费) |
| 股票素材 | Storyblocks (付费) | Pexels/Pixabay (免费默认) + Getty/Shutterstock (付费预留) |
| 角色 | 67+ 公共角色 + 用户克隆 + AI 生成 | SadTalker/MuseTalk (本地) + 13+ 公共角色种子 |
| 声音克隆 | paid feature | GPT-SoVITS (本地) |
| AI 图像 | Flux 2 Klein, runware-z-image-turbo | Stable Diffusion / Flux 本地 |
| AI 视频 | Runware | Stable Video Diffusion 本地 / Replicate (付费预留) |
| 工作流 | 6 个: Script/Blog/PPT/AutoEdit/Record/Empty | 同上，优先 Script + AutoEdit |

## 一、页面清单 (7 个主路由)

| 路由 | 标题 | 核心功能 |
| ---- | ---- | -------- |
| `/` (Home) | "Lets get started, Leo" | 3-tab (Video/Voiceover/Design) + 6 工作流卡片 + Recent files |
| `/editor/<playbackId>` | Remotion 编辑器 | 11 工具面板 + 中心预览 + 底部 timeline + 右侧脚本面板 |
| `/files` | 文件管理 | 网格/列表视图、All/Video/Audio/Design 过滤、search、trash、bulk create、new folder/new file |
| `/characters` | 角色库 | 67+ 公共角色 + New character + Clone your voice + Avatars (paid) |
| `/series` | 视频系列 | (待抓) |
| `/tools` | 工具集 | (待抓) |
| `/playground` | AI 生成器 | Image/Video/Music + Create/Edit/Upscale/Remove bg + 模型选择 (Flux 2 Klein 0.05 credits) + Style (Cinematic) + Reference images |
| `/automation` | 自动化 | (待抓) |
| `/brand-kits` | 品牌包 | (链接自 Settings) |

## 二、Home 页

Home (3-tab):
- Video (默认): textarea + 4 个 helper (Choose an avatar / voice / Attach files / Come up with an idea) + Create 按钮 + 6 个工作流卡片 (Script/Blog/PPT/AutoEdit/Record/Empty) + Recent files
- Voiceover (TTS-only 入口)
- Design (静态设计生成入口)

## 三、Editor 页（核心）

### 顶部
- Home link / Project name (inline edit) / Upgrade / Undo / Redo (默认 disabled) / Share preview / File actions / Download

### 左侧工具栏 (11 项，More tools 展开后)
1. **Copilot** - AI 对话助手
2. **Media** - 素材面板 (Stock/Library/Generate/Favorites/Recent x Video/Image/GIF)
3. **Character** - 角色面板 (Characters/Avatars x Public/Mine/All/Male/Female)
4. **Subtitles** - 字幕样式 (预设编辑器)
5. **Audio** - 音频面板 (Stock/Library/Generate/Favorites x Music/SFX/YouTube Music)
6. **Elements** - 装饰元素 (图标/形状/贴纸) (More)
7. **Record** - 屏幕录制 (More)
8. **Templates** - 场景模板 (More)
9. **Layers** - 图层管理 (More)
10. **Settings** - 项目设置 (ASPECT_RATIO 9:16/1:1/16:9 + Scene gap + BRAND/COLOR Brand kit/Background/Colors used/Fonts)

### 中心舞台
- **Remotion Player** (1920x1080@30fps)
- Timeline controls: 播放/暂停 + 时间 (00:00 / 00:12) + Zoom out/in + Reset + 100% 状态
- View tabs: Basic view / Timeline view

### 时间线
- 每 scene 一行: 缩略图 + Open layers + Hide scene + 时长标签 (4.0s) + Scene transition & sound
- Background music (项目级背景音乐)
- Select common scene (多选操作)
- Add scene 按钮

### 右侧 Script Panel
- 4 个 scene 卡片:
  - Scene 1: "Introducing our latest product, a smart AI assistant." [4s] voice=Sara
  - Scene 2: "It helps you write emails faster." [2.75s]
  - Scene 3: "It schedules your meetings automatically." [2.75s]
  - Scene 4: "Try it today." [1.75s]
- 每张卡片: 编号 + Download voiceover / Open layers / Scene options / Drag handle / Voice picker / Regenerate audio / 多行 textbox (富文本，关键词高亮) / 时长
- Script 可 unpin / hide thumbnails / close
- Add scene 按钮

### 弹窗 (按需出现)
- Share preview - 分享链接生成
- Layers dialog - 选中 scene 的 layer 编辑
- Slide panel - 通用抽屉
- 全屏 Dialog (h-[82vh] w-[calc(100vw-3rem)])

## 四、Media 面板
4 个 Tab:
1. **Stock** (默认) - 第三方库存; Search 输入 + 类型 radio (Video/Image/GIF) + 关键词自动出推荐 + Select 按钮
2. **Library** - 用户上传素材
3. **Generate** - AI 生成 (走 Playground 引擎)
4. **Favorites** - 收藏
5. **Recent** - 最近

## 五、Character 面板
2 个 Tab:
1. **Characters** (默认) - 一致性角色
   - 描述: "A consistent face and voice you can reuse across every scene."
   - 过滤器: Public / Mine / All / Male / Female
   - Create character (自定义)
   - 67+ 公共角色网格 (Chloe / Claire / Noah / Priya / Emma / James / Emily / Leila / Owen / Maya / Arjun / Daniel / Camila / Hannah / Ethan / Alejandro / Mina / Anjali / Sophie / Hiroshi / Marcus / Nicole / Vincent / Rebecca / Nadia / Manuel / Jake / Sunita / Andre / Sofia / Yasmin / Javier / Simone / Ryan / Antonio / Angela / Divya / Farah / Terrence / Denise / Sung / Ben / Susan / Gary / Meera / Ramon / Shirin / Eleanor / Isaiah / Marco / Haruki / Wei / Khalid / Grace / Paolo / Carlos / Fatima / Ava / Samuel / Elliot / Ricardo / Yvonne / Gloria / Margaret / Kenji / Robert / Laura / Michael / Tyler)
   - 每个角色有 N looks (形象变体数)
2. **Avatars** - 单帧形象 (Paid plans)

## 六、Audio 面板
4 个 Tab (Stock/Library/Generate/Favorites)
- Search: "groovy, beat, happy"
- 3 类: Music / Sound effects / YouTube Music Library
- 每条: 标题 + 时长 + 类型 (Scifi/Horror/Alarms/Cartoon)
- 样例: Futuristic Spell (00:02, Scifi), Futuristic Avalanche (00:27, Scifi), Futuristic Cosmic Lava (00:12, Scifi), Futuristic Strangers Ambiances (00:43, Horror), Futuristic Capsule Launching (00:05, Scifi), Futuristic Magnetic Gate, Futuristic Cartoon Computer (00:13), Digital Futuristic Notification (00:01, Alarms+Cartoon), Futuristic Lab Experiment (01:27, Scifi), Scientific Futuristic Ambience (00:33, Scifi)

## 七、Settings 面板
- ASPECT_RATIO: 9:16 / 1:1 / 16:9 (radio)
- Scene gap: 0s (spinbutton)
- BRAND & COLOR:
  - Brand kit (link /brand-kits)
  - Background (color picker)
  - Colors used (4 个 color slot)
  - Fonts (combobox, eg: Noto Sans SC)

## 八、Playground 页 (AI 生成器)
类型 radio: Image / Video / Music
模式 tab: Create / Edit / Upscale / Remove background
控件:
- Prompt textarea
- Enhance (AI 改写 prompt)
- MODEL dropdown: "Flux 2 Klein" - "Sub-second open-source generation with multi-reference editing support" - "0.05 credits"
- Aspect Ratio: 16:9
- Style: Cinematic
- Reference image (最多 4 张)
- Generate (显示 credit 消耗)
- Try these samples (50+ 历史样本 + Recreate 按钮)

## 九、Characters 主页
- 标题: "Create once, use everywhere"
- 描述: "Pick a ready-made public character or avatar, clone a real person from a photo or video, or generate a brand-new one from a description. Reuse them across every video."
- 2 CTA: New character / Clone your voice
- Tabs: Characters / Avatars (Paid plans)
- 过滤器: Public / Mine
- 67+ 角色网格 + Use <name> 按钮

## 十、Files 主页
- 工具栏: Search / Trash / Bulk create / New folder / New file (link /files/create)
- 类型过滤: All (1) / Video (1) / Audio (0) / Design (0)
- 视图切换: Grid / List
- 多选 checkbox
- 文件卡片: 类型标签 + 标题 + 时间 + Landscape + File actions menu

## 十一、Auth + 配额

### JWT Payload 解码
header: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9`
payload: `eyJpZCI6IjZhNjBiZTAwODY3OGRlMDRjZjIwOWI5NSIsImlzTW9iaWxlIjpmYWxzZSwiaWF0IjoxNzg0NzgxMTU2fQ`
解码: `{"id":"6a60be008678de04cf209b95","isMobile":false,"iat":1784781156}`

### Free plan limits
| 资源 | 限制 |
| ---- | ---- |
| units (月度) | 180 |
| voices | 300 |
| ultraRealistic | 0 (free 无真人级) |
| exportLength | 5 分钟 |
| sceneSize | 50 scenes |

### Credit 计费项 (16 类)
generateAvatar / generateAudio / generateImage / generateVideo / generateScript / generateVoiceover / generateVoiceCustom / removeBackground / render / publish / translate / workflow / summarizeMedia / stockDownload / copilot / creditAdditional / creditDeduct

### 用量
本例 free plan: used=33 / total=180 / remaining=147 / percentage=18
周期: monthly; startDate=2026-07-22; resetDate=2026-08-21

## 十二、5 个 Recipe (工作流模板)
| 名称 | 计划 | 描述 | cost |
| ---- | ---- | ---- | ---- |
| Stop-Motion Story Video Generator | premium | Stop-motion + needle-felted wool puppets | 400-620 credits |
| Raw Clips to Final Video | free | Upload clips → transcribe → cut silence → B-roll + subtitles | - |
| Product Image to Ad Creative | free | 三张产品广告图 | - |
| Translate Audio/Video | basic | 翻译+配音+字幕 | - |
| Product Image to Marketing Video | standard | 产品图 → 营销视频 | 67.5 credits |

## 十三、UI 库 + 视频引擎
- **Radix UI**: Dialog / Tooltip / Popover / DropdownMenu / ScrollArea / AlertDialog / Menu / Popper
- **Remotion**: LoadableComponent + withInteractivitySchema(Component) HOC, 1920x1080@30fps
- **class-variance-authority** + **Tailwind** (className 推断: `flex h-[82vh] w-[calc(100vw-3rem)] max-w-[79.2rem]` 等)
- **dnd-kit** 拖拽场景重排

## 十四、与本地架构的对照

见 architecture.md。本地克隆核心决策 (已锁定):
1. 渲染引擎: FFmpeg (用户决策，更便宜/更低硬件)
2. 协议: FastAPI + REST (proj_055 已成熟，零成本复用)
3. 端口: 8001 (避开 proj_055 的 8000)
4. 数据库: 独立 SQLite app.db (不共享 proj_055)
5. 文件输出: D:/workspace/Fliki视频制作还原/backend/data/{media,stock,tts,avatar,music,output}

## 十五、待补抓 (下次)
- [ ] Click Add scene 看添加菜单
- [ ] Click Share preview 看分享面板
- [ ] Click 头像角色详情 (voice clone 工作流)
- [ ] Series / Tools / Automation 页
- [ ] Subtitles panel 完整控件
- [ ] 一个 stock-character-picker 完整 dump (211KB)
- [ ] styles 视觉风格 prompt (74KB)
- [ ] mediaMyListSamples.image 完整样本 (70KB)

## 附：本次新增 vs v3

| v4 新增 | 来源 |
| ------- | ---- |
| JWT payload 解码 (userId + iat) | localStorage userAuth.token |
| Free plan 完整 limits 表 | subscriptionActive.limits |
| 16 类 credit 计费项 | usageSummary.records |
| 5 个 Recipe 完整列表 | recipeList |
| 67 个角色完整名单 (Chloe/Tyler) | stock-character-picker |
| Drive list home entry schema | driveList |
| playbackFocus state schema | playbackFocus |
| fileCreateSettings 完整字段 (含 features.aiModel=runware-z-image-turbo) | fileCreateSettings |
| Remotion LoadableComponent + withInteractivitySchema HOC 组件证据 | React Fiber walk |
| Playground Flux 2 Klein 0.05 credits 模型 | snapshot |
| Settings 完整结构 (Brand kit/Colors used 4 slot/Fonts) | snapshot |
| 11 个 editor tools 完整列表 (含 Elements/Record/Templates/Layers) | snapshot |
| Audio SFX 完整列表 (Futuristic Spell/Avalanche/Cosmic Lava...) | snapshot |
| Character 67 角色 + Public/Mine/Male/Female 过滤 | snapshot |


---

## 十六、v5 增量补充 (2026-07-23 第二轮补抓)

### 16.1 9 个补抓的新增内容

| 新增 | 来源 |
| ---- | ---- |
| Subtitles 面板 18 预设 | 点击 Subtitles 工具按钮 |
| Layers 工具面板 + Add layer 8 类菜单 | 点击 Layers 工具按钮 |
| Copilot 工具 + 4 LLM 模型 | 点击 Copilot 工具按钮 |
| Templates 工具面板 10+ 模板分类 | 点击 Templates 工具按钮 |
| Elements 工具面板 4 大类 | 点击 Elements 工具按钮 |
| Record 工具面板 Screen/Webcam/Mic | 点击 Record 工具按钮 |
| Audio Generate tab Ace Step 1.5 Base | Audio 面板 -> Generate |
| Media Generate tab Z Image Turbo + 9 样例 | Media 面板 -> Generate |
| Series / Tools / Automation 主页 | navigate 各路由 |
| Voices 页 Clone 2min + AI from prompt | characters -> Clone your voice |
| Character picker 完整 69 个 (含 looksLabels) | localStorage stock-character-picker |
| Styles 视觉风格库 29 个 (含 prefix/suffix) | localStorage styles |

### 16.2 Subtitles 面板

3 类预设 x 6 个 + 完整样式控件:

- Social 6: Bold Outline / Word / Pop Lime / Emphasis Pink / Neon Glow / Mint Spotlight
- Business 6: Minimal Classic / Basic / Minimal / Simple Glow / Boxed Blue / Navy Serif
- Retro 6: Editorial Serif / Script Gold / Handwritten / Fog / Fill / Retro 3D
- 每类有 View all 按钮

控件:
- 颜色选择器 4 个: Stroke / Background / Highlight / Keyword
- 数值输入: Stroke 0-100 / Padding 0-100 / Radius 0-100 (default 30) / Line -100 to 100
- 文本单位 radio: Word / Phrase (default) / Sequence / Full
- 对齐 radio: left / center (default) / right
- 垂直对齐 radio: top / middle / bottom
- Animation dropdown
- Apply to all scenes

底部 toolbar:
- SUBTITLES switch (开/关)
- 字体下拉: Noto Sans SC (Chinese)
- 字号: 30 (dropdown)
- Text color + Typography + Transform dropdown
- Apply to all scenes

### 16.3 Layers 工具面板 + Add layer 菜单

**Layers 工具** (left nav 第 9 个) 自动弹右侧 side panel:
- 标题 Layers + Close
- Add layer 按钮 (带 menu)
- Scene 切换器 (eg Scene 1)
- Top = front 提示
- 每 layer 一行:
  - 序号 (1, 2, 3...)
  - 类型标签 (Image/video, Voiceover, Subtitle...)
  - 时间范围 (00:00 - 00:04)
  - 操作按钮: Replace media / Copy layer / Hide layer / Drag to reorder / Play preview / Hide script
- 底部 Add 按钮 (带 menu)

**Add layer 菜单** (8 类):
- Image / video (插入图片或视频素材)
- Text (文本图层)
- Shape (几何形状)
- Graphic (装饰图形)
- Effect (特效)
- Avatar (数字人)
- Audio (音频)
- Watermark (水印)

### 16.4 Copilot 工具面板 + 4 LLM 模型

**Copilot 工具** (left nav 第 1 个) 弹 AI 对话面板:
- 描述: Ask Copilot to build or edit your video. It can add scenes, change media, rewrite the script, and more.
- TRY ASKING 3 个 quick prompt:
  - Reduce the background volume by 5%
  - Add a title text in scene 2 saying Hello world
  - Change the background music to upbeat music
- 输入框 (form, multiline)
- Attach an image 按钮
- **模型下拉 (combobox) 4 个选项**:
  - **GLM-5.2** (default, Fast, capable, agentic - 50% off credits here. All plans.)
  - **Flash** (Cheapest. Kept on a short leash - compact prompts + replies.)
  - **Gemini 3.5 Flash** (Fast + reliable workhorse.)
  - **🔒 Opus 4.8** (Newest Opus - maximum creative quality. Slowest, costs most.)
- Send 按钮

**关键发现**: Fliki 后端 LLM 注册表包含 GLM-5.2 (可能是智谱 GLM 模型改名) + Claude/Gemini。Flash + Opus 4.8 是 Claude 系列。

**本地启示**: 后端 LLM 注册表同样设计:
- 默认: DeepSeek (国产便宜)
- 高级: Claude/GPT-4 (慢但质量高)
- 廉价: Qwen/Hunyuan/GLM (国内)

### 16.5 Templates 工具面板

**Templates 工具** (left nav 第 8 个) 弹模板网格面板:
- 10+ 模板分类前缀:
  - Social Media Story (Top 3 hidden beaches, Boost your productivity)
  - Travel & Tourism (Thailand travel guide)
  - Motivational Quote (Weight loss journey, Top 5 famous quotes)
  - Explainer Video (Gym workout, Climate change, Budget strategy)
  - Product Demo (Hanes Hoodie, Apple AirPods, MyHealth Mobile App)
  - Breaking News (Volcanic eruption, Heatwave)
  - Educational Lesson (Introduction to Neurons, Climate change)
  - Real Estate Tour (Private villa Airbnb, Maple Leaf Realty)
  - How-To Tutorial (Make cup of coffee)
  - Quiz (Animal trivia challenge, Space trivia)
- 预览图: cdn.fliki.ai/media.v2/generated/6720f7a39c5d83f364ab39c9/<id>_thumbPreview.jpg

### 16.6 Elements 工具面板 (4 大类)

**Elements 工具** (left nav 第 6 个) 装饰元素面板:
- **Text** (8): Title / Highlight / Reveal / Pop / Impact / Spin / Caption / NEON
- **Lower thirds** (4): Clean / Spotlight / Headline / Accent Bar (人名条模板)
- **Background shapes** (14): Rectangle / Circle / Shape 3-14
- **Emoji** (30+): GRINNING FACE / FACE WITH TEARS OF JOY / ... (Unicode emoji)

### 16.7 Record 工具面板

**Record 工具** (left nav 第 7 个) 屏幕/摄像头录制面板:
- 实时预览窗口 (dark gradient background)
- Choose what to capture / Your live preview shows up here.
- What to capture 3 选项 (radio cards):
  - **Screen**: A window, tab, or your full screen
  - **Webcam**: Your camera as a video
  - **Microphone**: Your narration
- Start recording 按钮 + Up to 5 min - adds to the shared scene and saves to your library.

### 16.8 Audio Generate tab (Music 模型)

Audio 面板 -> Generate tab:
- 3 类 radio: Music (selected) / Sound effects / YouTube Music Library
- Library 子过滤: All / Uploaded / Generated
- Upload audio 按钮 + Record media 按钮 (跳转 Record 工具)
- Your generated music will appear here
- Prompt from scene 按钮
- **Model: Ace Step 1.5 Base** (免费版不可用, Not available on your current plan)
- Upgrade 提示

**关键发现**: Fliki 音乐生成用 Ace Step 1.5 Base (开源音乐生成模型, ACE-Step 项目)。本地 v1 用 MusicGen 或 Suno API。

### 16.9 Media Generate tab (Image 模型)

Media 面板 -> Generate tab:
- 类型 radio: Video (selected) / Image / GIF
- Stock 视图: 9 个 stock video 样例:
  - A large container ship skillfully navigating calm waters 00:10 16:9
  - Businesswoman Walking in the Park on a Sunny Day 00:14 16:9
  - Snow Melting On Snowdrop Flowers... 00:18 16:9
  - Vertical video: African couple sitting at home... 00:20 9:16
  - animation of abstract geometric composition of mesh pattern... 00:20 16:9
  - Vertical video: Adjusting earbud... 00:19 9:16
  - Blue energy magic sphere round high-tech digital iridescent morphing ball... 00:10 16:9
  - Scenic Water Falls At Victoria Falls In Matabeleland North Zimbabwe... 00:24 16:9
- 每个素材: More actions + Add as overlay 按钮
- Your generated image will appear here
- Prompt from scene 按钮
- **Model: Z Image Turbo** (Runware 后端, model=runware-z-image-turbo)

### 16.10 Series / Tools / Automation 主页

**Series 主页** (/series):
- 标题 Your Content Calendar, On Autopilot
- 描述 Schedule and auto-generate video episodes: daily, weekly, or on your own cadence.
- New series + Watch tutorial CTA
- 二级标题 Put your channel on autopilot + 描述 Describe a topic once. Fliki writes the script, makes every episode, and posts them to YouTube and TikTok.
- **Paid feature** (本地 v1 不实现)

**Tools 主页** (/tools): 5 个 Recipe 卡片 (与 recipeList 对应):
1. Stop-Motion Story Video Generator (Upgrade required, 400-620 credits)
2. Raw Clips to Final Video (free, 自动转写/静音剪/B-roll+字幕)
3. Product Image to Ad Creative (free)
4. Translate Audio/Video (Upgrade required)
5. Product Image to Marketing Video (Upgrade required, 67.5 credits)

**Automation 主页** (/automation):
- 标题 Content Creation at Scale
- 描述 Connect Zapier, Make, n8n, or the REST API...
- Create key + Zapier/Make/API doc 4 个 CTA
- 3 步: Create API Key / Connect Platform / Auto-Generate
- 4 个能力: Zapier / Make / REST TTS API (Enterprise) / No-Code
- **Enterprise feature**

### 16.11 Voices 页 (/voices)

- 标题 Your voice, your way
- 描述 Clone your own voice from a 2-minute recording, or design a brand-new AI narrator from a prompt.
- 3 类: Cloned (Paid plans) / AI voices (Paid plans) / Empty state No voices yet
- New voice + Create your first voice CTA
- **Paid feature** (本地 v1 用 GPT-SoVITS)

### 16.12 Character picker 完整 69 个

- Total: 69 (FEMALE 34 + MALE 35)
- isEnabled: 68 true / 1 false (Sung, isEnabled=false)
- 全部 isStock=true (公共)
- 每个有 4-10 个 imageVersions (looks)

**Looks 命名约定**:
- 4 look 角色 (40 个): Front / Close-up / Three-quarter / Seated
- 6 look 角色 (12 个): Front / Close-up / Three-quarter / Seated / Studio / Alt outfit
- 10 look 角色 (11 个): Front / Close-up / Three-quarter / Seated + Outfit A (front/angle/seated) + Outfit B (front/angle/seated)

**素材路径**:
- Thumbnail: cdn.fliki.ai/<thumbnail path> (jpg)
- DrivingVideo: cdn.fliki.ai/video/character-stock/<dir>/<id>.mp4 (数字人驱动视频)
- PreviewVideo: cdn.fliki.ai/video/character-stock/<dir>/<id>_preview.mp4 (静态预览)

**本地 v1 角色种子建议** (13 个核心):
- Chloe / Emma / Maya / Camila / Emily / Priya / Ava / Leila (8 女)
- Noah / James / Andre / Ben / Marco (5 男)
- 每人 1 个静态头像 (本地 Phase 1) -> 后续补 driving video

完整 69 个 CSV 见 `dump/character-picker.csv`。

### 16.13 Styles 视觉风格库 29 个

29 个 visual style 模板,每个含 prefix + suffix + characterPrompt + composition:
- 3D model: Pixar-style 3D animation, expressive design, warm cinematic lighting + polished CGI, vibrant colors, theatrical quality
- 70s Documentary: Cold War espionage cinematic, heavy 16mm film grain + handheld camera instability
- Anime: 1990s OVA anime aesthetic + grainy film texture
- Biblical: dramatic biblical painting + renaissance religious art
- Brush ink: brush ink illustration + ink stroke variation
- Chalkboard: chalk blackboard drawing + chalk dust particle
- Charcoal: charcoal illustration + charcoal dust particle
- Cinematic: cinematic film still + shallow depth of field, vignette, bokeh, cinemascope, moody
- Clay: stop-motion claymation + visible fingerprints
- Comic book: Western comic-book illustration + halftone shading
- Crayon: wax crayon illustration + saturated primary palette
- Fantasy art: ethereal fantasy concept art + cover art style
- Film noir: film noir + monochrome, high contrast, 1940s style
- Golden age: golden age sci-fi illustration + 1950s pulp art
- Golden hour: golden hour painterly realism + warm amber light
- Illustration: Digital Illustration
- Layered papercut: stacked papercut art + 3D layered dimensional
- Lego: Lego brick animation + primary color brick
- Line art: clean line art illustration + crisp linework
- Neon noir: neon noir ultrarealistic + cyan and magenta neon
- Paper cutout: paper cutout animation + South Park adjacent
- Pencil sketch: graphite pencil sketch + hatching and shading
- Realistic: A cinematic photograph + natural lighting
- Renaissance: Renaissance oil painting chiaroscuro + Rembrandt lighting
- Stick figure: hand-drawn black marker doodle + minimalist
- Technical illustration: precise technical illustration + blueprint aesthetic
- Tiny world: miniature diorama + tilt-shift photography
- Watercolor: watercolor painting + vibrant painterly
- Whimsical: Studio Ghibli-style + soft painterly lighting

**本地 v1 建议**:
- 选 5-10 个 style 种子 (Cinematic / Realistic / Anime / Watercolor / 3D model / Comic book)
- 每个存为 prefix + suffix (用于拼接 AI prompt)
- 后续可让用户上传自定义 style (存 characterPrompt + composition)

完整 29 个 CSV 见 `dump/styles.csv`。

### 16.14 总结 (v4 -> v5 关键变化)

| 维度 | v4 | v5 |
| ---- | -- | -- |
| Editor 工具面板 | 11 个抓到 | 11 个全部展开 (Layers/Copilot/Templates/Elements/Record/Settings) |
| Models | Z Image Turbo (Runware) | + Copilot 4 LLM + Ace Step 1.5 Base music |
| 角色库 | 67 名字 | 69 完整 + looks 命名约定 + CDN 路径模板 |
| 视觉风格 | 仅提到样式 | 29 个 style + prefix/suffix/characterPrompt/composition |
| 路由覆盖 | 7/11 | 11/11 |
| 文件输出 | 5 dump | + character-picker.csv + styles.csv |

下一步进入 Phase 1 工程脚手架,schema 已 100% 覆盖。

## 十七、v6 增量补充 (2026-07-23 第三轮补抓)

### 17.1 Playground AI 模型完整列表 (v5 漏的 14 个视频模型)

Playground 切换到 Video tab，MODEL dropdown 完整列出 14 个 paid 视频模型 (free plan 全部 disabled 标 Upgrade):

| # | 模型 | cps (credits/sec) | 描述 |
|---|------|-------------------|------|
| 1 | Seedance Pro Fast | 0.10 | Cheapest tier, ideal for drafts, prompt testing, and high-volume social b-roll |
| 2 | P-Video | 0.30 | Affordable everyday model for routine social and marketing clips |
| 3 | P-Video Replace | 0.50 | Swap a subject in your video with a reference character, keeping the motion |
| 4 | PixVerse v5 Fast | 0.60 | Best for anime, sci-fi, and template-driven viral effects with smooth motion |
| 5 | LTX-2 Fast | 0.80 | Open-source model up to 20 seconds, fastest for rapid iteration |
| 6 | LTX-2.3 | 1.5 | Production polish with native synchronized audio for final hero shots |
| 7 | Kling 2.5 Turbo | 1.5 | Cinematic look and weighted physics, great for fast iteration on B-roll |
| 8 | Kling 2.6 Pro-Motion Transfer | 2.0 | Transfer dance, action, or gestures from a reference video onto your character |
| 9 | Kling 3.0 Standard | 2.5 | Multi-shot clips with native audio, supports English and Chinese dialogue |
| 10 | HappyHorse 1.0 | 2.5 | Top blind-test rankings with native audio and 7-language lip-sync |
| 11 | Kling 3.0 Pro | 3.0 | Kling flagship with 15-second clips, full camera control, and native audio |
| 12 | Google Veo 3.1 Fast | 3.0 | Best-in-class dialogue and synced audio in 8s clips, strict on real likenesses |
| 13 | Seedance 2.0 | 3.5 | Multi-ref input (image/video/audio) with strong physics, blocks real-person uploads |
| 14 | Seedance 2.0 Mini | 1.5 | Faster, cheaper Seedance 2.0 for quick 720p clips |

控件: Aspect Ratio 16:9 + Duration 8s + Resolution 720p + Reference image (1)。模式: Create / Motion control / Remove background (不是 Image 的 Create/Edit/Upscale/Remove)。

### 17.2 Playground AI Music 模型 (v5 只抓 1 个，现抓全 2 个)

Playground Music tab 完整 2 个模型:

| # | 模型 | cps/cr | 描述 |
|---|------|--------|------|
| 1 | Ace Step 1.5 Base | 0.0030 cps | Ultra-cheap with tag-based control up to 5 min, instrumental sounds best (v5 已抓) |
| 2 | MiniMax Music 2.6 | 1.5 cr/gen | Full vocal songs & instrumentals from a prompt; the model sets the length (新发现) |

控件: Prompt + Enhance + Duration slider 30-300s。0.03 credits / 10s。

### 17.3 Editor Download Dialog (v3 遗留补抓)

点击 Editor 顶部 Download 按钮:

- Resolution: combobox (free plan 只 720p)
- Format: combobox (free plan 只 mp4)
- 提示: "Upgrade to unlock all resolutions & formats."
- Start export 按钮

Free plan 锁死 720p mp4。完整选项列表 (upgrade 后): 1080p/4K + mov/webm。

### 17.4 Editor Share Preview Dialog (v3 遗留补抓)

点击 Editor 顶部 Share preview 按钮:

- 标题: Share preview
- 描述: "Share a preview of the video by using the generated link and passcode."
- Create link 按钮

### 17.5 Editor Add Scene 流程 (v3 遗留补抓)

点击 Add scene 按钮 (底部 timeline 或 script panel):

- 直接添加空 scene，**不弹菜单**
- 新 scene 默认 1.0s 时长 (其他 4 个 scene 是 4s/2.75s/2.75s/1.75s)
- 默认 voice: Sara
- 默认 media: "Blank media — add a visual"
- 时长可在底部 toolbar 调

### 17.6 Editor Scene Options 菜单 (v3 遗留补抓)

每个 scene 右侧的 "Scene options" 按钮弹出 4 项菜单:

1. Rename - 重命名 scene
2. Custom duration - 自定义时长
3. Hide scene - 隐藏 scene
4. Copy scene - 复制 scene

### 17.7 完整 tRPC Batch Schema (v5 漏的 7 个 endpoint)

Editor 加载时一次性发起 7 个 tRPC endpoint batch 调用 (trpc-accept: application/jsonl):

- subscriptions.active
- userPlatform.list
- apiAccess.detail - 返回 avatarMale/avatarFemale/overlay
- pronunciation.list - 返回 voice 完整 schema
- playback.detail - **核心：playback 全量数据**
- workflow.detailByPlayback - 返回 features 配置
- drive.detail - 返回 drive + breadcrumbs
- font.list

完整 46KB JSONL 抓取，覆盖之前 16 endpoint 列表的盲区。

**v6 关键新发现**:
- AI 图像默认模型从 v5 推测的 Flux 2 Klein 改为 **runware-z-image-turbo**
- 场景拆解实际用 **Gemini 2.5 Flash Lite** (不是 v5 写的 GLM-5.2)
- aiVideoClipPercentage=20 (每 20% scene 插 AI video)
- aiImageAnimationPreset="Mix:Subtle Flow"
- subtitlePresetId="builtin-legacy-basic"
- scene.duration.{from,to,total,ahead} 全字段
- voice.serviceType="neural"/serviceCode="en-US-SaraNeural"
- voice.variants 数组 (跨语言版本)
- 数字人走 **D-ID service** (clips-presenters.d-id.com)，付费第三方
- 默认数字人: avatarMale=Alex (D-ID) / avatarFemale=Anita (D-ID)
- 默认 overlay: Bokeh particles (45.42s mp4)
- media.relatedVoiceover/charactersInFrame 新字段
- subtitle.keywords/colorHighlightKeyword 新字段

完整 schema 见 dump/trpc-batch-summary.md (19KB)。

### 17.8 v6 工程落地映射

新增 4 张表 (对应 v6 新发现的 schema 字段):

- avatar_drivers - 数字人 driver 配置 (替代 D-ID 走本地 SadTalker/MuseTalk)
- overlays - overlay 装饰效果
- project_features - per-project workflow features 配置 (aiModel/sceneBreakdownModel/aiVideoClipPercentage 等)
- voice_variants - 跨语言 voice 版本
- layer_transcriptions - word-level timing (subtitles 同步用)

### 17.9 Phase 1/2 调整

Phase 1 完成后立即进入 Phase 2 时需要补:
- providers/tts/ 抽象层需要 service/serviceType/serviceCode 三件套 (微软/Azure/Amazon/Google)
- providers/image/ 抽象层需要 model 字段支持 runware/flux/sd 切换
- providers/video/ 抽象层需要 cps 字段 + 14 模型支持 (本地 v1 只实现 mock，其他预留 API 配置)
- providers/music/ 抽象层需要 cr/gen 字段 + 2 模型支持
- workflows/script_to_video.py 需要 scene_breakdown_model + ai_video_clip_percentage 配置
- workflows/auto_edit_video.py 需要 voiceover layer schema 完整字段


## 18. Phase 2 增量 — Style 库 + 100 Sample Prompt

### 18.1 Style 库结构 (29 个)

字段: _id / name / key / prefix / suffix / characterPrompt / composition / thumbnail / 可选 imagePromptDirection + videoPromptDirection

- 3D model (3dModel)
- 70s Documentary (70sDocumentary)
- Anime (anime)
- Biblical (biblical)
- Brush ink (brushInk)
- Chalkboard (chalkboard)
- Charcoal (charcoal)
- Cinematic (cinematic) ★ imagePromptDirection
- Clay (modelingCompound)
- Comic book (comicBook)
- Crayon (crayon)
- Fantasy art (fantasyArt)
- Film noir (filmNoir)
- Golden age (goldenAge) ★ imagePromptDirection
- Golden hour (goldenHour)
- Illustration (illustration)
- Layered papercut (layeredPapercut)
- Lego (lego)
- Line art (lineArt)
- Neon noir (neonNoir)
- Paper cutout (paperCutout)
- Pencil sketch (pencilSketch)
- Realistic (realistic)
- Renaissance (renaissance)
- Stick figure (stickFigure)
- Technical illustration (technicalIllustration)
- Tiny world (tinyWorld)
- Watercolor (watercolor)
- Whimsical (whimsical)

### 18.2 characterPrompt 范式 (12+ style 有)

7 段 telegraphic 描述 meta-instruction: Demographics / Skin / Build / Features / Hair / Clothing / Accessories。每个 style 给出 banned 词列表。

### 18.3 Sample Prompt 范式

Image prompt (50): 主体 + 镜头/光 + dialogue in 引号 (含 <umm> <chuckle> <sigh> 标签) + SFX 行

Video prompt (50): 主体动作 + 镜头运动 + 光影调色 + 画幅 + SFX + Maintain identities throughout

Avatar prompt (7): 动作 + 表情 + 节奏 (slow blinks / pause), 外观由 reference 图提供

### 18.4 模型频率

- image: runware-z-image-turbo (43) | runware-gpt-image-2 (7)
- video: kling-3-pro / seedance-pro-fast / pixverse-v5-fast / p-video / happyhorse-v1 各 7 | ltx-2-fast 6
- avatar: p-video-avatar (4) | omnihuman-1-5 (3)

### 18.5 决策影响 (v6 + Phase 2)

- sceneBreakdown = gemini-2.5-flash-lite
- image = runware-z-image-turbo
- video = runware-kling-3-pro (9 选 1 留 API 配置)
- avatar = runware-p-video-avatar (本地化换 SadTalker/MuseTalk)
- TTS 标签 SSML 转换
- image 默认 1536x1024 (16:9)

完整数据见 research/dump/trpc-phase2-summary.md。


## 19. Phase 3 增量 - Render Pipeline

### 19.1 render.latest schema (4 状态)

**Phase A**: processing progress=0 (queue)
**Phase B**: processing progress 1-99 (渲染中)
**Phase C**: processing progress=100 (finalizing: thumb 生成)
**Phase D**: success + mediaGeneratedId 完整

时间 0s→30s(progress=93)→46s(progress=100)→50s(success)

### 19.2 字段表

_id / status / progress / resolution / extension / renderer=gke / **engine=remotion** / createdAt / mediaGeneratedId{_id, type=video, file, filesAssociated, thumbnail, thumbnailPreview}

### 19.3 决策冲突

用户决策 1 是 "Remotion vs FFmpeg 哪个更经济就用哪个". Phase 3 确认 Fliki 用 Remotion + GKE.

新建议: 保持跟 Fliki 一致 (Remotion), 或重写轻量 (FFmpeg). 让用户重选.

完整 schema 见 research/dump/trpc-phase3-summary.md.
