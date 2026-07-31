# D:\下载 ZIP 技能包 Web 页面 审计清单

> 审计日期: 2026-07-27  
> 范围: 27 个 ZIP 中真正含前端/HTML/模板页面的包  
> 方法: 仅读取 ZIP 内文件，未运行任何程序

---

## 1. Web/HTML 资产清点

| 包 | 类型 | 关键页面 | 数量 |
|---|---|---|---|
| **Pixelle-Video** | HTML 视频帧模板 + Streamlit WebUI | templates/1080x1920/*、templates/1920x1080/*、templates/1080x1080/*、web/app.py | 28+ HTML 模板 + 7 个 Streamlit 组件 |
| **MoneyPrinterTurbo** | Streamlit WebUI | resource/public/index.html | 1 个首页 HTML（仅占位） |
| **hyperframes** | Puppeteer 渲染的 HTML 视频模板 + 文档 | packages/core/docs/quickstart-template.html、registry 中 8+ 模板、agents/skills/changelog-video/examples/master-skeleton.html、docs/snippets/TemplateCard.jsx | 50+ 模板骨架 |
| **blcaptain-lingjian-video** | Next.js 14 App Router（多页） | apps/web/app/{page,new,script-review,voice-review,visuals-review,export}/page.tsx + styles.css、director-board/standalone.html、docs/gallery.html | 1 套完整产品 UI |
| **OmniVoice-Studio** | 桌面 Electron Web UI | web/（未审） | 数量未确认 |
| **Open-Generative-AI** | 文档/示例 | 链接清单为主 | 0 真实前端 |
| **mcp-crawl4ai-rag** | MCP 服务 | 无 Web | 0 |
| **Seedance2 / moyin / ViMax / MoneyPrinterPlus** | 后端或脚本 | 0 真实前端 | 0 |

---

## 2. Pixelle-Video 视频帧模板

### 可直接复用（CSS / DOM 结构）
- **CSS 变量体系**（`templates/1080x1920/image_neon.html`）：
  ```css
  --bg: #0b0f1a; --fg: #eaf6ff; --muted: #9fb6c6;
  --accent: #3cf0ff; --accent2: #ff3fe0; --accent3: #f0e130;
  --card-bg: rgba(12, 14, 20, 0.5); --border: rgba(255,255,255,0.12);
  ```
  → 适合做 Remotion 模板的 design tokens。

- **垂直分屏 4 段布局**：`grid-template-rows: 15% 53% 18% 14%;`  
  → 可借鉴到 9:16 模板。

- **中文安全字体栈**：
  `'Noto Sans SC', 'PingFang SC', 'Source Han Sans', 'Microsoft YaHei'`
  → 直接用在 Fliki 草稿预览和字幕模板。

- **页面尺寸 meta**：
  `<meta name="template:media-width" content="1024"><meta name="template:media-height" content="1024"><meta name="viewport" content="width=1080, height=1920">`
  → 可借鉴成 Fliki 模板元数据。

### 只能借鉴
- **视频帧模板（HTML→PNG）**：当前 Fliki 用 Remotion，不切回 HTML→PNG 路径。
- **Streamlit UI 组件**：与现有 React UI 不兼容。
- **ComfyKit 调用**：本机无 ComfyUI 服务。

### 不应使用
- **Google Fonts 外链**：Fliki 当前渲染在本地 Remotion，无外网渲染；外部链接会阻塞。
- **外部 image 占位 `{{image}}`**：Remotion 是从素材库传 prop，不在 HTML 里写占位。

---

## 3. MoneyPrinterTurbo WebUI

### 可直接复用
- 无（resource/public/index.html 只是 1 个 README 链接）。

### 只能借鉴
- 文本布局与"输入即生成"心智模型。

### 不应使用
- Streamlit UI 本身。

---

## 4. hyperframes HTML 模板

### 可直接复用
- **`quickstart-template.html` 的元信息结构**：
  ```html
  <meta name="viewport" content="width=1920, height=1080" />
  <meta data-composition-id="my-video" data-width="1920" data-height="1080" />
  ```
  → 适合直接抄到 Fliki 模板编辑器的元数据读取。

- **master-skeleton.html 的“verbatim scaffold” 注释风格**  
  → 适合作为 Remotion 模板骨架的注释范式。

- **script-tokens.json 的显示/朗读分层**：
  ```json
  { "display": "JSON", "spoken": "jay-sawn" }
  ```
  → 适合给 Fliki 字幕增加 “显示/朗读不同” 字段。  
  → 当前 Fliki 字幕是统一文本，没分层。

- **TemplateCard.jsx 卡片组件**：可借鉴结构做 Fliki 模板市场列表。

### 只能借鉴
- **GSAP 时间轴**：Fliki 当前用 Remotion；不能并行引入 GSAP。
- **Puppeteer 渲染**：与 Remotion 路线不同，不并入。

### 不应使用
- 任何 `@hyperframes/*` 包；本机 Node 24 + tsx + vite 不兼容 Bun 工程。
- 外部 CDN 加载 GSAP：本地渲染需内联。

---

## 5. blcaptain-lingjian-video Next.js UI（最完整）

### 可直接复用（结构 + CSS 命名）
- **三栏布局**（styles.css）：`.app-shell { grid-template-columns: 240px minmax(0,1fr) 280px; }`  
  → 与现有 Fliki 草稿编辑器 `app/dist/index.html` 思路一致，可加 `.inspector` 右栏。

- **侧边栏品牌块**：
  ```css
  .mark { background:#e2f2f1; color:var(--accent); width:36px; height:36px; border-radius:6px; display:flex; align-items:center; justify-content:center; }
  ```
  → 适合做 Fliki Avatar 库徽标。

- **状态语义色 token**：
  ```css
  --warn: #9f5a10; --danger: #ad2f2f; --ok: #2f7d4f;
  ```
  → 直接抄到 Fliki 草稿/渲染节点的 status 标签。

- **状态机 + 阶段面板**（page.tsx）：
  ```
  created → input_ready → script_review → voice_review → visuals_review → rendered → exported
  ```
  → 与现有 Fliki 工作流一致；可借鉴 "三审缺失/QA hard fail/mock provider 阻止 release" 的拦截文案。

- **approvals 列表 + 状态 hash**（script.json / voice_plan.json / visual_plan.json）  
  → 适合给 Fliki 增加"每镜确认卡 + 三审进度"。

- **`stage-pages.tsx` 单一驱动多页**：
  ```ts
  <StageWorkflowPage stage="script-review" />
  ```
  → 适合 Fliki 把 script/voice/visuals 三审合并到同一组件。

- **`director-board/standalone.html`**：分镜导演板，纯 HTML + JS；可借鉴 board 数据结构（`allConfirmed`、`confirmedCount`）。

- **`docs/gallery.html`**：作品画廊，自带 light/dark 主题切换 + 窄文大字：
  ```css
  --paper:#f4f1ea; --ink:#1a1a18; --accent:#1f4e79; --gold:#b08a3e;
  ```
  → 直接抄进 Fliki 模板市场页面。

### 只能借鉴
- Next.js App Router 路由（Fliki 当前是 Vite 多页静态，可借鉴 page 拆分思路）。
- CSS Grid 三栏 + Inspector 模式。

### 不应使用
- 整个 Next.js 工程（与当前 Vite + React 19 体系冲突）。
- 任何来自该工程的 React 组件源码（许可证和兼容性问题）。

---

## 6. OmniVoice-Studio Web UI

### 状态
- 未读取页面内容；本机测试期间应避免启动。

### 可直接复用
- 仅参考其“OpenAI 兼容 API 适配”文档，不搬 UI。

---

## 7. 总览：哪些可直接搬到 Fliki 现有 UI

| 模块 | 来源 | 借鉴什么 |
|---|---|---|
| AppShell 三栏布局 | blcaptain | sidebar / canvas / inspector |
| 状态色 token | blcaptain | warn/danger/ok |
| 阶段面板 + approvals | blcaptain | 三审状态机 + 进度条 |
| 主题变量 | Pixelle Neon + blcaptain Gallery | dark/light design tokens |
| 视频帧 CSS | Pixelle | 中文字体栈、grid 分段、装饰元素 |
| 模板元数据 meta | HyperFrames + Pixelle | composition-id、media-width/height |
| 字幕显示/朗读分层 | HyperFrames script-tokens | TTS vs 显示字幕分离 |
| 模板卡片 | HyperFrames TemplateCard.jsx | 模板市场卡片组件 |

---

## 8. 立刻可落地的 5 项（不引入新依赖）

1. **styles/app.css 增加 design tokens**：
   ```css
   :root {
     --bg: #f7f8fb; --surface: #ffffff; --ink: #16202a; --muted: #687381;
     --line: #d9e0e8; --accent: #126f7a;
     --warn: #9f5a10; --danger: #ad2f2f; --ok: #2f7d4f;
   }
   ```
2. **HomePage 顶部加 .app-shell 三栏布局**，把现有左侧栏、中间画布、右侧 EnvCheck 全部包起来。
3. **草稿编辑页新增 “display / spoken” 字幕双轨字段**：
   ```ts
   interface Subtitle { display: string; spoken?: string; }
   ```
4. **scene_drafts 增加 `media_width` / `media_height` 字段**，来自模板元数据。
5. **增加 `docs/motion-doctrine.md`**：抄录 HyperFrames motion-doctrine + cut-the-curve 的核心规则，作为 Remotion 模板设计规范。

---

## 9. 后续 P2（需要更多工作）

- 把 Pixelle 的 1080×1920 / 1920×1080 / 1080×1080 三档模板搬成 Remotion React 组件，代替当前的简单 `<Scene>`。
- 把 HyperFrames 的 transition catalog（crossfade / push-slide / zoom-through / waterfall / rack-focus）做成 Remotion 的 `<Transition>` 组件库。
- 把 director-board 的 `confirmedCount / total` 反馈机制接入 Fliki Scene 编辑器。

---

## 10. 结论

- **可直接复用**：CSS 变量、字体栈、布局三栏、状态色 token、字幕 display/spoken 分层、模板元数据 meta。
- **只能借鉴**：Streamlit / Next.js / GSAP / Puppeteer / ComfyKit 整体方案。
- **不应使用**：任何外部 CDN、Google Fonts、AGPL 包、ComfyUI / Streamlit 全栈、Bun 工程化。

本次审计仅读取 ZIP 内文件，未改动 `D:\workspace\Fliki视频制作还原` 内任何源代码。
