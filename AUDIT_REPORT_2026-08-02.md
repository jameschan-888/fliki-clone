# Fliki 视频制作还原 — 全面工程审计报告

审计日期: 2026-08-02 | 审计基线: git HEAD `489253b` | 审计人: Codex (长期执行型合作者)

---

## 0. 执行摘要 (结论先行)

- **整体交付度: 良好偏上 (可交付演示/试运行, 不建议直接生产)**。代码健康度高: 后端 569 测试全绿、`scripts/ci.js --offline` 强门 7/7、前端构建 + 40 测试全过、132 个 py 文件编译通过、无 TODO/FIXME 残留、SQL 全参数化、路径穿越/密钥/CORS/安全头实测通过。
- **主要短板不在代码, 在"交付工程化"**: 无 git remote (CI 从未真实运行过)、README 过期 30+ commits、依赖清单缺口 (requests/faster_whisper/openai 未入 requirements)、1 个 P1 级工作流断裂 (匿名创建草稿成孤儿)、Docker compose 浏览器路径不一致。
- **P1 共 2 项, P2 共 8 项, P3 共 5 项**; 修复工作量: P1 约 0.5-1 天, P2 约 1-2 天, P3 随开发顺带清理。

---

## 1. 验证方法 (透明执行)

| 维度 | 手段 | 结果 |
|---|---|---|
| 单元/集成测试 | `python -m unittest discover -s tests` (FLIKI_ENV=test + uvicorn 5181 live 组) | 569 OK, 5 skipped |
| 工程强门 | `node scripts/ci.js --offline` | 7/7 OK (279.6s) |
| 前端测试 | `npx vitest run` | 40/40 OK |
| 前端构建 | `npm run build` | OK (506ms) |
| 编译 | py_compile 全量 (排除 .venv/_archive) | 132/132 OK |
| 功能 smoke | OpenAPI 盘点 78 端点 + 40+ 关键路径实测 | 通过 (见 §3) |
| 安全审计 | 路径穿越/CORS/安全头/鉴权/限速实测 + 代码面扫描 | 通过 (见 §4) |
| 静态扫描 | TODO/FIXME、SQL 拼接、裸连接、死代码、密钥入仓 | 见 §5/§6 |

---

## 2. 测试与构建结果 (全绿清单)

- 后端全量 `569 tests OK (skipped=5)` — 与历史基线一致, 无回归; skipped 5 项为依赖外部服务的可选用例。
- `scripts/ci.js --offline` 7 项全 PASS: ① 路由挂载检查 ② 后端单元测试全量 (239.5s) ③ API 合约测试 ④ Remotion TS 编译 ⑤ 前端生产构建 ⑥ 前端 vitest ⑦ 模板预览 smoke。
- 前端 `vitest run` 40/40 (6 个测试文件: drafts/autoedit/auth/Composer/App/AutoEditPage)。
- `npm run build` 产物 dist/ 正常 (drafts/autoedit/avatars/templates/voices/env-check/index 6 页面)。
- `py_compile` 132 个文件全过 (当前 HEAD, 含上轮 main 反向依赖强拆改动)。
- 代码规模: Python 153 文件 / 23,362 行; 前端 TS/TSX 28 文件 / 3,690 行; git 52 commits。

---

## 3. 功能与工作流验证 (smoke 实测)

### 3.1 认证与安全链路 ✅ 全通
- register → login → me → refresh → logout 全链路; **refresh token 轮换**: 旧 token 再用返 401 (原子化 UPDATE + rowcount 校验)。
- 限速: 5 次错误密码后第 6 次返 429 (IP+email 桶); `FLIKI_ENV=test` 下 reset 端点可用。
- 注册角色白名单: `role=admin` 返 403。无 token 访问受保护端点返 401。
- 注意: 登录响应字段名是 `token` (非 `access_token`), 前端已按此契约实现, 但 OpenAPI 与常见约定不一致, 外部对接方需知晓。

### 3.2 核心业务工作流 ✅ 全通 (带 token)
- workflow-drafts: 创建(source_script 自动分镜) → scenes 追加 → reorder → 列表 → confirm, 全部按 user_id 隔离, 跨用户 404 防枚举。
- render 管线: `POST /render.create` 排队 (mock renderer) → `/render-jobs/{id}` 查询 → `/render.latest?playback_id=` 查询; job 表含 user_id FK。
- templates: 创建(fields+structure 校验) → 读取 → 删除 → categories 统计; id 强制 `^[a-z0-9_]+$`。
- voices / voices/locales: edge_tts 真实返回 400+ 语音; env-check 能力矩阵: edge_tts/faster_whisper/wav2lip_onnx/remotion_render/autoedit_pipeline/gpt_sovits_cpu/heygen_api 全 true。
- provider health: wav2lip_onnx configured; GPT-SoVITS (9880) 未运行属预期 (可选服务); minimax 配置在但 enabled=false。

### 3.3 错误合约 ✅
- 404/422/401 统一返回 `{error_code, message, hint, details, status}` 结构; 422 带字段级 errors; 未知路径返 404 JSON。

---

## 4. 安全审计结果

### 通过项 (实测/代码确认)
- **密钥安全**: `.env` (13 个真实 key) 被 `.gitignore` 忽略, 未被 git 追踪; 仅 `.env.example` (键名无真实值) 入仓; docs/secrets.archive 已迁出仓库留 .gitkeep。JWT_SECRET 64 字符强随机。
- **CORS 白名单**: `http://evil.example.com` 请求无 ACAO 头 (实测); `localhost:5180`/`127.0.0.1:5180` 放行; preflight OPTIONS 返 204。
- **安全头**: X-Content-Type-Options: nosniff、X-Frame-Options、Referrer-Policy、CSP (frame-ancestors none 防 clickjacking) 全部实测存在; X-Request-ID 自动生成。
- **SQL 注入面**: 业务层 execute 全参数化; `db/connection.py` 的字符串拼接仅限内部 schema 迁移 (table/col 来自内部常量, 非用户输入)。
- **路径穿越**: `/outputs/..%2f.env`、`/uploads/..%2f..%2f.env` 全返 404 (实测); file_security.py 有 Windows 保留名 + 非法字符清洗。
- **上传鉴权**: `/api/uploads` 无 token 返 401; 静态挂载 `/outputs` `/uploads` 依赖 UUID 不可枚举 (设计已文档化)。
- **SQLite 并发**: busy_timeout + 每线程独立连接; 唯一例外 `workers/render_queue.py` 模块级共享连接, 但由单进程 SimpleQueue 串行化 (需保持该约束, 勿多进程)。

### 弱项 (不阻塞, 生产前处理)
- CSP `script-src 'unsafe-inline'` + `connect-src http: https:` 偏宽 (本地工具可接受)。
- `config.py` DB_PATH 固定 `app.db`, 无环境隔离 (FLIKI_ENV=test 也写同一库) — 测试/生产共用库风险。

---

## 5. 工程与架构审计

### 结构健康 ✅
- 分层清晰: `routers/` (startup/alerts/analytics/render) + `models/` + `providers/` (tts/avatar/stock/music) + `services/` + `workers/` + `db/` (schema.sql 21 表 + 30 索引)。
- 上轮强拆后 `from main import get_db` 反向依赖已清零 (grep 确认); `_resolve_con` 直连 `db.connection.get_db`。
- `metrics_router.py` (/metrics/summary, /metrics/users...) 与 `routers/analytics.py` (/metrics, /characters, /providers) 路径不冲突, 但职责可归并。
- pre-commit (ruff + trailing-whitespace + detect-private-key) 与 commitlint 配置完整。

### 发现项 (见 §7 问题清单)
- `routers/render.py` L184-185 双 `@router.post("/render.create")` (同函数重复装饰, 无害冗余)。
- 匿名创建草稿成孤儿 (P1, 详见 §7-1)。
- `.gitignore` L47 断行 bug 导致 `app/autoedit.html.vanilla.bak` pattern 失效, 该 17KB 备份文件已被 git 追踪 (P2)。

---

## 6. 文档与交付一致性

| 项 | 状态 |
|---|---|
| README 更新时间 | ❌ 写 2026-08-01 rev30 / HEAD a25d336; 实际 HEAD 489253b, 落后 30+ commits |
| README 测试数 | ❌ 写 532; 实际 569 |
| README "当前改动尚未提交" | ❌ 已过时 (工作树干净) |
| INSTALL.md | 285B 极简, 指向 README (可接受) |
| docs/ 工程设计文档 | ✅ 8 篇 (BACKUP_DR/DOWNLOAD_AUDIT/motion-doctrine/render-segment/stage-c 等) |
| .env.example vs .env | ⚠️ 键名前缀不一致 (PEXELS_API_KEY vs FLIKI_PROVIDER_PEXELS_API_KEY), 示例未覆盖 JWT_SECRET/FLIKI_ALLOWED_ORIGINS 等 |
| CI (.github/workflows/ci.yml) | ⚠️ 配置完整 5 job, 但**仓库无 git remote, 从未真实跑过** |

---

## 7. 问题清单 (按优先级)

### P1 (修复 0.5-1 天)

1. **匿名创建草稿成孤儿** (`workflow_drafts.py`)
   - 现象: 无 token `POST /workflow-drafts` 创建成功 (user_id=None); 之后任何 token 或无 token 访问该草稿都 401/404 (实测证实), 数据永久不可达。
   - 触发: 前端 `ensureSession` 失败 (后端未起/网络抖动) 时用户仍创建了草稿, 恢复会话后草稿"丢失"。
   - 修复: 二选一 — (a) create_draft 无 token 直接 401 (与其它写端点一致); (b) 允许匿名创建但创建响应带一次性 claim 令牌供绑定。推荐 (a) 简单一致。

2. **Docker compose 浏览器路径不一致** (`docker-compose.yml`)
   - 现象: compose 覆盖 `REMOTION_BROWSER_EXECUTABLE=/usr/local/bin/fliki-chromium`, 但 Dockerfile 装的是 google-chrome-stable 且 ENV 指向 `/usr/bin/google-chrome-stable`; compose 值指向的文件在镜像中不存在。
   - 影响: 容器内 Remotion 渲染可能找不到浏览器 (除非 remotion_runner 有兜底)。
   - 修复: compose 删除该覆盖行 (沿用 Dockerfile ENV), 或 Dockerfile 建立 symlink。需真机验证一次 `docker compose build && up` + 模板渲染。

### P2 (修复 1-2 天)

3. **requirements.txt 依赖缺口**: `requests` (cloud_renderer 有 try/except 兜底, 缺了静默降级)、`faster_whisper`/`openai` (autoedit 转写, 裸 import 无兜底, 未装时调用即 ImportError→500); CI 里 `pip install -r requirements.txt || true` 掩盖缺口。
4. **无 git remote / CI 未运行**: 52 个 commit 全在本地; `.github` 5 个 job 从未真实执行。交付前需建仓推送, 首跑 CI 大概率暴露 Windows runner 上的依赖/路径问题。
5. **README 过期**: HEAD 基线、测试数、状态段需同步; 建议每次 commit 后由脚本更新或至少周更。
6. **`.gitignore` L47 断行 bug**: `app/autoedit.html.vanilla.bak# Runtime data ...` 注释与 pattern 挤一行; 修复后 `git rm --cached` 该备份文件。
7. **无草稿删除端点**: `DELETE /workflow-drafts/{id}` 返 405; templates 有删除而 drafts 没有, 功能不对称。
8. **DB 无环境隔离**: `config.py` DB_PATH 固定; 建议支持 `FLIKI_DB_PATH` 环境变量, 测试/CI 用独立库。
9. **双 `@router.post("/render.create")`** (`routers/render.py` L184-185): 删一行即可, 防止未来语义混淆。
10. **CI 弱门禁**: `pip install ... || true` 应改为严格失败; requirements 与显式 pip install 重复, 应统一。

### P3 (顺带清理)

11. `.env.example` 键名与 `.env`/代码读取键不一致, 补全 FLIKI_JWT_SECRET/FLIKI_ALLOWED_ORIGINS/FLIKI_PROVIDER_* 前缀对齐。
12. `metrics_router.py` 与 `routers/analytics.py` 可归并 (职责分散)。
13. requirements-wav2lip.txt 独立文件, 部署需手动组合; 建议主 requirements 加 optional extras 或安装脚本。
14. CSP 偏宽 (本地可接受, 生产前收紧 script-src/connect-src)。
15. Dockerfile EXPOSE/CMD 5181 vs compose 8765 默认分叉 (compose 覆盖后一致, 但易混)。

---

## 8. 交付能力评估 (短板与建议)

### 能力矩阵

| 能力 | 评分 | 说明 |
|---|---|---|
| 功能完备性 | 9/10 | 78 端点覆盖 6 大工作流 + 辅助能力; auth/render/workflow/templates/voices/avatar 全通 |
| 代码健康 | 9/10 | 569 测试 + 7/7 强门 + 全量编译过; 无 TODO/死代码残留; 分层清晰 |
| 安全基线 | 8.5/10 | 密钥/CORS/安全头/限速/轮换全实测过; CSP 与 DB 隔离待生产化 |
| 文档一致性 | 5/10 | README 过期 30+ commits; 交接主文档是最新但项目状态段未同步 |
| 工程化 (CI/CD/部署) | 3.5/10 | 无 git remote、CI 未运行、Docker 浏览器路径 bug、依赖清单缺口 |
| 可维护性 | 8/10 | 反向依赖已清、模块边界清晰、schema 有迁移机制; 剩余小冗余可清理 |

### 短板 → 下一步建议 (按 ROI 排序)

1. **建 git remote + 推仓, 首跑 GitHub Actions** (0.5 天): 暴露真实 CI 问题, 补齐交付闭环。
2. **修 P1 两项** (0.5-1 天): 匿名草稿孤儿 + Docker 浏览器路径, 各补一个回归测试。
3. **依赖清单补全 + requirements 收敛** (0.5 天): requests/faster_whisper/openai 入 requirements (或 optional extras), CI 去掉 `|| true`。
4. **README/.env.example 同步 + .gitignore 修复** (0.5 天): 含 `git rm --cached` 备份文件。
5. **DB 环境隔离** (0.5 天): FLIKI_DB_PATH 支持, 测试/生产分库。

---

## 9. 审计副作用说明 (透明)

- 审计期间向 `backend/data/app.db` 写入了若干 `audit-*` / `local-*@fliki.local` 测试用户与草稿记录 (正常 register/login 流程产生); 均为随机邮箱, 不影响业务数据, 可清理。
- 审计期间启动/停止了 uvicorn (5181, FLIKI_ENV=test) 与 scripts/ci.js 强门; 未修改任何产品代码。
- 临时脚本已清理 (`.run_audit_start.ps1` 等)。
- 报告文件: `D:\workspace\Fliki视频制作还原\AUDIT_REPORT_2026-08-02.md` (与 README/HANDOFF 同级, 便于交接)。

---

# 追加: P1/P2 修复 + 工作流完整性复审计 (2026-08-02 下午)

## A. 修复落地 (4 commits: e1ae64c / ee0d490 / 85cb1bd / d4152c9)

### P1 两项
1. **匿名草稿孤儿**: `create_draft` 无 token 直接 401; 新增回归测试 (匿名创建 401). 实测: 匿名 POST /workflow-drafts → 401. ✅
2. **Docker 交付链路**: 3 处修复 — ① compose `build.context: .` → `..` (Dockerfile `COPY backend/...` 需要仓库根 context) + `dockerfile: backend/Dockerfile`; ② `REMOTION_BROWSER_EXECUTABLE` compose 覆盖值与 Dockerfile ENV 对齐为 `/usr/bin/google-chrome-stable`; ③ 新增根 `.dockerignore` 控制 context 体积. 另修 `.env` 文件头 BOM+空行 (docker compose env_file 解析失败).
   - **构建验证受网络阻塞**: `docker compose build` 在安装 google-chrome-stable 阶段失败 — `dl-ssl.google.com`/`dl.google.com` 在本机网络不可达 (环境性, 非代码问题). 代码级修复已完成; 实际构建需代理/可访问 Google 的网络, 或改用 chromium 包 (见 §C 优化项).

### P2 八项
| # | 项 | 状态 |
|---|---|---|
| 3 | requirements 依赖缺口 | ✅ 补 requests/openai/faster-whisper; CI 去掉 `|| true` 弱门禁和重复 pip install |
| 4 | git remote / CI 未运行 | ⚠️ 需用户建仓推送 (本机无账号可代建); README 已列入队列 |
| 5 | README 过期 | ✅ 状态段同步 HEAD/测试数/审计链接 |
| 6 | .gitignore 断行 bug | ✅ L47 拆行修复; `git rm --cached` 移除 app/autoedit.html.vanilla.bak (17KB) |
| 7 | 无草稿删除端点 | ✅ 新增 `DELETE /workflow-drafts/{draft_id}` (owner 校验; 有关联 run 返 409; 无 run 级联删除) + 3 回归测试 |
| 8 | DB 无环境隔离 | ✅ config 支持 `FLIKI_DB_PATH` 覆盖; 实测隔离库完整跑通工作流 |
| 9 | 双 @router.post | ✅ render.py 删重复装饰器 |
| 10 | CI 弱门禁 | ✅ 随 #3 一并收紧 |

另顺带: `.env.example` 补 FLIKI_JWT_SECRET / FLIKI_ALLOWED_ORIGINS / FLIKI_DB_PATH 三键. ✅

## B. 工作流完整性复审计 (端到端实测, 隔离库)

| # | 工作流环节 | 结果 |
|---|---|---|
| 1 | 匿名创建草稿 | 401 (P1-1 生效) ✅ |
| 2 | 注册登录 → 带 token 创建草稿 (source_script 自动分镜 3 场景) | ✅ |
| 3 | 追加场景 → reorder 倒序 → confirm | ✅ |
| 4 | from-draft 创建 run → run 详情查询 | ✅ |
| 5 | 有 run 删草稿 | 409 (防误删渲染产物) ✅ |
| 6 | 无 run 删草稿 → 删除后读 | 200 + {"deleted":true} → 404 ✅ |
| 7 | 跨用户访问 (B 读 A 的草稿/run) | 404 防枚举 ✅ |
| 8 | 列表 user 隔离 (A 1 条 / B 0 条) | ✅ |

全量回归: **573 tests OK (5 skipped)** — 含 4 个新测试 (匿名创建 401 ×1, 删除端点 ×3). 前端 build + vitest 40/40 通过.

### 新发现 (复审计): 测试基建与 DB 隔离耦合
- `test_p0_security` / `test_d1_tenant` / `test_p1a_user_metrics` 等 live 测试依赖"测试进程与服务进程共享默认 app.db" (测试进程直接写临时库, 服务 HTTP 读默认库). 用 `FLIKI_DB_PATH` 隔离服务后这组失败 (6 个). 默认库下全绿. 属测试基建耦合, 生产化/CI 隔离前需重构: live 测试应全部通过 API 自举数据, 或测试进程与服务读取同一 `FLIKI_DB_PATH`.

## C. 短板评估与优化提升方案 (按 ROI)

| 优先级 | 优化项 | 内容 | 工作量 |
|---|---|---|---|
| P0 | 建 git remote + 首跑 CI | 推仓后 .github 5 job 首次真实运行; 在 CI 加"起服务跑 live 测试组"步骤 (当前 live 组在 CI 会 skip) | 0.5 天 |
| P0 | Docker 构建网络化 | Dockerfile chrome 源支持 build-arg 指向国内镜像, 或换 `chromium` apt 包 + REMOTION_BROWSER_EXECUTABLE 调整; 构建后跑一次模板渲染验证 | 0.5-1 天 |
| P1 | live 测试去耦合 | p0_security/d1_tenant/p1a 改为 API 自举数据或统一 FLIKI_DB_PATH 读取 | 0.5-1 天 |
| P1 | 真实渲染/转写工作流验证 | 本机跑一次真实 Remotion 模板渲染 (非 mock) + autoedit 上传→faster-whisper 转写→草稿 闭环 | 1-2 天 |
| P2 | 文档自动同步 | scripts 更新 README 状态段 (HEAD/测试数), commit hook 或周更; 防再次过期 | 0.5 天 |
| P2 | 草稿生命周期 | archived 清理策略 + draft_revisions 保留上限 | 0.5 天 |
| P3 | CSP 收紧 | 生产前置: script-src 去 unsafe-inline, connect-src 白名单化 | 0.5 天 |

## D. 验证命令速查

```bash
# 全量回归 (需 5181 起服务, FLIKI_ENV=test)
python -m unittest discover -s tests -p "test_*.py"
# 离线强门 7/7
node scripts/ci.js --offline
# 前端
npm run build && npx vitest run
```
