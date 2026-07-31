# 多租户 FK (rev24 阶段 C #8)

## 目标
- workflow_drafts / workflow_runs / render_jobs 三张表加 `user_id` 列
- JWT 中间件从 Authorization header 解 `sub` 注入 user_id
- 旧 DB 通过 init_db 自动 ALTER 加列 + 索引
- 不带 token 仍可创建 draft/run（兼容匿名路径），user_id 留空

## 端到端协议
1. `POST /auth/register` 拿 JWT
2. `POST /workflow-drafts` 带 `Authorization: Bearer <token>` 创建草稿
   - 后端从 token 解 `sub`，写入 `workflow_drafts.user_id`
3. `POST /workflow-runs/from-draft/{id}?force=true` 同样注入 user_id
4. `POST /render.create` 注入 user_id

## schema 变更 (db/schema.sql)
- `workflow_drafts.user_id TEXT`
- `workflow_runs.user_id TEXT`
- `render_jobs.user_id TEXT`
- 三个 `idx_*_user` 索引 (动态创建，旧 DB 升级时保证)

## init_db 兼容
`main.init_db()` 在启动时执行：
1. `executescript(schema.sql)` — `CREATE TABLE IF NOT EXISTS` 创建/无 op
2. 遍历旧列，缺则 ALTER ADD COLUMN
3. 缺索引时动态 CREATE INDEX

## 接入 Lambda 协议
`backend/workers/cloud_renderer.py` 已实现 LambdaProvider，协议：
- `POST {CLOUD_LAMBDA_URL}/renders` (body: `{jobName, renderSpec, inputProps(b64), codec}`)
  → `{jobId, status: "queued"}` (202)
- `GET {CLOUD_LAMBDA_URL}/renders/{id}` → `{jobId, status, progress, outputUrl?, message, ...}`
- `GET {CLOUD_LAMBDA_URL}/renders/{id}/download` → mp4 bytes

`scripts/lambda_stub.js` 是本地 stub server，验证协议。生产环境只设
`CLOUD_LAMBDA_URL=https://your-lambda.example.com` 即可切换。

## 端到端验证 (已跑)
1. **Lambda provider 端到端**: submit → poll (progress 0→25→60→100) → download
   - 实测: 5.1s 完成, mp4 152KB (1280x720)
   - 文件: `tests/load/lambda_e2e-20260728-223200.log` (在 /tmp)
2. **多租户 FK 端到端**:
   - register user → token
   - create draft with token → `user_id` 落库正确
   - create draft without token → `user_id=None`
   - /auth/me with token → 返回 user 详情

## 单测
- `tests/test_user_id_fk.py` (5 cases)
  - `get_user_id_from_request` 4 个 case (no header / 坏 token / 有效 token / 篡改签名)
  - `init_db` 幂等性 + 列/索引存在性
- `tests/test_cloud_provider.py` (9 cases, 已有)
- `tests/test_segment_dispatcher_stage_c.py` (6 cases, 已有)

回归 72/72 测试在 10.7s 通过 (cloud + multi-tenant + workflow_drafts + render_progress 等)

## 已知短板
- 路由级 `request: Request = None` 兼容性写法只为单测; 生产 FastAPI 永远会注入
- 没有 `WHERE user_id=?` 过滤的 list 端点 (需要后续做 GET /workflow-drafts 列表)
- 没有跨用户共享/授权 (multi-tenant 边界是硬墙)
- 旧 task 在 ALTER 时若 app.db 被 uvicorn 锁住, 启动会失败 — 实战需先 stop 后 start
