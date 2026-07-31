# ⚠️ 已并入 README.md — 本文档保留为历史参考, 不再单独维护

**主文档: [README.md](./README.md)**

本文档 (2026-07-27 版) 已并入 README.md. 后续请直接查阅 README.md; 本文档仅保留作为历史档案, 不再单独维护内容.

---

# Fliki 项目完成度与后续实施计划

更新时间：2026-07-25
项目根目录：`D:\workspace\Fliki视频制作还原`

## 结论

- 技术底座约 **99%**：P7 前端暴露完成（ProviderKeyManager + env-check 自动渲染 MiniMax 4 项 healthcheck）；env_check.py 集成 + 修 import httpx + Music lyrics/timeout。
- 用户可跑通主链路约 **83%**：Script-to-video 与 Auto-edit 全部从输入走到真实 MP4；TTS 多了一条云端路径（MiniMax）+ Edge TTS + GPT-SoVITS 三选一。
- 主要短板：MiniMax 真机 key 待核对（healthcheck 返回 "invalid api key"）、Composer 模板库、跨机 README 收口。

## 证据

| 验证项 | 结果 |
|---|---|
| Python 单元测试 | 宿主与 Docker 镜像内均 **213/213** 通过（含 P7-1..P7-4 MiniMax 全模态 49 个 + P6A GPT-SoVITS 4 + P6B 真实 Provider 失败回退 6 + 历史回归） |
| Python 编译 | `python -m compileall -q .` 通过 |
| 前端生产构建 | `npm.cmd run build` 通过 |
| Script-to-video | 草稿 → 编辑 → 确认 → Stock/TTS/Music → Remotion MP4 已闭环 |
| Auto-edit | 30 秒输入 → 转写/切分 → 编辑 → 确认 → 约 30.03 秒真实 MP4 |
| 渲染控制 | 进度、取消、硬超时、进程树回收已验证 |
| 数字人 | Wav2Lip-ONNX 适配器和静态回退已验证；模型本体尚未装入 |
| 声音 | Edge TTS Gallery 321 声音/142 locale；GPT-SoVITS HTTP 适配器已验证 |

## 模块评估

| 模块 | 完成度 | 当前判断 | 下一步 |
|---|---:|---|---|
| Phase 1-3 网站研究 | 100% | 已抓公开页、登录态页面、编辑器结构、API/Schema、渲染时间线 | 不再重复抓站 |
| FastAPI + SQLite | 95% | 主服务、初始化、19 张表、兼容增量逻辑已完成 | 后续只做拆分和运维 |
| Remotion + FFmpeg | 90% | 真实 MP4/JPG、进度、取消、超时、回收已完成 | 补 Docker 真验证 |
| P5A 场景草稿 | 100% | 草稿编辑、版本、排序、确认锁定和 UI 已完成 | 补 Avatar 字段/选择 |
| P5B 确认后流水线 | 95% | Stock → TTS → Music → Render 已真实跑通 | 修 Provider 密钥持久化 |
| P5C Auto-edit | 95% | 上传、ffprobe、Whisper、静音、草稿、确认、剪辑和重试已完成 | 增强异常提示和产品打磨 |
| Env-Check | 100% | 启动自检、Wav2Lip 明细和 Provider 发布能力矩阵已展示 | 后续仅维护 Provider 状态 |
| Voice Gallery | 90% | 321 声音/142 locale，试听链路已完成 | 与草稿选音交互再统一 |
| GPT-SoVITS | 90% | 客户端 + 4 个连通性测试 + 完整外部联调文档 | 等用户侧起服务做一次真实合成验收 |
| Wav2Lip-ONNX | 90% | 适配器、fallback、Env-Check、中文路径与 CPU 低分辨率真机验证完成 | 后续仅做性能优化或 CUDA 机器验证 |
| 前端工作台 | 95% | drafts/autoedit/voices/avatar/env-check 页面 + Provider 色卡 + 外部联调健康度 + key 变量名复制 | 后续做模板/历史/Composer |
| 部署与版本管理 | 100% | `.venv` + `INSTALL.md` + `scripts/{bootstrap,start_backend,start_frontend,stop_backend,status}.cmd` + Git 基线全闭环 | 仅做 README 收口与跨机验收 |

## 当前缺口排序

### P0：影响产品闭环

1. **GPT-SoVITS 外部联调**（已收尾 90%）：HTTP 客户端 + 4 个连通性测试 + 完整外部联调文档；真实合成需用户在另一台机器起服务（详见 docs/GPT_SOVITS.md）。
2. **真实外部 Provider 失败回退**（P6B 收尾）：Pexels / Pixabay / Freesound 6 个测试覆盖 401/429/网络/空结果/缺 key；`run_full_diagnostic` 新增 `external_providers` 字段；stock 默认 fallback 走次 Provider 不卡死。
3. **README 漂移**：本机默认端口未启动服务，也没有可用于验收的真人参考音频；现阶段只有 HTTP 适配器和 Mock 测试。


### P1：影响交付（已闭环）

1. ✅ 项目专用 `.venv` + 一键安装/启动/停止/状态脚本 + INSTALL.md（见 P6D 章节）。
2. ✅ 外部 Pexels/Pixabay/Freesound 网络、额度、授权和失败回退验收已通过（164/164 测试覆盖，P6B）。

### P2：可选增强

1. GPT-SoVITS 外部 HTTP 服务联调。
2. Wav2Lip-ONNX 性能优化或 CUDA 机器验证。
3. 有 NVIDIA/CUDA 机器后再评估 SadTalker/MuseTalk。
4. 模板、历史版本、项目列表、完整 Composer 和更多媒体 Provider。

## P6D 安装基线（已完成 2026-07-25）

**目标**：新电脑可按 `INSTALL.md` 一键安装并启停，无须依赖当前机器的隐式环境。

**已完成：**

- `backend/.venv` 已创建（pip 26.1.2），装好 13 个核心包 + 5 个 Wav2Lip 可选依赖。
- `INSTALL.md` 6 节：前置 / 一键安装 / 启动停止 / 验证 / 端口冲突 / 模型与外部 Provider / 故障排查。
- `scripts/bootstrap.cmd` 一键安装（venv + pip + .env.example → .env + npm install + compileall + npm build，19 秒跑通）。
- `scripts/start_backend.cmd` / `start_frontend.cmd` / `stop_backend.cmd` / `status.cmd` 全部跑通。
- `backend/.env.example` 加 8 段注释（Stock / Freesound / Provider Secret / LLM / TTS / Avatar / Pollinations）。

**关键坑（已写入踩坑日志）：**

1. `spawnSync('npm.cmd', [...], {shell:false})` 在 Windows 返回 `status:null`。bootstrap.js 自动给 .cmd/.bat 加 shell:true。
2. PowerShell 内置 `$PID` 只读变量被赋值抛错。脚本里所有 `$pid` → `$procId` 改名。

**验证命令：**

```powershell
cd D:\workspace\Fliki视频制作还原
scripts\bootstrap.cmd        # 一键安装 (venv+pip+npm+compileall+build)
scripts\start_backend.cmd    # 后端 http://127.0.0.1:5181
scripts\start_frontend.cmd   # 前端 dev http://127.0.0.1:5180
scripts\status.cmd           # 端口 + pidfile + /health
scripts\stop_backend.cmd     # Stop-Process by pidfile + port 5181 fallback
```

---

## 后续实施计划


### P5D-5：Avatar 前端接入

**目标**：用户在创建/编辑场景草稿时，可以选声音和 Avatar；确认后 Avatar 选择进入工作流。

实施项：

- 复用 Voice Gallery 的选择回传机制，补 Avatar 列表和预览。
- 草稿场景增加 `avatar` 字段，格式固定为 `avatar:<uuid>`。
- 确认快照保留 Avatar 字段；workflow pipeline 将其传到 Avatar 节点。
- Env-Check 页面显示模型是否存在、依赖是否完整、是否会走静态回退。
- 增加“未配置模型时仍能生成静态 Avatar MP4”的前端提示。

验收：

- 不确认草稿时，Avatar Provider 不被调用。
- 确认后可看到 Avatar 节点状态。
- 缺模型时任务不崩溃，明确显示 fallback。

### P5E：Provider 密钥持久化（已完成）

**目标**：用户可以在本机配置 Provider，重启后仍然有效，且前端永远看不到明文密钥。

已完成：

- `persist=true/false` 明确区分本地持久化与当前进程临时注入。
- 密钥写入独立 managed 段，不进入 SQLite，响应只返回掩码。
- 启动 hydrate、DELETE 清除、Docker secrets 卷与 0600 权限已验证。
- 宿主与 Docker 镜像内全量测试均为 `152/152`。

### P5D-7：部署与交接基线

**目标**：新电脑可以按清单启动，而不是依赖当前机器的隐式环境。

实施项：

- 固定 Python 版本并建立项目 `.venv`。
- 增加 Windows 启动/停止脚本和端口检查。
- 真运行 `docker compose up` 并记录结果；若 Docker 的 Remotion/Chrome 不稳定，保留本机系统 Chrome 路径为默认方案。
- 编写 `INSTALL.md`，只写已验证命令。
- 用户确认后创建首次 Git 基线提交；提交前清理或明确保留历史辅助脚本、旧日志和旧 DOCX。

### P5D-8：本地 AI 能力

**目标**：在不抬高当前电脑门槛的前提下增加可选数字人和克隆声音。

实施顺序：

1. Wav2Lip-ONNX：已完成模型文件、可选依赖、中文路径兼容和低分辨率短视频 CPU 真机测试；约 2 秒音频在当前 CPU 用时 73.116 秒，且 `fallback_used=false`。
2. GPT-SoVITS：继续作为 HTTP 客户端；服务可在本机或局域网另一台机器运行。
3. SadTalker/MuseTalk：仅在有 NVIDIA/CUDA 机器或兼容远程 API 时进入候选。

## 推荐执行顺序（按 ROI）

1. ~~核对 MiniMax key~~ ✅（正确域名 `api.minimaxi.com`，TTS + Music 真机通）。
2. ~~P7-3 MiniMax Image Provider~~ ✅（image-01 真机 36.8 秒 1280×720）。
3. ~~P7-4 MiniMax Video Provider~~ ✅（Hailuo-2.3 真机 submit 通，task_id 拿到）。
4. ~~前端暴露 MiniMax~~ ✅（ProviderKeyManager 动态渲染 + env-check.html 4 面板自动展示）。
5. **统一 README**（INSTALL + HANDOFF + PROJECT_STATUS 三份去重）。
6. **Composer / 模板库**。
2. 统一 README（INSTALL + HANDOFF + PROJECT_STATUS 三份去重 / 合并）。
3. Composer / 模板库（前端拖拽时间线 + 场景模板）。
4. P5D-8：GPT-SoVITS 外部联调（用户换电脑后评估，或保留 VoxCPM2 作为更现代的本地继任者）。
5. SadTalker/MuseTalk/VoxCPM2（仅在有 NVIDIA/CUDA 时评估）。

## 不要做的事

- 不要重新抓 `app.fliki.ai`，除非出现明确的新功能缺口。
- 不要把截图作为结构或功能事实来源。
- 不要在当前 Intel/无 CUDA 机器上默认引入 SadTalker/MuseTalk 重模型。
- 不要在草稿确认之前调用付费或高算力 Provider。
- 不要把用户 API Key 写入文档、测试、前端 bundle 或 Git。
- 不要把 Mock 测试结果写成真实外部 API 已验证。

## 复用命令

```powershell
cd D:\workspace\Fliki视频制作还原\backend
python -m unittest discover -s tests -q
python -m compileall -q .

cd D:\workspace\Fliki视频制作还原\app
npm.cmd run build
```

## 文档状态

- 当前移交主文档：`D:\workspace\Fliki视频制作还原\HANDOFF.md`
- 当前状态计划：`D:\workspace\Fliki视频制作还原\PROJECT_STATUS_AND_PLAN.md`
- 规则：`D:\workspace\规矩文档.txt`
- 历史踩坑：`D:\workspace\踩坑日志.txt`
- 本次只更新上述两份 Markdown，没有修改源码、测试、抓取资料、API Key 或旧版 DOCX。


## 2026-07-26 本机承载优化增量

- Wav2Lip-ONNX 已用 GWen 真人脸和本地 MP3 真推理成功：CPUExecutionProvider、无 fallback，2.2 秒音频约 33 秒完成，输出 1080×1080 H.264/AAC。
- 本机定位为 8 逻辑核、15.8GB 内存、Intel Iris Xe、无 CUDA；数字人口型适合短片段串行生成，不适合并行或高分辨率长片批量推理。
- `/env-check/quick` 已拆成纯本地检查，不再运行外部 Provider 网络探测；接口实测约 2.8 秒（GPU 单项约 0.35 秒）。
- 完整环境检查明确跳过 MiniMax 视频提交，防止消耗每日 3 次额度；未经用户明确授权不发起视频生成。
- `autoedit_runs.output_path` 已加入 schema 和启动迁移，旧库重启后自动补列；旧成功记录仍通过 `render_job_id` 兼容返回。
- 验证：前端生产构建通过；Python 全量 unittest 310/310 通过；关键 Python 文件语法检查通过。
- 本机下一阶段最高 ROI：将 Wav2Lip 真输出接入 workflow 的 avatar 场景合成；按 2–6 秒切段串行推理并缓存；随后做一条纯本地 stock+TTS+avatar+Remotion 的完整回归。


## 2026-07-27 Avatar 分段接入与本地完整闭环

- 已将工作流 Avatar 节点改为 2–6 秒串行 Wav2Lip-ONNX 分段推理，并按内容哈希缓存。
- 已验证 6.144 秒本地语音拆为 2 段，均为真 ONNX、无 fallback；二次运行命中缓存。
- 已完成本地 Stock + Edge TTS + Avatar + Remotion 闭环，产物位于 `backend/data/output/local_e2e/local_e2e.mp4`。
- 本机建议继续保持 concurrency=1；下一步可把真实 Pexels/Pixabay 本地下载资产接入同一回归脚本。


## 2026-07-27 D:\下载 ZIP 技能包审计

- 完成 D:\下载 内 27 个压缩包静态审计；产出 `docs/DOWNLOAD_AUDIT.md`（8.4KB）。
- 三个高价值包：Pixelle-Video (Apache-2.0)、MoneyPrinterTurbo (MIT)、hyperframes (Apache-2.0)。
- 直接可复用：Edge TTS 列表、视频宽高比枚举、VideoTransitionMode、文件安全工具、BGM 启用判定、HyperFrames SKILL 文档、registry 模板示例。
- 不应使用：MoviePy 全栈、ComfyUI/Streamlit WebUI、Bun/Node 22 工程化、OmniVoice AGPL 代码并入、任何触发付费视频 API 的依赖。
- 下一步：把 VideoAspect/VideoTransitionMode 接入 scene_drafts，添加文件安全模块，撰写 motion-doctrine.md 作为 Remotion 模板说明。


## 2026-07-27 Web/HTML 页面审计

- 完成 4 套前端审计（Pixelle HTML 帧、HyperFrames 模板、blcaptain Next.js、MoneyPrinterTurbo 占位 HTML）。
- 产出 `docs/DOWNLOAD_WEB_AUDIT.md`（6.4KB）。
- 直接可复用：design tokens、三栏布局、状态色、字幕 display/spoken 分层、模板元数据。
- 不应使用：外部 CDN、Google Fonts、Streamlit、Next.js 全套、Bun 工程化、AGPL 包。
- 下一步：5 项立刻落地 → styles/app.css 增加 design tokens、HomePage 三栏布局、Subtitle 双轨字段、scene_drafts media_width/height、docs/motion-doctrine.md。


## 2026-07-27 HANDOVER_NEXT 交接

- 产出 HANDOVER_NEXT.md（10KB），作为本轮对话完整交接快查。
- 接手顺序: HANDOVER_NEXT.md → PROJECT_STATUS_AND_PLAN.md → HANDOFF.md → 规矩文档 → 踩坑日志。
- P0 起步: 统一 README + 合并三份文档 + 更新 docs/motion-doctrine.md。
- 后端 313 测试全绿，前端构建 OK；后端 5181 (PID 30144) 在跑。


### 2026-07-27 转场补验收
- slide-right / slide-down 已完成真实 Remotion 渲染与密集抽帧肉眼验收。
- 产物：`backend/data/output/v2_e2e_right_down/v2_e2e_right_down/v2_e2e_right_down.mp4`，1280x720，12.05s，6.15MB，h264+aac 30fps。
- 验收图：`backend/data/output/v2_e2e_right_down/frames/contact-right.jpg`、`contact-down.jpg`。


### 2026-07-27 Composer 真实模板接入
- Composer 从后端 `/templates` 加载 5 套真实模板和分类，不再只是展示静态卡片。
- 可选择目标场景并一键套用，自动补齐必填模板字段后持久化；Composer 元数据修改也直接保存。
- 修正前端默认 API 端口 8001 → 5181；浏览器验证模板 PATCH 200，前端构建通过，模板测试 47/47。
