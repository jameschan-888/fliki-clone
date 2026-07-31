# rev18 阶段 C 进展报告 (2026-07-28)

## 启动动机

突破单机 chrome OOM 红线 (15min 视频), 跑通 5min × 5 成功率 ≥ 90% 验收门.

## 已完成

| 项 | 文件 | 状态 |
|---|---|---|
| 云端 renderer 抽象 + Mock | `backend/workers/cloud_renderer.py` (5KB) | ✅ |
| render 持久化任务队列 | `backend/workers/render_queue.py` (3.7KB) | ✅ |
| dispatcher 接入 render_slot | `backend/workers/segment_dispatcher.py` L196-197 | ✅ 代码就绪 |
| main.py cloud 分支 | `backend/main.py` L337-351 | ✅ |
| README 更新 | `README.md` (rev18 阶段 C 段, run id 表) | ✅ |
| red-line 更新 | `tests/load/red-line.md` (rev18 阶段 C 段, 验收门表) | ✅ |
| 踩坑日志追加 | `D:\workspace\踩坑日志.txt` (8 条) | ✅ |
| dispatcher smoke test 脚本 | `scripts/_b_dispatcher_smoke.py` (5.2KB) | ✅ |
| 后台 monitor | `scripts/_monitor_round.js` PID 25612, `tests/load/monitor_round_2_5.log` | ✅ |

## 实测数据 (round 1-2 已 PASS)

| Run | 模式 | 时长 | 结果 |
|---|---|---|---|
| 25b91565 | round 1 (5min, 30 场景 K=3 cloud) | 35min | ✅ 6MB MP4 |
| a925eae3 | round 2 (5min, 30 场景 K=3 cloud) | 39min | ✅ 9MB MP4 |
| 3b6e4086 | round 3 (5min, 30 场景 K=3 cloud) | ⏳ 进行中 | (asset 24%) |
| - | round 4-5 | ⏳ 排队 | - |
| e89e35fb | 15min cloud K=3 PASS | 96min | ✅ 27MB MP4 |

## 待验证 (round 3-5 完成后)

1. `scripts/_b_dispatcher_smoke.py` 真实验证 render_queue semaphore (CRITICAL)
2. **重启后端** (让 dispatcher render_slot 真进内存: 后端 PID 39280 启动 15:05 早于 dispatcher 16:06 改动)
3. README/red-line finalize 5 轮成功率统计

## 环境配置 (round 5 完成后)

```bash
# 重启后端 (env 含 PYTHONIOENCODING=utf-8 防 ffmpeg 静默吞错)
Stop-Process -Id 39280 -Force
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'
$env:RENDER_PROVIDER='cloud'; $env:RENDER_SEGMENT_SCENES='30'
$env:RENDER_QUEUE_MAX_CONCURRENT='1'  # smoke test 强制串行
Start-Process powershell -ArgumentList 'node D:\workspace\Fliki视频制作还原\scripts\start_backend.js' -WindowStyle Hidden

# 等 5s 健康
curl http://127.0.0.1:5181/health

# 跑 smoke test
python D:\workspace\Fliki视频制作还原\scripts\_b_dispatcher_smoke.py --scenes 4 --duration 5
```

## 关联文档

- README.md (顶层主文档, rev18 段已加)
- tests/load/red-line.md (红线评估, rev18 验收门表已加)
- D:\workspace\踩坑日志.txt (8 条新增 rev18 坑)
- D:\workspace\规矩文档.txt (不动, 第 25-34 条已覆盖)
- backend/data/render_queue.db (semaphore SQLite 持久化)

## 下次接手第一件事

```bash
# 1. 看 monitor 是否还在 + log 最新行
Get-Process -Id 25612 -ErrorAction SilentlyContinue
Get-Content D:\workspace\Fliki视频制作还原\tests\load\monitor_round_2_5.log

# 2. 如已 "ALL DONE", 按本文件 "环境配置" 段重启后端 + 跑 smoke test
# 3. 如 monitor 还在, 等下一个 5min 周期再查
```
