# Fliki 视频制作还原 - 移交文档 (rev44, 2026-08-06)

## 1. 一句话定位

Fliki 风格的本地 AI 视频制作工具：用户输入脚本 → AI 拆分场景 → 多模态 provider 出图/出音/出视频 → Remotion 合成渲染。本机生产使用，不上线。

## 2. 当前状态 (rev44)

| 项 | 数据 |
|---|---|
| Backend 代码 | 80 .py / ~14k 行 |
| Frontend (app/) | 896 .tsx+ts / ~262k 行 |
| Backend 测试 | 668 PASS + 31 SKIP + 0 FAIL（pytest.ini xdist auto） |
| Routers | 25 文件 / 106 endpoint |
| Provider | DeepSeek 文本 + MiniMax 4 类（image/video/tts/music）+ Pexels/Pixabay/Freesound + Edge TTS + Wav2Lip-ONNX |
| Workflow | 5 大：main drafts + blog/ppt/record/translate |
| 文档 | README 30KB + HANDOVER_NEXT 97KB（自动 router 表）+ 本文档 + 9 个专题 docs/ |
| Backup drill | RTO 0.55s 真删真恢复 + sha256 校验（沙箱） |

## 3. 架构概览

### Backend (FastAPI + SQLite)
- backend/main.py lifespan 入口：env 校验（P0#2 必填 key fail-fast） + 路由挂载
- backend/routers/ 25 个 API 模块；backend/workers/ 后台任务（render_queue + render_manager + cloud_renderer）
- backend/providers/ 多模态 provider 抽象层（image/video/tts/music/text）
- backend/workflows/ 5 大工作流（drafts 主 + blog/ppt/record/translate）
- backend/data/app.db SQLite（WAL + busy_timeout 5s）
- backend/chat.py 自然语言改 draft（5 op: shorten_subtitles/set_aspect/shorten_duration/set_voice/adjust_visual, LLM-first + regex fallback）

### Frontend (React + Vite + Tailwind)
- app/src/ 9 个 page（Home/Drafts/Editor/AutoEdit/Record/Share/Templates/...）
- app/src/api/*.ts 前后端 API 绑定层（重构后端 router prefix 须同步这里）
- a11y 已系统铺：R8/R9/R13/R19a/R19b/R23/R25 + htmlFor + role=alert + aria-label
- app/src/components/VisualDiff 视觉回归测试

### Provider
- MiniMax（多模态）：image+video+tts+music 4 类已接入（rev40 R28a）
- DeepSeek（文本）：chat.py 指令解析 + workflows/blog.py 摘要
- Pexels（真实 key）/ Pixabay / Freesound（素材库）
- Edge TTS（默认 TTS, 离线）/ Wav2Lip-ONNX（口型同步, 本地）

## 4. 关键能力清单

| 能力 | 路由 / 文件 |
|---|---|
| 用户注册登录 | POST /auth/register /auth/login /auth/refresh |
| 创建 draft + AI 拆分场景 | POST /workflow-drafts (use_ai=true 走 DeepSeek ai_split_script) |
| 自然语言改 draft | POST /chat/apply（5 op, LLM-first） |
| 5 大工作流 | POST /workflow-runs/from-draft/{id} + blog/ppt/record/translate |
| 模板预览 | POST /templates/{id}/preview |
| 渲染队列 | render_queue.py semaphore MAX_CONCURRENT=4 + retry helper |
| 监控指标 | GET /metrics（user/tenant 维度, TOP_N=10 + other 桶） |
| 告警 webhook | POST /api/alerts/eval（4 rule + HMAC-SHA256 + throttle 5min） |
| 灾备 smoke | scripts/db_backup_smoke.py 沙箱真删真恢复 + sha256 |
| 路由自动枚举 | scripts/enum_routers.py + precommit hook → HANDOVER_NEXT 顶部 |

## 5. 跑测部署

### 5.1 本机启动
`powershell
# 后端（端口 5181）
cd D:\workspace\Fliki视频制作还原
node scripts/start_backend.js   # 起后端
curl http://127.0.0.1:5181/health   # 应 200

# 前端（端口 5180）
cd app
npm run dev   # 起 vite dev
`

### 5.2 测试
`powershell
cd backend
python -m pytest -n auto --dist=loadfile -m not no_xdist   # 全量 ~154s
python -m pytest -n 0 -m no_xdist   # 串行 ~13s

cd ..
node scripts/ci.js   # 10 阶段
`

### 5.3 灾备演练
`powershell
python scripts/db_backup_smoke.py   # 月度深度（沙箱真删真恢复）
python scripts/db_backup_drill.py   # 周度轻量（验备份完整性）
`

### 5.4 环境变量 (.env)
- 必填（lifespan fail-fast）：DEEPSEEK_API_KEY / MINIMAX_API_KEY / FLIKI_JWT_SECRET（≥32 字符, 非占位）
- 可选：PEXELS_API_KEY / PIXABAY_API_KEY / FREESOUND_API_KEY / ALERT_WEBHOOK_SECRET / OPENAI_API_KEY / SENTRY_DSN
- 测试模式：FLIKI_ENV=test（conftest 已设）+ CHAT_LLM_ENABLED=true/false

## 6. 已完成 ROI 复盘 (rev40-rev44)

| Commit | 内容 | ROI |
|---|---|---|
| 7cb5779 | P0#1 全量测试闭环 | 644 PASS, 10 失败 pre-existing 关闭 |
| ffb1c76 | P0#2 startup env 校验 | 启动 fail-fast 防止漏配 |
| 27a59c2 | P2#11 chat apply e2e | 14 test 覆盖 5 op + auth + LLM |
| d6811a6 | P0#3 灾备 smoke | 沙箱真删真恢复 + sha256 校验, 月度 |
| 6d43c0e | P1#5 render queue | default 3→4 + retry helper |
| 512ea21 | R18 HANDOVER 同步 | 25 router/106 endpoint 表自动 |
| d851745 | R24 TestClient 收口 | 18 test 提速 30-70x |
| 050e178 | R23 a11y 增量 | AutoEditPage + Composer |
| a245cb2 | R25 htmlFor | WorkflowPage implicit→explicit |
| 368836f | R19b a11y | CatalogPages 4 处 + 9 vitest |
| 15dd908 | R19a a11y | SharePage alert + 6 vitest |
| 82bf4a4 | R28c-A ai_split_script | DeepSeek smart scene splitter |
| 968446b | R28c-B chat LLM 解析 | 5 op LLM-first + regex fallback |
| e21ae26 | R26 blog-to-video | URL fetch + DeepSeek 摘要 + MiniMax 图 |
| c1eadee/bee9dcb | R28a/b | MiniMax 4 类 provider + DeepSeek text |

## 7. 已踩坑摘要（详细见 D:\workspace\踩坑日志.txt）

- **N67**: PS heredoc 写多行 Python 含 chr()/转义会 SyntaxError → 用 Python open() 重写
- **N68**: PS 调 git commit -F 中文 message 插 BOM → Python subprocess
- **N70**: generator 写 Python source 用 chr(34) 拼 "", val 必须带外引号
- **N71**: generator JSON 字面量别用 "" + chr(123) + ... + "" 拼 → 用 raw string r'...'
- **N72**: chat.py 错误响应是 D2 格式 {error_code, message, hint, details, status}, 测试用 body.message 不用 body.detail
- **N74**: render_queue retry 用独立 helper 不动 manager（最小风险）
- **N75**: PS 跑 Python subprocess 显式 encoding=utf-8 + text=True
- **N76**: 文件 BOM U+FEFF 导致 ast.parse SyntaxError, raw bytes strip 前 3 byte (b'\xef\xbb\xbf')

## 8. 已知限制 + 待办

### 已知限制
- **render.create in TestClient 阻塞**: render.create 触发 Popen worker subprocess 在 TestClient in-process 同步执行 30s+, 致 test_render_user_id.py 52s/test. 生产路径（live HTTP）异步不受影响。
- **MAX_CONCURRENT 默认 4 未真正接入**: render_queue.py 有 semaphore 但 render_manager.run_render_job 没 acquire_slot. 下次接 background_tasks 时用 render_slot context manager 包一下即可。
- **Pexels key 是真实 key, Pixabay/Freesound 已迁 .env**（rev40）
- **FLIKI_JWT_SECRET = change-me-32-char-min**（dev 占位, prod 会 reject 必填 ≥32 字符非占位值）
- **Pre-existing 测试问题**: test_template_renderer.py 模块 top-level def test_xxx(self) 应为 class method（pre-existing, 非本次改动引入）

### 待办（按 ROI）
1. **R24 第二批**: test_render_user_id.py 改 TestClient（SQL 直插 render_jobs 绕开 render.create background task）
2. **R16 Playwright 关键流程 E2E**: 登录 → 创建 draft → 拆分 → render → 下载（防 SPA flake 重点）
3. **R15 a11y 增量**: DraftsPage / TemplatesPage label + role 排查
4. **render_queue 接入**: background task 包 render_slot context manager（防 chrome OOM）
5. **chat.py LLM 模式扩展**: 当前 5 op, 可加 set_template/translate/auto_adjust 等
6. **MiniMax 5 类扩展**: 当前 4 类（image/video/tts/music）, 可加 live2d / motion / style transfer

## 9. 紧急故障排查

| 现象 | 排查 | 修复 |
|---|---|---|
| 后端启动 fail | check env: DEEPSEEK_API_KEY / MINIMAX_API_KEY / FLIKI_JWT_SECRET | 设齐 3 个必填 |
| SQLite database is locked | 残留 uvicorn 进程 | 杀进程 + 清 .db-journal/.db-wal/.db-shm |
| chat apply 422 但 detail 空 | 实际是 D2 message 字段 | 看 body.message 而非 body.detail |
| provider 调用 401/403 | key 过期或 quota 用完 | 换 key 或联系 provider |
| render 一直 queued | render_queue semaphore 满 | 检查 MAX_CONCURRENT + active slots |
| 测试收集阶段 SyntaxError | 多为 BOM 或 PS heredoc 转义 | 用 Python open 重写, 显式 utf-8 |
| pre-commit 卡住 | enum_routers 检测到 router 未在 main.py include | 加 include_router 或删 router 文件 |

## 10. 接手人第一周 checklist

- [ ] 读 README.md（30KB 项目主文档）
- [ ] 跑 node scripts/start_backend.js + cd app && npm run dev, 确认能起
- [ ] 跑 node scripts/ci.js（10 阶段全过）
- [ ] 看 backend/main.py lifespan + 路由挂载
- [ ] 看 backend/routers/audit_router.py 一个完整 router 模板
- [ ] 看 backend/chat.py 理解 LLM-first + regex fallback 模式
- [ ] 看 backend/workers/render_queue.py 理解 semaphore 模式
- [ ] 看 backend/providers/text/deepseek_text.py 理解 provider 抽象
- [ ] 跑 python scripts/db_backup_smoke.py 验证灾备链路
- [ ] 跑 python scripts/enum_routers.py --check-routes 验证路由覆盖
- [ ] 看 D:\workspace\规矩文档.txt + 踩坑日志.txt

## 11. 联系 + 资源

- Repo: https://github.com/jameschan-888/fliki-clone
- 部署: 本机生产使用, 不上线
- 主要模型: DeepSeek chat + MiniMax 4 类（image/video/tts/music）
- 素材库: Pexels (real) + Pixabay + Freesound
- 视觉回归: app/src/components/VisualDiff + tests/e2e/visual_diff.py
- 文档: 9 个专题 docs/*.md + HANDOVER_NEXT.md 自动 router 表 + 本文档

---

最后更新: 2026-08-06 rev44 (push d851745 R24 第一批)
下一步建议: R24 第二批 (test_render_user_id.py SQL 直插) → R16 Playwright E2E → R15 a11y

