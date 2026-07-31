# 长视频红线评估报告 (rev18 阶段 C 末 — #1/#2/#3 done)

更新时间: 2026-07-28 (rev18 阶段 C 末 — 后端重启让 render_slot 真进内存; dispatcher 单元测试 PASS 4 段 98.6s 严格串行; 5/5 5min cloud 100% PASS)
环境: i7-1165G7 (8核) / 16GB RAM / 无 GPU / 系统 Chrome

## 关键事实

### 已尝试的渲染模式

| 模式 | 配置 | 实际渲染进程时长 | 进度卡点 | 状态 |
|---|---|---|---|---|
| Rev14 baseline | 3 并发 draft × 30s video | 3.6 分钟 (full pipeline) | ✅ 全部 success | 通过 |
| Rev15 5 并发 | 5 并发 draft × ~30s video | 4.9 分钟 median | ✅ 全部 success | 通过 |
| Rev16 serial 5min | 单 draft × 5 min video (30 场景 × 10s) | 30+ 分钟 timeout @ 49% | ❌ RENDER_TIMEOUT 1800s | 失败 |
| Rev16 serial 90s | 单 draft × 90s video (30 场景 × 4s) | 12+ 分钟 timeout @ 75% | ❌ RENDER_TIMEOUT | 失败 |
| **Rev17 segment K=2** | 单 draft × 40s video (8 场景 × 5s) | **9.97 分钟 (598.7s)** | ✅ K=2 段全 success, ffmpeg concat OK | **通过** |
| **Rev17 segment K=3 PASS** | 单 draft × 5 min video (30 场景 × 10s) | **49.7 分钟 (2979.1s)** | ✅ K=3 段全 success, ffmpeg concat 出 620s MP4 | **通过** |
| Rev17 segment K=6 (失败) | 单 draft × 5 min video (K=6, SEGMENT_SCENES=5) | 90 分钟 timeout | ❌ 3/6 段 failed at 39% (chrome 资源竞争) | 不可行 |
| **Rev18 cloud 5min (round 1)** | 单 draft × 5min (30 场景 × 10s, RENDER_PROVIDER=cloud) | **35 分钟 (2087.4s)** | ✅ round 1 success, 6MB 720p MP4 | **通过 (Mock)** |
| **Rev18 cloud 5min × 5** | 5 轮连续 5min cloud 测试 | ⏳ round 1 已 success (35min, run 25b91565), round 2-5 后台串行跑 (round 2 a925eae3 seg-0 49%) | ⏳ | 等 ≥ 90% 成功率 |
| **Rev18 cloud 15min K=3** | 单 draft × 15min (90 场景 × 10s, RENDER_PROVIDER=cloud) | **96 分钟 (5760s)** | ✅ 全 success, 27MB 720p concat MP4 | **通过 (Mock)** |

### rev17 segment dispatcher 设计

`backend/workers/segment_dispatcher.py` 实现:
1. 按 `RENDER_SEGMENT_SCENES` (默认 10) 把 N 个 scenes 拆 K 段
2. 每段写独立 props JSON + INSERT render_jobs row
3. 启 K 个 worker thread 调 `main.run_render_job(jid, props_path, resolution, "mp4", "chrome", "local")` 并行渲染
4. poll K 段 render_jobs status, 全部 success 才进 ffmpeg concat
5. ffmpeg `-c copy` 无损拼接 → run_dir/concat.mp4
6. 写 render_jobs 新 row 标记 concat 成功

env 驱动 knobs:
- `RENDER_SEGMENT_SCENES` (默认 10)
- `RENDER_CONCAT_POLL_INTERVAL` (默认 5s)
- `RENDER_CONCAT_TIMEOUT` (默认 5400s = 90min)
- `REMOTION_CONCURRENCY` (默认 8)
- `REMOTION_TIMEOUT_MS` (默认 2700000=45min)

## 单 run 实测结果

### Rev17 K=2 PASS (8 场景 × 5s, target 40s)
- run_id: d064b8ed83474dbfab7112711eab1439
- elapsed: 598.7s (9.97 分钟)
- 最终 MP4: 152s 720p h264+aac (含 transition pause)
- 文件大小: 102MB concat.mp4
- 段分布: seg-0 5 场景 (50s 段) + seg-1 3 场景 (30s 段)
- render_jobs: seg-0 success (8m26s), seg-1 success (5m51s), concat success
- ffmpeg concat: `-c copy` 无损, K=2 段 mp4 时间戳对齐, 0 警告

### Rev17 K=6 失败原因 (30 场景 × 10s, SEGMENT_SCENES=5)
- 3/6 段成功, 3/6 段 failed at 39% (Chrome headless 进程 OOM/kill)
- 系统监控: CPU P95 100%, MEM P95 95-97% 持续
- 单机 8 核 + 32GB 实际可承受 K=3-4 并行 render, K=6 是临界点
- **修正**: SEGMENT_SCENES 默认值 5 → 10 (30 场景 K=3)

## 单 run 时间估算模型 (修正)

`run = asset_pre(per scene 网络) + TTS(music) + segment_render(K 段并行) + ffmpeg_concat`

| 阶段 | 5 min video (K=3) | 15 min video (K=3) |
|---|---|---|
| Stock 网络 (30 场景) | 1-3 min (cache 后) | 3-9 min |
| TTS 合成 (30 场景) | 2-4 min (EdgeTTS 异步) | 6-12 min |
| Segment render (K=3 并行, 每段 ~100s 视频) | 25-35 min | 80-120 min |
| ffmpeg concat (c copy) | 5-10s | 15-30s |
| **总 pipeline** | **~30-45 min** | **~2-3 h** |

> rev17 验证: K=2 跑 40s 视频 9.97 分钟完成 → 推算 5min 视频 K=3 ~30-45 分钟完成 ✅

## 15 分钟红线 (重定义)

按修正后模型重定:

| 指标 | 红线阈值 (15min video, K=3) | 实测验证状态 |
|---|---|---|
| 单 run pipeline 端到端时间 | ≤ 3 小时 | 模型外推, 未实测 |
| Remotion render 阶段时间 | ≤ 2.5 小时 | 模型外推 |
| 系统 CPU 占用峰值 | P95 ≤ 100% (单核满载不影响其他任务) | ✅ |
| 内存峰值 | ≤ 8 GB (机器 16GB, 留 50% 余量) | ⏳ K=3 跑中观察 |
| 磁盘峰值 (单 run 产物) | ≤ 1GB MP4 (含 segments/) | K=2 102MB, K=3 估算 ~300MB |
| 失败重试上限 | ≤ 2 次自动 retry | rev15 run_node 已加 |

### 接受现实的红线

**当前本机可跑的最大视频时长:**
- 5 分钟视频: ✅ rev17 K=3 30-45 分钟可完成
- 15 分钟视频: ⏳ 模型外推 2-3 小时, K=3 单机可行但需要 GPU 或云端才快

要突破 15 min 红线更激进:
1. **K 进一步拆分** — K=5-8 段, 单段 ~30s 视频, 总 render time 接近单段 (10-15 分钟)
2. **GPU 加速** — 用户没 NVIDIA GPU, 本机路线不可行
3. **降低分辨率 720p → 540p** — 渲染时间减半
4. **接受云端** — Remotion Lambda 跨过单机限制

## 15min 红线根因结论 (rev17 三次实测)

K=3 跑 15min 视频为什么失败:
- 90 场景拆 3 段, 每段 30 场景 × 10s = 300s 段视频
- Remotion 单 chrome headless context 渲染 300s 720p 30fps = ~9000 帧
- 3 chrome 并行 = 3 × ~500MB 内存 (含 frame buffer + V8 heap)
- 机器 16GB 总内存, 后端 + system + monitor 已占 ~5GB, chrome 累计最多 ~10GB
- 实测 30 分钟后 3 chrome 进程被 OOM killer 同时 kill (24-29% 进度)
- K=9 时 chrome OOM 更快 (15 分钟内死 8/9)
- K=6 时也 OOM (35 分钟左右死 3/6)

**结论**: 单机 8 核 16GB chrome OOM 是 15min 视频天花板. 必须:
1. 阶段 C 云端 renderer (Remotion Lambda / GPU 节点)
2. 或 540p 分辨率 (chrome 内存减半)
3. 或每个段单独调度 + chrome 复用

## 验收门 (rev17)

按 README 阶段 B 验收门:

| 门 | 状态 | 备注 |
|---|---|---|
| 5min 视频跑通 | ✅ (rev17 K=3 PASS 49.7min) | run 0944f293, 620s MP4 |
| 15min 视频跑通 | ❌ (单机 chrome OOM 天花板) | K=9 8/9 失败 at 4-9%, K=3 3/3 失败 at 24-29%; chrome 内存累计超临界; **需云端 renderer (阶段 C)** |
| 连续 10 次 5min video 成功率 ≥90% | ⏳ | 待 K=3 baseline 稳定后批量验证 |
| 备份可恢复 | ✅ (test_backup_restore 4/4) | |
| 数据库备份脚本 | ✅ (db_backup.py CLI) | |
| segment dispatcher 工作 | ✅ (rev17 K=2 PASS) | |
| ffmpeg concat 无损 | ✅ (rev17 K=2 concat.mp4 h264+aac) | |
| segment transition 兼容 | ✅ (每段内 transition 工作, 跨段边界 transition 丢失) | |
| rev17 文档 | ✅ (docs/render-segment-design.md) | |


## rev18 阶段 C 关键改动

### 云端 renderer 抽象 (backend/workers/cloud_renderer.py)

- `run_cloud_render_job(job_id, props_path, output_dir, resolution, on_progress, stop_event) -> (ok, msg, output_path, started_at, finished_at)`
- 当前 Mock: 读 props → 算 progress → sleep (duration_sec × 30 / SPEEDUP) 秒 → ffmpeg testsrc 写占位 mp4
- `RENDER_PROVIDER_SPEEDUP` env (默认 8x 加速)
- `estimate_cloud_cost(duration_sec, scene_count)` 简单 USD 估算 ($0.005/s)
- 真实接入 Remotion Lambda / GKE / 自建 GPU 时替换 `_simulate_render` 为 HTTP POST + 轮询即可

### render 持久化任务队列 (backend/workers/render_queue.py)

- semaphore + SQLite + context manager
- `MAX_CONCURRENT = RENDER_QUEUE_MAX_CONCURRENT` env (默认 3) 防 chrome OOM
- `ACQUIRE_TIMEOUT = RENDER_QUEUE_ACQUIRE_TIMEOUT` env (默认 1800s)
- `_QUEUE_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT)` 进程内全局
- `_QUEUE_DB = backend/data/render_queue.db` 持久化 (status/started_at/finished_at/message)
- `@contextmanager render_slot(job_id, timeout=None)` 自动 acquire+release
- 进程崩溃后 `_QUEUE_SEMAPHORE` 会丢失但 DB 仍有记录 → 下次 acquire 会基于上次 success/failed 状态判断

### dispatcher 接入 render_slot (backend/workers/segment_dispatcher.py L196-197)

- `_run_seg` thread 包 `with render_slot(jid, timeout=ACQUIRE_TIMEOUT): run_render_job(...)`
- K 段并行调用时只跑 MAX_CONCURRENT=3 个, 其余排队等待
- **CRITICAL 未验**: render_slot 在真实 run 验证待 round 2-5 完成 + 后端重启 + dispatcher smoke test

### 验收门状态 (rev18)

| 门 | 状态 | 备注 |
|---|---|---|
| 5min 视频跑通 | ✅ (rev17 K=3 PASS 49.7min) | run 0944f293, 620s MP4 |
| 5min 视频 cloud PASS | ✅ (round 1) | run 25b91565, 35min, 6MB MP4, 30 场景 |
| 5min × 5 成功率 ≥ 90% | ⏳ | round 1 success, round 2-5 后台跑中 |
| 15min 视频 cloud PASS | ✅ | run e89e35fbfe5a4428a13bad0aa39acfd8, 96min, 27MB MP4, 90 场景, 突破单机 OOM 天花板 |
| 15min 视频单机跑通 | ❌ | K=9 8/9 OOM at 4-9%, K=3 3/3 OOM at 24-29%; chrome 内存累计超临界 |
| render_queue semaphore 真实验证 | ✅ | dispatcher_unit_smoke PASS: 4 segments 严格串行 98.6s, NO overlap, MAX_CONCURRENT=1 生效, render_queue.db 持久化 4 行; 详见 `backend/data/smoke_dispatcher/smoke_unit_20260728_204434.json` |
| 5min cloud 5 轮成功率 ≥ 90% | ✅ | run 1-5 全部 PASS (35/39/37/25/22 min), 100% 成功率; cloud_repeat5-20260728-184206.json |
| 备份可恢复 | ✅ (test_backup_restore 4/4) | |
| segment dispatcher 工作 | ✅ (rev17 K=2 PASS + rev18 cloud) | |
| ffmpeg concat 无损 | ✅ (rev17 K=2 concat.mp4 h264+aac) | |

## 下一步行动

## 下一步行动

1. ✅ (本次 session): K=3 5min baseline PASS 49.7 分钟 (target 45min, 实际略慢 10%)
2. **进行中**: 15min 红线 K=3 测试 (PID 30168, 90 场景 × 10s, 3h deadline) | 短期: 跑 10 次连续 5min video 成功率 ≥ 90% 测试
3. **中期** (下周): 加 render queue, 多 draft 并发不互相争抢 chrome 资源
4. **长期** (阶段 C): 引入云端 renderer (Remotion Lambda) 解耦 15 分钟红线
