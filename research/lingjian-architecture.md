# blcaptain-lingjian-video 架构对照笔记

阅读范围：`D:\下载\blcaptain-lingjian-video-main\blcaptain-lingjian-video-main`（与 Codex 装在 `C:\Users\chanl\.codex\plugins\cache\blcaptain-lingjian-video\lingjian-video\0.2.0` 内容一致，仅路径不同）。

目的：把灵剪（lingjian-video，Apache-2.0）作为独立参考实现，提取对我们 Fliki 视频制作还原项目有用的设计，不复制代码、不替换我们现有架构。

## 1. 总览

| 维度 | 灵剪 | Fliki 视频制作还原 |
|---|---|---|
| 语言 | Python 3.11+ + Node 20 | Python 3.12 + Node 24 |
| 后端 | FastAPI（CLI-first，Web 次之） | FastAPI + REST（8001） |
| 入口 | `uv run lj ...` Typer CLI；`apps/api/lingjian_api` 留空壳 | `python -m uvicorn main:app` |
| 持久化 | 每个项目独立目录：`project.yaml` + `manifest.json` + `.lingjian/index.sqlite` + `artifacts/*.json` + `history/` + `renders/` | 单 SQLite `backend/data/app.db`，19 张表 |
| 渲染 | ffmpeg drawtext + concat（M1 仅 ffmpeg_card） | Remotion + FFmpeg + 系统 Chrome |
| 流程 | 7 阶段闸门：created → input_ready → script_review → voice_review → visuals_review → rendered → exported；每关必须 HMAC 签名审批才能进下一关 | 草稿 → confirm → 编排器跑 Stock/TTS/Music/Render；Auto-edit 单独一条链 |
| Provider | 子进程 CLI 契约（stdin JSON → stdout JSON）；env 注入 key；mock 不能 release | 函数式 Provider，配置存 SQLite；mock 默认但没拦 release |
| 凭据 | macOS Keychain / Linux secret-tool / Windows 用户环境变量；默认 ephemeral-env | `.env` 文件 + 接口注入到 `os.environ`；当前没有密钥回溯落盘机制 |
| 错误模型 | `LingjianError(error_code, message_zh, hint, details)` → `ErrorResult` | FastAPI `HTTPException(status_code, detail)` |
| 测试 | pytest；mock 提供方（CLI contract fake_llm / fake_tts）只演示契约 | unittest discover；HTTP/ONNX 全 mock；73 用例 |

## 2. 灵剪最有价值的 5 个设计点

### 2.1 五阶段审批 + HMAC 签名与产物哈希绑定

`packages/core/approvals.py` 用项目级 `approval_secret` 给每条审批生成 HMAC 签名，并把签名绑到 `artifact_sha256 = canonical_json_hash(artifact)`。任何源文件改了就让审批 `stale`，下次渲染直接被 `validate_render_gate()` 拒掉。

对应实现要点：
- 路径：`artifacts/script.json`、`voice_plan.json`、`visual_plan.json`
- 校验函数：`validate_render_gate(project)` 返回 `APPROVAL_REQUIRED` 或 `APPROVAL_STALE`
- 哈希约定：`canonical_json_hash()` 排序 + 去除 `generated_at` 等易变字段

我们已经有等价的“草稿 confirm 锁定 + version 升号 + draft_revisions 快照”，不需要照搬 HMAC；但可以借鉴“内容改 → 批准自动失效”的语义，写到 P5D-6（Provider 持久化 + 草稿一致性校验）。

### 2.2 capabilities 库：分门别类的横切能力

`capabilities/` 目录包含 5 个独立能力：
- `cadence/` ffmpeg silencedetect → 语音段起点；画面事件起点 ≥ 配音词起点
- `transition-library/` 四象限转场谱系 + 匹配器 + 稀缺守卫（≤3 个强转场）
- `sfx-strategy/` 动作-音效映射 + 五铁律
- `layout-safety/` 大字-标签间距硬规则
- `director-board/` 数据驱动的导演板（React 独立项目）

每个文件只做一件事，是“固化能力”而不是“软提示词”。README 明确说：换比例、换风格 = 复用这些能力换皮重排，不重做。

我们当前把节奏、字幕、转场都揉在 `workflow_pipeline` 或 `autoedit_pipeline` 里。可借鉴：把 cadence 抽出来，把字幕分块、CJK 断行抽出来，做成独立单文件模块。

### 2.3 Provider 抽象用 CLI 契约而不是函数

`examples/providers/fake_llm_contract.py` / `fake_tts_contract.py` 演示：
- LLM：`stdin` 读 JSON，`stdout` 输出 `{"scenes": [...]}` 顶层非空
- TTS：`stdin` 读 JSON，`stdout` 输出 `{"audio_base64": "...", "duration_sec": >0}`

优点：换任何 provider 实现（云 API、本地 CLI、远端服务）都只要遵循 stdio JSON 接口，不依赖 Python 库导入。

我们目前用函数式 Provider（PexelsHTTPProvider、EdgeTTSProvider、Wav2LipONNXAvatarProvider）。这条思路更轻量，但失去了“在另一台机器上跑 provider 进程”的灵活性。**不要照搬**，但可在未来需要把 GPT-SoVITS 部署到第二台机器时再考虑 CLI 契约。

### 2.4 capabilities + doctor 双轨能力探测

`packages/core/capabilities.py` 的 `detect_capabilities(env, lookup)` 输出按 `kind` 分组的 `CapabilityGroup`（llm / tts / visual / render / font / cli / local_tts），每组有 `best_provider_id()`。`packages/core/doctor.py` 把 capability 报告再生成可发布的 `DoctorResult`（区分 mock / 非发布级 provider）。

我们 `backend/env_check.py` 已经落 `backend/data/env-check.json`，包含 `wav2lip_onnx`、`gpt_sovits`、`capabilities` 等字段。可借鉴点：
- 字段命名统一为 `kind → group → provider × method`
- 明确标 `publish_grade: bool`，让前端能直接显示“当前用的是 mock provider，不能 release”
- `next_steps` 列表给出具体修复动作（已经部分实现）

### 2.5 错误码 + 中文消息 + 提示 + 详情

`packages/core/errors.py`：
```
class LingjianError(Exception):
    error_code: str     # 机器可读
    message_zh: str     # 用户可读
    hint: str           # 下一步操作
    details: dict       # 上下文（field / value / path 等）
```

我们 FastAPI 的 `HTTPException` 只带 `status_code` + `detail` 字符串。前端要做错误展示/国际化都不方便。**这是高 ROI 的小改动**：把 `errors.py` 引入后端，让所有路由把 `LingjianError` 转成统一响应体。

## 3. 灵剪与 Fliki 的本质区别（不要强行拉齐）

| 维度 | 灵剪 | Fliki | 结论 |
|---|---|---|---|
| 入口形态 | CLI 优先 + 本地 Web 控制台 | Web SPA + FastAPI REST | 灵剪想“让 agent 在 CLI 里逐关签字”，我们想要“用户在浏览器里看进度”。维持各自形态 |
| 项目隔离 | 每个项目独立目录 + 自己的 SQLite | 单库 + projects 表 | 我们已经有项目维度，不需要每项目一份 DB |
| 渲染 | ffmpeg drawtext + concat | Remotion + FFmpeg | Remotion 更适合多 Scene + 字幕 + 旁白 + 音乐的多层合成，不换 |
| 审批模型 | 5 阶段 HMAC 签名 + stale 重审 | 单 confirm 闸门 + version 自增 + draft_revisions 快照 | Fliki 当前已足够；不引入 HMAC 以免改成本变高 |
| Provider | CLI 进程契约 | 函数式 + Pydantic 配置 | 维持现状；GPT-SoVITS 走 HTTP 适配器即可 |
| Mock 拦截 | `is_mock=True` provider 不能 release | mock 是默认（甚至 dev 用） | **应当收紧**：mock provider 触发 confirm 时应给出告警，详见 §5 |

## 4. 灵剪里我们不需要抄的东西

- `director-board/`：独立 React 项目，做“能量曲线 + 逐镜确认”。超出当前 Composer 范围。
- `apps/web/app/{new,script-review,voice-review,visuals-review,export}/page.tsx`：5 个 StageWorkflowPage 用同一组件。我们 `app/drafts.html` / `app/voices.html` / `app/autoedit.html` 已经分页，按业务分文件更易维护。
- `apps/cli/lingjian_cli/main.py` 223KB：Typer 子命令非常全（ingest text/url/command/codex/image/audio/video + approve script/voice/visuals + credentials）。我们不走 CLI，不引入。
- HMAC 签名 + canonical_json_hash：合规级别超出当前项目需求。
- 整片“蓝图 + 能量曲线”：超出当前业务目标；先跑通脚本/草稿/剪辑，再考虑剧本节奏。

## 5. 可在 Fliki 项目里复用的 5 个动作（按收益排序）

### A. 收紧 mock provider：明确“mock 不能 release”

**问题**：当前 `provider_config.py` 的 mock 字段与真实 provider 并列，confirm 时不区分。

**最小改动**：在 `provider_configs.config_json` 加 `is_mock: true/false` 字段；`workflow_pipeline.py` 的 confirm 闸门校验 default provider `is_mock`，命中则返回 `MOCK_PROVIDER_BLOCKS_RELEASE` 错误码。

**收益**：避免“开发用 mock 配置去跑真生成”事故；让 env-check.json 能区分 `publish_grade`。

**工时**：0.5–1 天。

### B. cadence 抽取成独立 service

**问题**：`autoedit_pipeline.py` 的 silencedetect 用得对，但脚本 → 视频链路里没把配音段起点反馈到场景时长。

**最小改动**：新建 `backend/services/cadence.py`，把 silencedetect + 词级起点解析抽出来；`workflow_pipeline.py` 在生成 TTS 后调一次，把 voice 段起点写到 `workflow_nodes.result.cadence`，场景时长按它修正。

**收益**：解决灵剪 README 提到的“画面比配音快”问题。

**工时**：1 天（要写测试）。

### C. errors.py 统一错误体

**问题**：路由层抛 `HTTPException(detail=...)`，前端只能拿到字符串。

**最小改动**：建 `backend/errors.py` 抄 `LingjianError` 模式；写一个 FastAPI `exception_handler` 把 `LingjianError` 转成 `{error_code, message, hint, details}` 响应；router 关键路径（confirm / retry / upload）切换。

**收益**：前端可以做错误提示国际化、灰度统计。

**工时**：0.5 天。

### D. capabilities 目录风格

**问题**：当前所有横切能力都散在 `workflow_pipeline.py` / `autoedit_pipeline.py` 里。

**最小改动**：建 `backend/services/`（或 `backend/capabilities/`）子目录，至少把 cadence、字幕分块、CJK 断行、转场提示做成单文件模块 + 各自单测。

**收益**：未来换比例、换风格不需要再改 pipeline 主体。

**工时**：1.5 天。

### E. env-check.json 升级为 capability 报告

**问题**：现有 env-check.json 字段稳定但缺发布级判定。

**最小改动**：参照灵剪 `CapabilityGroup`/`ProviderGroupStatus`，让 env-check 输出按 kind 分组，每组包含 `publish_grade` + `providers[]`（每个含 `is_mock` + `available` + `latency_ms`）。

**收益**：前端 env-check.html 展示更清晰；为后续自动推荐最佳 provider 打底。

**工时**：0.5 天（已有 env-check.json 结构）。

## 6. 仓库交叉点（仅引用，不复制）

- `examples/providers/fake_llm_contract.py`、`fake_tts_contract.py`：可作为我们写新 Provider 测试夹具时的 I/O 范式参考。
- `capabilities/cadence/cadence.py`：和我们在 `autoedit_pipeline` 里用的 silencedetect 完全同款，可作为注释里的引用。
- `packages/core/credentials.py`：凭据存储的跨平台表（macOS Keychain / secret-tool / Windows user-env）。我们 Windows 用 `.env` 足够，不必引这套。
- `apps/cli/lingjian_cli/main.py`：仅用于查 subcommand 名字和阶段顺序。

## 7. 风险与边界

- 灵剪仓库版本 `v1.1.0`（HEAD 解析到 `0.2.0`，不是最新 tag）。后续若该仓库节奏加快，重新核对 SKILL.md 与 capabilities README。
- `director-board/` 是独立 React 项目，不是 npm 包，不要试图 import；仅作 UX 参考。
- `pyproject.toml` 锁 Python 3.11-3.12；我们当前是 Python 3.12.7，刚好兼容。
- LingjianError 的 `message_zh` 字符串在错误码与提示里有大量业务术语（如 `PROVIDER_AUTH_FAILED`、`LLM_RATE_LIMITED`）；引入时不要照抄字符串，统一放在 `backend/i18n/` 或类似位置，方便日后扩展。
- 不要把灵剪的 `director-board/`、`examples/providers/`、`capabilities/transition-library/transitions.json` 直接搬进 Fliki 项目；只搬运设计思路。

## 8. 下一步建议

不立即动手；先在下一阶段里挑一个最小动作（A 推荐）作为切入点。
- 优先级：A > C > E > D > B
- A 完成后再判断是否引入 D（capabilities 目录风格）。
- B 涉及语音段对齐，当前仅在 Auto-edit 链路有意义；脚本 → 视频链路要看 P5B 的实测再决定。
- 不动 HMAC、不动 CLI、不动 director-board。
