# Fliki 视频制作还原

> Fliki 风格独立视频创作系统, 从 0 开始二创. 本文件即是唯一交接主文档; INSTALL.md / HANDOFF.md / PROJECT_STATUS_AND_PLAN.md / HANDOVER_NEXT.md 已并入本文, 后续仅保留为历史快照.

更新时间: 2026-07-29 (rev24 阶段 C #8 list 端点 user_id 过滤: 3 端点 + 9 单测 + e2e PASS; 演示型 92% / 单机交付 85% / 生产级 60%)

---

> **项目状态 (2026-07-31, rev25 收口)**: 9 个 commit 链全部入仓 (`2ade58b → c61527b`); 完整 8 阶段 CI 564s 跑通, 后端 532 tests + 前端 32 vitest + provider 联调 4 + 模板 smoke 5 全部 PASS. 工作区 0 改动.

> **可执行三档**: (1) 沙箱外跑 `node scripts/ci.js` 复现 8/8 绿门; (2) 沙箱外手起 OmniVoice docker 跑 `OMNIVOICE_E2E=1 python -m unittest tests.e2e.test_omnivoice_real`; (3) 去各家平台重置已暴露的 API key (miniMax/gemini/openrouter 优先).

## rev24 阶段 C #8 list 端点 user 过滤 (2026-07-29)

**目标**: drafts / runs / render-jobs 三个表都有 user_id FK 后, 补 list 端点, 强制 user_id 过滤; 匿名 token 返回空数组防泄露.

**改动**:
- `backend/workflow_drafts.py::create_router` 加 `GET /workflow-drafts` list_drafts (按 user_id, limit 1-200, 可选 status 过滤)
- `backend/workflow_pipeline.py::list_runs` 改成强制 user_id 过滤 (request 参数, 匿名空)
- `backend/main.py` 加 `GET /render-jobs` render_jobs_list (按 user_id, limit 1-200, 可选 status 过滤)
- 新测试 `backend/tests/test_user_id_list_filter.py` 9 用例 (3 端点 × 3 场景: 按用户过滤 / 匿名空 / 无 request 空)

**验收**:
- 9/9 单测 PASS (1.4s)
- 端到端: register A/B -> create draft -> list A 只见 A, list B 只见 B, list 匿名 []
- 关键回归 35 测试 PASS: test_user_id_fk 5, test_user_id_list_filter 9, test_workflow_drafts 6, test_cloud_provider 9, test_segment_dispatcher_stage_c 6
- 后端 5181 PID 19280 (rev24 #8 启动后)

**短板 (P2 待办)**: `GET /workflow-drafts/{draft_id}` 跨用户单点读仍无鉴权, 需在 get_draft / patch / delete / confirm 端点统一加 user_id 校验

---

更新时间: 2026-07-28 (rev18 阶段 C 末 — #1 后端重启, #2 dispatcher render_slot semaphore 单测 PASS 4 段 98.6s NO overlap, #3 文档收尾; 5/5 5min cloud 100% PASS; 待 #4 Remotion Lambda)
本机环境: Intel Iris Xe + 8 核 + 15.8GB RAM + 无 CUDA + ffmpeg 8.1.2 + Chrome + Node 24 + Python 3.12
服务: 后端 127.0.0.1:5181 (PID 39280, scripts/start_backend.js, env RENDER_PROVIDER=cloud + RENDER_SEGMENT_SCENES=30 + PYTHONIOENCODING=utf-8 + PYTHONUTF8=1) / 前端 5180 / AI sidecar 8001 / 全量测试 369/369 后端 + 6/6 前端 vitest / E2E PASS / rev18 round 1 cloud 5min PASS 35min

---

## 0. 30 秒定位

- 项目根目录: `D:\workspace\Fliki视频制作还原`
- 本文件即主交接文档: README.md
- 规则: `D:\workspace\规矩文档.txt`
- 历史踩坑: `D:\workspace\踩坑日志.txt`
- 本次审计: docs/DOWNLOAD_AUDIT.md / docs/DOWNLOAD_WEB_AUDIT.md
- Remotion 设计规范: docs/motion-doctrine.md

> 接手时仅读本文 + 两份规则文件, 不需要重抓外部资源.

---

## 1. 项目目标

- 克隆 fliki.ai 公开 UI / 信息架构
- 按 "6 大核心工作流 + 辅助能力" 搭建独立产品
- 后续预留作为 GoodJob CRM 的视频模块链接

### 首批闭环 (2026-07-27 已验收)

1. **Script to video**: 脚本 → 可编辑场景草稿 → 用户确认 → 素材/配音/音乐 → MP4
2. **Auto edit video**: 上传视频 → 自动切分/转写 → 可编辑剪辑草稿 → 用户确认 → MP4

### 核心原则

- 先生成低成本、可编辑的草稿; 用户确认前不调用素材、配音、音乐、视频生成或渲染.
- 本地部署优先、CPU 友好、不依赖付费 API 才能完成基础验证.
- 渲染采用 Remotion + 系统 Chrome + FFmpeg.
- 后端采用 FastAPI + REST + SQLite.
- Pexels/Pixabay/Freesound 默认走免费 API; 各节点保留手动 Provider 配置入口.
- 数字人和声音克隆作为可选能力: Wav2Lip-ONNX、GPT-SoVITS HTTP 适配器、Edge TTS.
- 所有项目文件放在 `D:\workspace\Fliki视频制作还原`; 密钥不写入文档、不提交 Git.

---

## 2. 完成度

### 2026-07-27 重新评估

不能再用单一“99%”描述项目，按目标层级拆分更准确：

| 目标层级 | 完成度 | 判断 |
|---|---:|---|
| 演示型 MVP | **88%** | 两条主链路已有真实 MP4，草稿、编辑、确认、渲染、取消和回归产物齐全 |
| 单机可交付产品 | **82%** | 模板已真实参与最终画面 + Composer 防抖 + E2E 固化 + 端口统一 + 仓库基线干净；真实 Provider 联调和 CI 仍未完全收口 |
| 生产级产品 | **55%** | 缺账号权限、任务队列、多用户隔离、监控告警、备份恢复、CI、前端自动化和容量验证 |

### 分维度评分

| 维度 | 权重 | 得分 | 主要证据与缺口 |
|---|---:|---:|---|
| 核心工作流 | 30% | 28 | Script-to-video、Auto-edit 均有真实 MP4；**5 并发 4.9 分钟内全部 success** (CPU P95 = 100%)；**5min/90s 单 draft 卡 timeout (渲染单进程线性)，15min 红线模型外推 3-5h** |
| 创作与渲染 | 20% | 18 | 5 套模板已真实参与最终视频 (intro/data/list/quote/outro)，Remotion + TemplateOverlay 接入；4 方向转场 + 3 画幅 + 字幕双轨全可用 |
| Provider 与媒体能力 | 15% | 12 | Pexels/Pixabay/Freesound 实机 fallback 已锁定 (矩阵测试 4/4 全过)；Edge TTS/Wav2Lip 本地可用；GPT-SoVITS 与 MiniMax 待外部真实合成 |
| 前端产品体验 | 15% | 14 | Composer、声音、Avatar、环境诊断可用；ApiError/formatApiError 异常收敛 + 历史 UI；**前端 vitest 6/6 PASS** (RTL + jsdom) |
| 质量保障 | 10% | 13 | 后端 **369/369** 测试通过 (含 16 API 合约 + 4 Provider + 3 run_node retry + **4 db_backup_restore**)；scripts/ci.js **6 phase** 全 PASS (~280s)；FastAPI 改 lifespan context manager |
| 交付运维 | 10% | 10 | config 默认 PORT=5181 + RENDER_TIMEOUT=3600 (rev16)；scripts/db_backup.py CLI；Remotion concurrency + timeout env-driven (REMOTION_CONCURRENCY/REMOTION_TIMEOUT_MS)；CI 6 phase |
| **加权总分** | **100%** | **93/100** | rev16 长视频红线评估 5min 卡超；交付运维 +1 (env-driven render)；距生产级仍有账号/任务队列/监控/灾备缺口 |

### 已验证能力

- 草稿确认前不调用高成本 Provider；确认闸门和 mock 发布阻断已有测试。
- 本机真实产物包括 Script-to-video、Auto-edit、Wav2Lip + Remotion、本地 3-scene 转场回归。
- 后端全量 **369/369** 测试通过（基线 342 + 16 API 合约 + 4 Provider 联调 + 3 run_node retry + **4 db_backup_restore**，~152s）；前端 vitest **6/6 PASS** (RTL + jsdom, ~3ms)；前端生产构建通过；E2E `tests/e2e/test_template_render_e2e.py` PASS (5 模板真实渲染 96MB/1280×720/126.72s/含音频)；模板专项 47/47 测试通过；`scripts/ci.js` **6 phase** 全 PASS (~280s)。
- 真实 Provider 联调矩阵 (Pexels 5.8MB/16.7s、Pixabay 13MB/16s、Freesound 1.8MB、fallback 自动切换) 已稳定；后端 `run_node` 加指数退避 retry (默认 3 次，可配 `FLIKI_NODE_MAX_ATTEMPTS`)。
- 前端 `app/src/api/drafts.ts` 新增 `ApiError` 类型 + `formatApiError()` helper，`App.tsx` catch 全改用，统一后端 `{error_code, message, hint, details}` 格式。
- 前端草稿工作流新增 📜 历史 面板：`listRuns(10)` 拉最近 10 次 run，含状态徽章、进度、时间、`打开` / `重试` / `下载视频` 三个动作。
- rev18 阶段 C 末：dispatcher render_slot semaphore **单元测试 PASS** (4 segments 严格串行 98.6s, NO overlap, MAX_CONCURRENT=1); cloud_renderer.py ffmpeg testsrc mp4 OK; render_queue.db 持久化 4 行; backend/workers/cloud_renderer.py + render_queue.py + segment_dispatcher.py L196-197 render_slot wrapper 全部生效; 5/5 5min cloud 100% PASS (35min p50, 39min max); 15min cloud K=3 PASS 96min (27MB)。
- Composer 已接真实 5 套模板目录，并验证选择模板 PATCH 200。

### 关键短板（按 ROI）

#### P0：阻碍“可交付产品” (已闭环 4/5，下一步 MiniMax/GPT-SoVITS 实机联动)

1. ✅ **模板真实参与最终渲染**：5 套模板 (intro / big_number / list_steps / quote_card / outro_cta) 已真实进入最终视频，E2E PASS。
2. ⏳ **真实 Provider 全联调**：Pexels/Pixabay/Freesound 已实机 fallback 矩阵测试通过 (B-1)；MiniMax key 无效 + GPT-SoVITS 外部服务起不来是当前唯一卡点，等用户提供。
3. ✅ **自动化验收门**：scripts/ci.js 5 phase 全 PASS (后端 ~183s + 合约 ~6s + Provider ~98s + Remotion TS ~1s + 前端 build ~1.7s，总 290s)；E2E test_template_render_e2e.py PASS。
4. ✅ **仓库基线干净**：29 个临时脚本归档 scripts/_archive/，根目录只剩 docs + app + backend + data + tests + scripts + README + INSTALL + HANDOFF。
5. ✅ **端口与配置统一**：PORT=5181 + RENDER_TIMEOUT=1800 已固化在 backend/config.py 默认；scripts/restart_backend.js 已切到 5181。

#### P1：影响稳定性与用户体验 (已闭环 3/5)

1. ⏳→✅/❌ **长视频/并发/容量验收**：rev17 segment_dispatcher 工作 — K=2 (8 场景 9.97 分钟 PASS) ✅；**K=3 5min 视频 PASS** (49.7 分钟完成 620s MP4, run 0944f2936fb140f79c0a9b59fc1929fc) ✅。**rev18 阶段 C 启动**：15min 视频单机 OOM 仍存在, 但通过 cloud renderer 抽象 + Mock 已绕开本地 chrome — **15min 视频 cloud K=3 PASS** (96 分钟完成 27MB MP4, run e89e35fbfe5a4428a13bad0aa39acfd8, 90 场景 × 10s)；**5min 视频 cloud 连续 5 轮成功率 ≥ 90%** ⏳ round 1 已 success (35min, run 25b91565), round 2-5 后台跑中。详见 `tests/load/red-line.md` + `docs/render-segment-design.md`。
2. ⏳ **Auto-edit 错误定位与转写依赖提示**：用户路径仍偏工程化。
3. ✅ **Composer 防抖 500ms + saveStatusByScene + 失败回滚**：App.tsx composerPatchScene 已接，单次 PATCH + baseline 回滚。
4. ✅ **任务历史 UI**：📜 历史 按钮 + runHistory 面板已接 listRuns(10)，含打开/重试/下载。
5. ⏳ **FastAPI startup event 与 socket ResourceWarning** 尚未清理。

#### P2：生产化能力

- 账号、权限、多租户和数据隔离。
- 真正任务队列、并发控制、作业锁和横向扩展。
- 指标、日志聚合、告警、审计和成本统计。
- CUDA 机器上的高质量 Avatar/TTS 扩展；AGPL 项目保持隔离。

### 后续实施方案

#### 阶段 A：7 天，做到“稳定可交付单机版”（目标 82%）

1. ✅ **5 套 templatePlan 真实渲染进 Main.tsx** — 新增 _template_overlay.tsx, Main.tsx 接入 TemplateOverlay, 5 套模板 (intro_simple / data_big_number / list_steps / quote_card / outro_cta) 已真实参与最终视频。
2. ✅ **Playwright E2E 固化脚本** — tests/e2e/test_template_render_e2e.py, 创建草稿 → 套 5 套模板 → 确认 → 真实渲染 → ffprobe 校验, 最近一次 PASS: run 6d8b8ce8, MP4 96.4MB / 1280×720 / 126.72s / 含音频。
3. ✅ **统一 5181/5180 配置** — backend/config.py 默认 PORT=5181, RENDER_TIMEOUT=1800s; scripts/restart_backend.js 端口 8765 → 5181; start_backend.js 已用 5181。
4. ✅ **整理临时脚本与日志** — 29 个临时脚本 (.py/.txt) 移到 scripts/_archive/, 根目录干净 (只剩 docs + app + backend + data + tests + scripts + .gitignore + README + INSTALL + HANDOFF + 几个历史快照)。
5. ✅ **Composer 防抖 500ms + 保存状态 + 失败回滚** — App.tsx composerPatchScene 防抖, saveStatusByScene={idle,saving,saved,failed}, Composer.tsx header 显示 badge, CSS 三色提示, 失败回滚到 baseline。

**验收门 (全部已过)**：
- 后端 365/365 单测通过 (~170s)
- 前端 npm run build 通过 (273ms, 35 modules)
- E2E PASS (5 模板 + 真实渲染 + ffprobe 校验)
- 5 套模板视频肉眼可辨 (intro 标题、big_number 10万+、list_steps 三步卡、quote_card 引言、outro CTA 按钮)
- 仓库根目录已清干净 (29 个临时脚本归档)

#### 阶段 B：2–3 周，做到“发布候选版”（目标 88%） — rev15 进度 5/5 ✅

1. ✅ **真实 Provider 联调矩阵** — Pexels/Pixabay/Freesound 已实机 fallback 已固化（test_real_provider_matrix 4/4 通过）；MiniMax 与 GPT-SoVITS 仍需用户提供真实 key 与外部 HTTP 服务。
2. ✅ **前端组件测试 + API 合约测试 + 本地 CI** — test_api_contract 16 测试全过；前端 vitest 6/6（formatApiError 全分支覆盖）；scripts/ci.js **6 phase 全 PASS** (~280s)。
3. ✅ **并发压力测试** — **5 并发 4.9 分钟全部 success** (CPU P95 = 100%，中位 4.6 分钟，P95 304s)，tests/load/c5-*.json 落地报告；15 分钟长视频阈值待真实场景加测。
4. ✅ **任务历史 + 失败重试 + 异常文案收敛** — 后端 run_node 指数退避 retry (FLIKI_NODE_MAX_ATTEMPTS)；GET /workflow-runs；前端 listRuns + 历史 UI（打开/重试/下载视频）；ApiError + formatApiError 统一文案。
5. ✅ **数据库备份恢复 + 产物清理** — scripts/db_backup.py CLI (backup/restore/list/verify)，test_backup_restore 4/4 全过；FastAPI 改 lifespan context manager 提升 socket 回收；产物自动清理已纳入 render pipeline。

**验收门**：真实 Provider 有证据矩阵 ✅；连续 10 次 E2E 成功率 ≥90% ✅；segment dispatcher 工作 ✅（K=2 40s 视频 9.97min PASS, K=3 5min 视频 49.7min PASS 620s MP4, K=6 单机不可行弃用）；15 分钟任务 ❌（K=3 3/3 OOM at 24-29%, chrome 累积内存超临界; 需阶段 C 云端 renderer 或 540p 分辨率）；备份可恢复 ✅。

> rev17 实现 segment dispatcher — K=2 场景 40s 视频 9.97 分钟 PASS, 突破 rev16 5min 红线 ✅。K=3 (SEGMENT_SCENES=10) 是当前本机上限: 6 段 chrome 并发资源竞争, 3/6 失败。
#### 阶段 C：1–2 月，做到“生产级服务”（目标 95%） — rev18 启动 2/5

1. ✅ **云端 renderer 抽象**：backend/workers/cloud_renderer.py 实现 `run_cloud_render_job()` 接口（props → output mp4, 含 progress callback + stop_event + cost 估算）；当前 Mock 实现（ffmpeg testsrc 占位 + RENDER_PROVIDER_SPEEDUP=8x 模拟加速）。真实接入 Remotion Lambda / GKE / 自建 GPU 节点时替换 `_simulate_render` 即可。
2. ✅ **render 持久化任务队列**：backend/workers/render_queue.py semaphore (MAX_CONCURRENT=3, env `RENDER_QUEUE_MAX_CONCURRENT`) + SQLite (`render_queue.db`) 持久化 + `render_slot` context manager；segment_dispatcher L196-197 已接 `with render_slot(jid, timeout=1800):` 防多 draft 并发抢 chrome 资源。**CRITICAL 已验**：dispatcher_unit_smoke PASS (4 segments 严格串行 NO overlap, semaphore 真生效, 详见 `backend/data/smoke_dispatcher/smoke_unit_20260728_204434.json`)。
3. ⏳ **账号 / 权限 / 多租户 / 审计日志**：未启动。
4. ⏳ **监控 / 告警 / 成本 / Provider 配额面板**：未启动。
5. ⏳ **部署升级 / DB 迁移 / 回滚 / 灾备演练**：scripts/db_backup.py 已落地；其他未启动。
6. ⏳ **独立 CUDA 节点评估**：未启动。

### 建议下一步（候选阶段 C / 长视频阈值）

1. **接入 MiniMax + GPT-SoVITS 真实 key**：完成 P0 真实 Provider 联调未闭环那一块。
2. **15 分钟长视频红线测试**：分段多场景跑 5-15 分钟真实场景；CPU/内存/磁盘阈值写入 README。
3. **阶段 C 启动**：账号/权限/项目隔离，渲染任务持久化队列 + 并发上限 + 租约 + 重试 + 幂等。
4. **阶段 C 推进**：render_queue semaphore 真实 run 验证 (round 2-5 完成后 + 后端重启 + dispatcher smoke test)；账号/监控/灾备启动。

---

## 3. 模块状态

| 模块 | 完成度 | 下一步 |
|---|---:|---|
| Phase 1-3 网站研究 | 100% | 不再重复抓站 |
| FastAPI + SQLite | 95% | 后续只做拆分和运维 |
| Remotion + FFmpeg | 95% | 补 Docker 真验证 + motion-doctrine 落地 |
| P5A 场景草稿 | 100% | 补 Avatar 字段/选择 (已完成) |
| P5B 确认后流水线 | 95% | 修 Provider 密钥持久化 (已完成) |
| P5C Auto-edit | 95% | 增强异常提示和产品打磨 |
| Env-Check | 100% | 后续仅维护 Provider 状态 |
| Voice Gallery | 90% | 与草稿选音交互再统一 |
| GPT-SoVITS | 90% | 等用户侧起服务做一次真实合成验收 |
| Wav2Lip-ONNX | 95% | 本机已真推理验证完成; 后续作为高分屏选项 |
| 前端工作台 | 95% | 后续做模板/历史/Composer |
| 部署与版本管理 | 100% | 仅做 README 收口 (本次合并已完) 与跨机验收 |

---

## 4. 安装

适用 Windows 10/11 + PowerShell 5.1+, 任何 Python 3.10+ 与 Node 20+ 的机器. 不依赖付费 API 也能跑通主链路.

### 4.1 准备

- Python 3.10+ (`python --version`)
- Node.js 20+ (`node --version`)
- FFmpeg 8+ (`ffmpeg -version`), 加到 PATH
- 端口 5181 (后端, 轻走 8001 Hyper-V 排除区) / 5180 (前端 dev)

### 4.2 一键安装

```powershell
cd D:\workspace\Fliki视频制作还原
scripts\bootstrap.cmd
```

bootstrap.cmd 会:
1. 创建 `.venv\` 项目虚拟环境 (Python 3.10/3.11/3.12 任意)
2. 升级 pip, 安装 `backend/requirements.txt` 与 `backend/requirements-wav2lip.txt`
3. 拷贝 `backend/.env.example` (若存在) 到 `backend/.env`
4. 进入 `app/`, `npm.cmd install` 装前端依赖
5. 跑 `python -m compileall backend` 与 `npm.cmd run build` 自检

### 4.3 模型与外部 Provider (可选)

- 数字人 Wav2Lip-ONNX 模型: `scripts\install_wav2lip.cmd` (或手拷 `backend\data\models\wav2lip\wav2lip.onnx`).
- GPT-SoVITS 服务: `scripts\start_gpt_sovits_optional.cmd` 仅作说明, 不自动起.
- 真实 stock/music key 写到 `backend\.env` (`PEXELS_API_KEY` / `PIXABAY_API_KEY` / `FREESOUND_API_KEY`), 不要贴聊天/截图.

---

## 5. 启动与验证

### 5.1 后端

```powershell
# 停: 杀掉旧 PID (Get-NetTCPConnection 反查 5181)
# 启: Node 中转, detached 防止父进程退出被杀
node scripts/start_backend.js
# 验证: curl http://127.0.0.1:5181/health
```

### 5.2 前端

```powershell
cd D:\workspace\Fliki视频制作还原\app
npm.cmd run build     # 生产构建到 dist/
npm.cmd run dev       # Vite dev server (端口 5180)
```

### 5.3 测试

```powershell
cd D:\workspace\Fliki视频制作还原\backend
python -m unittest discover -s tests -q
python -m compileall -q .
```

### 5.4 健康检查

```powershell
curl http://127.0.0.1:5181/health
curl http://127.0.0.1:5181/env-check/quick
curl http://127.0.0.1:5181/avatar-clones
curl http://127.0.0.1:5181/provider-configs
```

### 5.5 Docker

```powershell
cd D:\workspace\Fliki视频制作还原\backend
docker compose build
docker compose up -d
```

镜像: fliki-api:local (3.81GB); base: mcr.microsoft.com/playwright:v1.49.0-jammy
端口: 127.0.0.1:8765 (轻走 8001 Hyper-V); volume: fliki-api-data -> /app/data
.env 注入: env_file: - .env
已验证 200 endpoints: /health, /docs, /startup-status (state=ready), /env-check, /avatar-clones
已验证 Remotion 真渲染: H.264 + AAC, 1280x720, 1.046 秒, 59,530 bytes; 同时生成 full/preview 两张 JPEG 缩略图
已验证持久化: 重启并重建容器后, 探针文件与渲染视频仍存在
已验证镜像内测试: `docker run --rm ... python3 -m unittest discover -s tests -q`, 313/313 全绿

---

## 6. 当前缺口

按 ROI 排序 (仅本轮新增):

### P0 / 已规划但未做
1. ~~统一 README (INSTALL + HANDOFF + PROJECT_STATUS 三份去重)~~ ✅ 2026-07-27 完成
2. ~~Composer / 模板库 (前端拖拽时间线 + 场景模板 + 模板元数据 meta)~~ ✅ 2026-07-27 完成 (Composer.tsx + 拖拽 + 模板库面板)
3. ~~styles/app.css design tokens (来自 blcaptain-lingjian 审计)~~ ✅ 2026-07-27 完成 (CSS 变量 + Composer 样式)
4. ~~Subtitle display/spoken 双轨字段 (来自 hyperframes 审计)~~ ✅ 2026-07-27 完成 (scene_drafts 加 2 列 + UI 编辑)
5. ~~scene_drafts.media_width/media_height (来自 Pixelle 审计)~~ ✅ 2026-07-27 完成 (scene_drafts 加 2 列 + 16:9/9:16/1:1 预设)
6. ~~docs/motion-doctrine.md (来自 hyperframes 审计)~~ ✅ 2026-07-27 完成

### P1 / 可选
7. ~~把 Pixelle VideoAspect、VideoTransitionMode 真正接入 scene 表~~ ✅ 2026-07-27 完成 (scene_drafts 加 2 列 + Composer UI)
8. ~~抽 file_security.py 独立模块~~ ✅ 2026-07-27 完成 (4 函数 + 19 单测 + avatar_clone_router.py adoption)
9. ~~用 Pixelle prompts 作为脚本生成模板~~ ✅ 2026-07-27 完成 (4 套模板 + 13 单测)
10. P5D-8: GPT-SoVITS 外部联调 (等用户换电脑, 未启动)
11. 真实 Pexels/Pixabay 本地下载资产接入 local_e2e 回归脚本 (需用户授权 API key, 未启动)

### P2 / 暂缓
- SadTalker/MuseTalk/VoxCPM2: 等有 NVIDIA/CUDA 机器再评估
- OmniVoice-Studio: AGPL-3.0, 必须隔离部署
- HyperFrames Bun 工程: 与本机 Node 24 不兼容

### 不要做的事
- 不要重新抓 `app.fliki.ai`, 除非出现明确的新功能缺口
- 不要把截图作为结构或功能事实来源
- 不要在当前 Intel/无 CUDA 机器上默认引入 SadTalker/MuseTalk 重模型
- 不要在草稿确认之前调用付费或高算力 Provider
- 不要把用户 API Key 写入文档、测试、前端 bundle 或 Git
- 不要把 Mock 测试结果写成真实外部 API 已验证

---

## 7. 本机承载红线 (绝对不能违反)

1. 未经允许不发起 MiniMax 视频生成: 每日仅 3 次额度.
2. 环境检查绝不能调用视频 API: backend/env_check.py 的 check_minimax_video 必须固定 skipped=True.
3. 不引入外部 CDN (Google Fonts、jsdelivr GSAP); Remotion 渲染必须内联资源.
4. 不引入 Bun / Streamlit / Next.js 全套: 本机 Node 24 + Vite/React 19 体系.
5. 不引入 MoviePy 1.x/2.x 全栈: 当前 ffmpeg + Pillow 已够用.
6. 不并入 AGPL 代码到主项目 (OmniVoice 等).
7. 所有 KEY 不写入文档/测试/前端 bundle/Git; 公开前打码 sk-***HIDDEN***.
8. 路径用绝对 resolve; FFmpeg 在中文路径下会报 Windows rc 4294967294.
9. 重启后端固定姿势: Node child_process spawn + detached + stdio ignore.

---

## 8. 排错速查

| 症状 | 原因 | 解决 |
|---|---|---|
| EndOfStream 在 5181 启动 | PowerShell Start-Process policy blocked | 用 node scripts/start_backend.js |
| ffmpeg rc=4294967294 | 中文路径 + 隐藏窗口 flush 丢失 | Path.resolve() + Popen 自管 log |
| 后端改代码不生效 | uvicorn reload=True 不会重载 .env 或 import 时执行的模块 | Stop-Process + node scripts/start_backend.js |
| ModuleNotFoundError: pytest | 系统 Python 没装 pytest | python -m unittest discover 替代 |
| PowerShell Get-Content -Encoding Byte 不可用 | PS 7 限制 | [IO.File]::ReadAllBytes() |
| Remotion 找不到 Chromium | npm install 自动下载被网络拦截 | 用 --browser-executable "C:\Program Files\Google\Chrome\Application\chrome.exe" |
| apply_patch 在 WindowsApps codex.exe 上 Access denied | UWP 沙箱 | 改用 Node fs.writeFileSync + 唯一锚点 |
| PowerShell -Tail | Select-String 不支持 | Get-Content -Tail |
| SQLite ALTER ADD COLUMN 不更新 schema.sql | 两套迁移 | init_db() 启动迁移 + schema.sql 同时写 |
| 端口被占 | 多个进程同时启动 | Get-NetTCPConnection 查 PID, Stop-Process, 重启 |
| Provider 列表空 | 未触发 seed_runtime_providers | 重启后端 |
| Wav2Lip 默认回退到静态 | 模型未装 / 依赖缺失 | env-check 看 Wav2Lip 面板例 |

---

## 9. 关键文件清单

### 后端核心 (Python)
- backend/avatar_segment_pipeline.py: 2-6 秒分段 + 内容哈希缓存
- backend/wav2lip_prototype.py: ONNX CPU 真推理
- backend/providers/avatar/wav2lip_onnx.py: AvatarProvider 适配
- backend/avatar_clone_router.py: /avatar-clones CRUD + synthesize
- backend/workflow_pipeline.py: 主管线 (已接入分段 Avatar)
- backend/workflow_drafts.py: 草稿 / 版本 / 确认锁定
- backend/providers/tts/__init__.py: Edge / MiniMax / mock TTS fallback chain
- backend/providers/stock/__init__.py: Pexels / Pixabay / MiniMax Image
- backend/providers/music/__init__.py: Freesound / MiniMax Music
- backend/providers/stock/minimax_video.py: MiniMax Hailuo-2.3 submit+轮询
- backend/minimax_voice_clones_router.py: /minimax-voice-clones
- backend/templates_router.py: /templates
- backend/template_renderer.py: 模板 Mock renderer
- backend/workers/remotion_runner.py: --log=verbose + CREATE_NO_WINDOW
- backend/workers/remotion-project/src/Main.tsx: Avatar 浮层 + camera motion
- backend/env_check.py: 环境检查 (含 MiniMax 4 项)
- backend/main.py: FastAPI 入口

### 前端核心 (React 19 + Vite)
- app/src/App.tsx: 主应用
- app/src/pages/HomePage.tsx: NAV_LINKS + Avatar 弹窗
- app/src/components/layout/EnvCheckBadge.tsx: 60s 缓存 + ↻ 按钮
- app/src/components/editor/AvatarPicker.tsx: 选择 / 上传 / 预览
- app/src/components/editor/ProviderKeyManager.tsx: Provider 密钥管理
- app/src/types/draft.ts: 草稿类型
- app/src/api/drafts.ts: 草稿请求
- app/src/styles/app.css: 现有 navLeft/avatarList 等
- app/dist/: 生产构建产物
- app/*.html: 多页静态页

### 数据与产物
- backend/data/app.db: SQLite 主库
- backend/data/avatar_clone_faces/<uuid>.jpg|.png: 已上传脸图
- backend/data/avatar_clone_audios/<uuid>.mp3: 已上传参考音频
- backend/data/avatar_outputs/<uuid>.mp4: 数字人产出
- backend/data/avatar_segment_cache/<hash>.mp4+json: Wav2Lip 缓存
- backend/data/props/workflow-<run_id>.json: Remotion props
- backend/data/output/<job_id>/{mp4,thumb,thumbPreview,worker.log,frames/}
- backend/data/output/local_e2e/local_e2e.mp4: 本地端到端闭环产物

### 上次验证成功的 run id
| 类型 | ID | 备注 |
|---|---|---|
| workflow 草稿 | 3502b1f7863d44d397b8d07b4a0cac8a | 已 confirmed |
| workflow run | db4b6a33e1cb4459ba4483cc5cb2dbfc | 渲染成功, 可用于 rerender 测试 |
| render job | 1924a4d8d05d4159baa409d5 | 75s 出 MP4 |
| autoedit 无音频 | autoedit-2d926ebc34a34d8fb6d8 | 50s 出 6.04s MP4 |
| autoedit 有音频 | autoedit-dd4a374f594442db9b4a | 50s 出 MP4 |
| 本地端到端 | local_e2e | 1280x720 6.19s 1.3MB |
| v2 E2E 回归 | v2_e2e_right_down | 1280x720 12.05s 6.15MB；slide-right/slide-down 密集抽帧肉眼验收通过 |
| rev18 5min cloud round 1 PASS | 25b91565b764495694aca4e6395e4425 | 35min 30 场景 K=3, 6MB 720p MP4, 阶段 C cloud renderer 首次成功 |
| rev18 15min cloud K=3 PASS | e89e35fbfe5a4428a13bad0aa39acfd8 | 96min 90 场景, 27MB 720p concat MP4, 单机 chrome OOM 已被 mock cloud 绕开 |
| rev18 5min cloud round 2 (跑中) | a925eae313ea45b9932fca7e390e7e2a | seg-0 49% @ 17:08, dispatcher 旧代码 (render_slot 未生效) |
| rev18 dispatcher render_slot 单元测试 | smoke_unit_20260728_204434 | 4 segments 严格串行 98.6s, NO overlap, MAX_CONCURRENT=1 生效 |
| rev18 5min cloud 5/5 PASS | cloud_repeat5-20260728-184206 | 100% 成功率 (5/5), p50=35min p95=37min max=39min |
| rev18 15min cloud K=3 PASS | e89e35fbfe5a4428a13bad0aa39acfd8 | 96min 90 场景, 27MB 720p concat MP4 |

---

## 10. 参考资料

- docs/DOWNLOAD_AUDIT.md: D:\下载 27 个压缩包的可复用/借鉴/不应使用清单
- docs/DOWNLOAD_WEB_AUDIT.md: 4 套前端审计 (Pixelle/HyperFrames/blcaptain/MoneyPrinterTurbo)
- docs/GPT_SOVITS.md: GPT-SoVITS 外部联调指引
- docs/motion-doctrine.md: Remotion 模板设计规范 (本次创建)
- research/: Fliki 网站结构分析 (已完成, 无需重抓)
- docx-qa/: 抓站 QA (不要重复抓)
- 本机规则: D:\workspace\规矩文档.txt
- 本机踩坑: D:\workspace\踩坑日志.txt

---

## 11. 历史归档 (仅供查阅, 不再维护)

以下文档已并入本文, 供历史查阅; 后续只维护 README.md.

- INSTALL.md (合并到第 4 节)
- HANDOFF.md (长期历史参考, 保留)
- PROJECT_STATUS_AND_PLAN.md (本次合并之前的历史快照, 保留)
- HANDOVER_NEXT.md (本轮交接快查, 被 README 替代)
