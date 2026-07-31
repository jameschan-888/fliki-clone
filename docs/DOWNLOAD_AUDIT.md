# D:\下载 ZIP 技能包 审计清单

> 审计日期: 2026-07-27  
> 审计对象: `D:\下载` 内 27 个压缩包  
> 审计方法: 仅读取 ZIP 内源码、依赖、许可证和入口，不运行、不解压到主项目、不调用任何视频生成 API  
> 主项目: `D:\workspace\Fliki视频制作还原`

---

## 1. 总览

| 优先级 | 包 | 核心价值 | 主许可证 | 本机可用度 |
|---|---|---|---|---|
| **P0** | Pixelle-Video-v0.1.15-win64.zip | 本地视频工作流、MoviePy、ComfyKit、FastMCP、Edge TTS、Streamlit | Apache-2.0 | 中 |
| **P1** | MoneyPrinterTurbo-main.zip | Script-to-Video、字幕、转场、批量任务、Streamlit WebUI | MIT | 中 |
| **P1** | hyperframes-main.zip | HTML→视频、过渡 shader、SKILL 文档、动效规则 | Apache-2.0 | 高 |
| **P2** | OmniVoice-Studio-main.zip | 本地 TTS、声音克隆 | AGPL-3.0（限制） | 待测 |
| **P3** | ViMax-main.zip | 长视频自动编排 | 待查 | 低 |
| **P3** | Seedance2-Storyboard-Generator-main.zip | 分镜脚本生成 | 待查 | 低 |
| **P3** | moyin-creator-main.zip | 角色/分镜创作 | 待查 | 低 |
| **P3** | MoneyPrinterPlus-main.zip | 自动化发布 | 待查 | 低 |
| **P3** | jianying-editor-skill-main.zip | 剪映后处理 | 待查 | 低 |
| **P3** | crawl4ai-main.zip | 通用爬虫 | 待查 | 低 |
| **无关** | v2rayN-windows-64.zip | 翻墙工具 | 无关 | 无 |
| **无关** | openship-main.zip | 电商物流 | 无关 | 无 |
| **无关** | ruflo-main.zip | Codex/MCP 编排（已采纳） | 无关 | 无 |
| **无关** | agency-agents-main.zip | 通用 Agent 集合 | 无关 | 无 |
| **无关** | GoodJob*.zip | 其他项目备份 | 无关 | 无 |
| **无关** | mcp-crawl4ai-rag-main.zip / reachsurge-搜客MCP.zip | 与视频无关 | 无关 | 无 |
| **无关** | awesome-stock-resources-master.zip | 资源链接清单，可索引 | CC0 | 仅作素材来源索引 |
| **无关** | awesome-workflow-automation-main.zip / Open-Generative-AI-main.zip / blcaptain-lingjian-video-main.zip / awesome-seedance-main.zip | 已采纳 / 链接清单 | 无关 | 无 |

---

## 2. Pixelle-Video (P0)

### 项目画像
- Python ≥ 3.11，Streamlit + FastAPI + MoviePy + Edge TTS + ComfyKit + FastMCP。
- 视频生成流水线：linear pipeline (template method) → storyboard → 帧 → FFmpeg 合成。
- 模块：`api/`、`pixelle_video/`、`web/`、`templates/`、`bgm/`、`resources/`。
- 强依赖 ComfyUI 作为底层推理服务器。

### 可直接复用（白名单）
- **Edge TTS 包装**：`pixelle_video/utils/tts_util.py` + `pixelle_video/tts_voices.py`。
  - 当前 Fliki 已有 Edge TTS Provider，但缺少统一的“语音目录与语速/音色归一化”。
  - 可以抽出 `tts_voices.py` 中 zh-CN voice 列表，合并到 `voice-gallery` 的 Voice Gallery 数据源。
- **字幕/分镜生成提示词模板**：`pixelle_video/prompts/*.py`。
  - `asset_script_generation.py`、`topic_narration.py`、`title_generation.py`、`image_generation.py`。
  - 是文档级提示词，不调用 API 也不强依赖云端，可直接借鉴写作风格。
- **Pipeline Context 模型**：`pixelle_video/models/progress.py`、`storyboard.py`。
  - 适合借鉴进度事件/状态机思路，但当前 Fliki 已有 workflow_pipeline，不建议重写。

### 只能借鉴（不能搬代码）
- **`LinearVideoPipeline` 模板方法**：与 Fliki 现有 `workflow_pipeline.py` 重复，直接搬会引入两套调度器。只借鉴分层与上下文传递思路。
- **ComfyKit 集成**：本机无 ComfyUI 服务；硬塞会引入大量外部依赖。建议保留为可选项，仅借鉴其“Provider 可插拔”接口风格。
- **Streamlit 工作台**：Fliki 用 React；不能换成 Streamlit。可借鉴 Streamlit 的“输入预览输出”分区思路应用到现有前端。
- **`html2image` 帧生成**：适合做封面/卡片/字幕帧；当前 Fliki 用 Remotion/ffmpeg。
- **`fastmcp` 资源声明方式**：当前 Fliki 用 FastAPI REST；如未来要做 MCP 服务，可借鉴其 `register_*` 模式。

### 不应使用
- **`moviepy==1.0.3`**：与本地 MoviePy 1.x 不兼容（Fliki 周边已用 ffmpeg + Pillow），引入会干扰。
- **ComfyUI 默认配置**：本机无 GPU，会卡住所有视频生成。
- **任何含 `dashscope` / `azure-cognitiveservices-speech` / `google-genai` 的示例**：本机测试期间应避免触发付费 API；当前 Fliki 走本地 + MiniMax。

### 本机兼容
- 强依赖 Python ≥3.11，本机是 3.12.7，可跑。
- 强依赖 ComfyUI；本机无 ComfyUI → **不能直接启动**。
- MoviePy 1.x 与 2.x 行为差异大；本机 MoviePy 现状不明，跑前必须先 `pip show moviepy`。

---

## 3. MoneyPrinterTurbo (P1)

### 项目画像
- Python ≥ 3.11，Streamlit + FastAPI + MoviePy 2.2.1 + Edge TTS + faster-whisper + Redis + LiteLLM。
- 核心：脚本→分镜→TTS→字幕→素材→合成。
- 模块：`app/services/{video,subtitle,voice,material,bgm,utils/video_effects}.py` + `app/models/schema.py`。

### 可直接复用
- **`VideoParams` 数据结构**：`app/models/schema.py` 里的枚举非常完整。
  - `VideoConcatMode`（random/sequential）→ 借鉴到 `scene_drafts`。
  - `VideoTransitionMode`（fade_in/out、slide、shuffle、zoom_in/out）→ 直接可加入 `camera_motion`。
  - `VideoAspect`（landscape/portrait/square）+ `to_resolution()` → 已具备 1920×1080 / 1080×1920 / 1080×1080 切换，可借鉴。
- **`subtle_file_security`**：`app/utils/file_security.py`。
  - 路径合法化、文件名清理、Windows 保留名过滤。
  - 当前 Fliki 缺少统一路径安全工具，可以借鉴成一个独立模块。
- **`should_use_bgm` 业务规则**：`app/services/bgm.py`。
  - 把“是否需要 BGM”从 Provider 中解耦出来；可借鉴到 `providers/music/__init__.py`。
- **`video_effects.transition` 系列**：`app/services/utils/video_effects.py`。
  - FadeIn/Out、Slide、Zoom In/Out 都是 MoviePy 2.x 的纯 Python 封装。
  - 适合抽离成无状态的工具函数，给 Remotion 之外的视频做兜底合成。

### 只能借鉴
- **任务状态机**：与 Fliki 现有 workflow_runs 重叠；只借鉴“任务恢复 + cross_post future 注册/反注册”的写法。
- **Redis 任务管理**：单机不必要；Fliki 用 SQLite + 进程内 Future 已经够。
- **faster-whisper 配置**：本机已用 faster-whisper，建议保持；只借鉴 word timestamps 与标点切分逻辑。
- **Sonilo / ElevenLabs Music**：付费 BGM，与本地策略冲突。

### 不应使用
- **`moviepy==2.2.1`**：当前 Fliki 的 ffmpeg + Pillow 已够用，引入会破坏稳定性。
- **`streamlit==1.59.1`**：与 Fliki 的 React UI 冲突，且 Streamlit 不是多用户产品形态。
- **`dashscope`、`azure-cognitiveservices-speech`、`google-genai`、`litellm`**：避免触发付费 API。
- **`twelvelabs` 视频理解**：当前不需要；模型大、依赖 GPU。

### 本机兼容
- 全部纯 Python；只要不导入 ComfyUI / 启动 Streamlit 即可独立审计源码。
- 与本机 Edge TTS、faster-whisper 一致。

---

## 4. HyperFrames (P1)

### 项目画像
- TypeScript monorepo，Bun + npm workspaces，Node ≥22。
- 多包：`core` / `engine` / `producer` / `player` / `studio` / `studio-server` / `cli` / `parsers` / `lint` / `shader-transitions` / `aws-lambda` / `gcp-cloud-run` / `sdk` / `sdk-playground`。
- 核心：`@hyperframes/engine` = Puppeteer + FFmpeg 把 HTML 渲染成视频。

### 可直接复用
- **HTML 模板/转场目录**：`registry/registry.json` 中有完整示例（warm-grain, play-mode, swiss-grid, vignelli, decision-tree, kinetic-type, product-promo, nyt-graph, data-chart, us-map-* 等）。
  - 适合作为 Fliki 模板市场的扩展来源。
- **SKILL 文档**：`.agents/skills/` 与 `.claude/skills/`。
  - `seam-craft`、`cut-the-curve`、`captions-overlay`、`motion-doctrine`、`oversized-cursor`。
  - 是写作级知识，可直接抄进 Fliki 的模板说明和编辑器引导。
- **transitions registry**：可作为 Remotion 转场/动画的“灵感与命名约定”参考。

### 只能借鉴
- **Puppeteer + FFmpeg 渲染**：Fliki 已经走 Remotion；不必切。但可以借鉴其 WebGL/Shader Transition 的实现细节。
- **`@hyperframes/parsers` (AST 解析)**：借鉴思路，可在 Fliki 模板编辑器里做模板字段校验。
- **`@hyperframes/lint` / `validators`**：思路可用于 Fliki 模板发布前的检查。

### 不应使用
- **任何 AWS Lambda / GCP Cloud Run 包**：与本地策略冲突。
- **Bun + Node 22 工程化**：与当前 Fliki 的 Node 24 + tsx + vite 体系不同；不要把 Bun 工程硬塞进项目。
- **`@hyperframes/sdk-playground`**：演示型，与生产无关。

### 本机兼容
- 当前 Node 24，可跑；但 HyperFrames 工程依赖 Bun，装 Bun 成本高，不建议直接安装。
- **建议只借鉴 SKILL 文档和注册表**，不引入任何 HyperFrames 包。

---

## 5. OmniVoice-Studio (P2)

### 项目画像
- 桌面端 11labs 替代品；TTS、声音克隆、视频配音；声称 646 种语言。
- AGPL-3.0，**强 copyleft**：任何衍生作品必须开源。

### 可直接复用
- **OpenAI 兼容 API 文档/接口风格**：可作为 Fliki “本地 TTS Provider” 的设计参考。

### 只能借鉴
- **TTS 引擎切换思路**：可作为 Fliki 多个本地 TTS Provider 的统一接入模式。

### 不应使用
- **任何 AGPL 代码直接并入主项目**。
- **未审计前不安装/不启动**；AGPL 包常常自带模型下载和外联调用。

### 本机兼容
- 已知 beta，需先看模型大小与 CPU/GPU 依赖。
- 当前 Intel Iris Xe 无 CUDA；轻量 CPU 量化模型值得尝试，但要在隔离目录里做。

---

## 6. 其他包 (P3 / 无关)

| 包 | 处置 |
|---|---|
| ViMax-main | 长视频编排，待审计；可能价值不高 |
| Seedance2-Storyboard-Generator-main | 仅做分镜文案，不要触发视频 API |
| moyin-creator-main | 角色/分镜创作，待审计 |
| MoneyPrinterPlus-main | 自动化发布，待审计 |
| jianying-editor-skill-main | 剪映后处理工具，不作核心引擎 |
| crawl4ai-main | 通用爬虫，可用于未来素材采集 |
| v2rayN / openship / ruflo / agency-agents / GoodJob* | 与本项目无关，忽略 |
| awesome-stock-resources-master | CC0 资源清单，可整理为本地 Stock 来源索引 |
| mcp-crawl4ai-rag-main / reachsurge-搜客MCP | 与视频无关，忽略 |

---

## 7. 直接落地建议（按 ROI）

### 立刻做（不引入新依赖）
1. 把 `VideoAspect` 三档宽高比加入 Fliki 前端草稿表单。
2. 把 `VideoTransitionMode` 中的 fade / slide / zoom 映射到现有 `scene_drafts.camera_motion`：
   - `zoom-in` / `zoom-out` 已有；新增 `fade-in` / `fade-out` / `slide-left` / `slide-right`。
3. 把 `file_security.py` 抽出独立工具模块：路径/文件名清洗、Windows 保留名拒绝。
4. 在 `docs/` 增加 `motion-doctrine.md`、`cut-the-curve.md`、`captions-overlay.md`，
   把 HyperFrames SKILL 的思路（向量法则、Seam Gate、overlay vs band）抄进 Remotion 模板说明。

### 短期（P1）
5. 给 Voice Gallery 注入 Pixelle 的 zh-CN Edge TTS 列表，去重并扩展 locale。
6. 给 `autoedit` 提示词增加 Pixelle 的“题目长度 + 关键信息 + 字数限制”结构。
7. 给 `provider_config` 增加 “BGM 是否启用” 通用判定字段，参考 `should_use_bgm`。

### 中期（P2）
8. 在隔离目录部署 OmniVoice-Studio（先 AGPL 评估），用 HTTP 适配器接入 TTS。
9. 把 Pixelle `LinearVideoPipeline` 的“上下文 + 进度回调”思路合并进 workflow_pipeline，
   **仅做重构**，不引入 MoviePy。

### 不做
- 不安装 Pixelle 的 Streamlit/ComfyUI 全栈。
- 不引入 HyperFrames 的 Bun/Node 22 生态。
- 不引入 OmniVoice 的 AGPL 代码到主项目。
- 不引入任何触发付费视频 API 的包作为“开箱即用”依赖。

---

## 8. 审计结论

- **可直接复用**：Edge TTS 列表、视频参数枚举、文件安全工具、BGM 启用判定、HyperFrames SKILL 文档、registry 模板示例。
- **只能借鉴**：linear pipeline、Streamlit 工作流、Puppeteer 渲染、ComfyKit、TTS 引擎抽象。
- **不应使用**：MoviePy 1.x/2.x 全栈、ComfyUI/Streamlit WebUI、Bun/Node 22 工程化、AGPL 代码并入、任何触发付费视频 API 的依赖。

本次审计只读取 ZIP 内文件，没有改动 `D:\workspace\Fliki视频制作还原` 内任何源代码。
