# Render 分段并行重构设计文档 (rev17, 阶段 render-refactor)

更新时间: 2026-07-28
目标: 解决 rev16 单 draft 长 render 卡超时问题，让 15min 视频可在合理时间内完成

## 当前瓶颈 (rev16 实测)

`backend/workers/remotion_runner.py` 一次 render 输出整个 draft 的 mp4。
Remotion 调度 N 个 scene 帧到 chrome headless 单 context，**并发只在调度层生效，实际每帧渲染受 GPU/内存带宽线性约束**。

- 5 min 视频 (30 场景 × 10s × 30fps = 9000 帧) 在 concurrency=8 下实测 **50+ 分钟** 仍卡 49%。
- 90s 视频 (30 场景 × 4s = 3600 帧) 在 concurrency=8 下 **12+ 分钟** 卡 75%。

结论：**单进程渲染是线性瓶颈，资源堆叠无法突破**。必须拆段并行 + ffmpeg 合并。

## 新架构 (rev17)

```
                              draft (N scenes)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              segment_0       segment_1     ...  segment_{K-1}
             (5 scenes)       (5 scenes)         (5 scenes)
                    │               │               │
              parallel_concurrent_remotion_render (subprocess)
                    │               │               │
                 seg0.mp4        seg1.mp4      ... seg{K-1}.mp4
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                          ffmpeg_concat_demuxer
                            (concat list + audio merge)
                                    │
                              final.mp4
```

### 关键决策

1. **拆分单位：每段 S=5 场景** (env `RENDER_SEGMENT_SCENES`)
   - 30 场景 → 6 段；90 场景 → 18 段
   - 段数 K = ceil(N / S)

2. **并行度：每段一个 subprocess**，`P=8` 段同时跑 (env `RENDER_SEGMENT_CONCURRENCY`)
   - 总段数大时分批 (semaphore)
   - 本机 8 核 + Chrome 多 context ≈ 8 段并行最稳

3. **段 Remotion props**：每段 `<Remotion draft segments=[scene_{start}..scene_{end-1}]>`
   - 每段独立 output_path: `data/output/{run_id}/seg_{idx}.mp4`
   - props JSON: `data/props/seg_{idx}_{run_id}.json`

4. **concat 用 ffmpeg concat demuxer** (无损拼接)：
   - 写 list.txt `file seg_0.mp4 \n file seg_1.mp4 ...`
   - `ffmpeg -f concat -safe 0 -i list.txt -c copy final.mp4`
   - audio: 每段 mp4 已含 audio (TTS + music), 直接 c copy 即可
   - 过渡: 默认 `concat` demuxer 无 transition; 需 slide 转场时用 `xfade` filter (rev17 简化: 暂不实现)

5. **状态机**：

```
render_node {
  queued -> segmenting -> segments_queued
  segments_queued -> segments_rendering (K 段, 8 并行)
  segments_rendering -> segments_done (全部 success)
  segments_rendering -> segments_partial (部分 failed, 重试 <=2)
  segments_done -> concatenating -> thumbnails -> success
  任何失败 -> failed
}
```

6. **失败重试**：run_node retry 已经覆盖 (默认 3 次指数退避)

## 改动清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/workers/remotion_runner.py` | 改 | 接受 `--start` `--end` 参数；只渲染 props.scenes[start:end] 范围 |
| `backend/workers/segment_dispatcher.py` | 新 | 拆段调度：创建 K 个 props 子集文件，并行 K 个 render subprocess |
| `backend/workers/ffmpeg_concat.py` | 新 | concat 多个 segment mp4 + 缩略图 |
| `backend/workflow_pipeline.py` | 改 | render_node 改调 segment_dispatcher (而非 remotion_runner) |
| `backend/remotion-project/src/index.tsx` 或 segments 组件 | 改 | 接受 partial scenes 范围 |
| `backend/config.py` | 改 | 加 RENDER_SEGMENT_SCENES=5, RENDER_SEGMENT_CONCURRENCY=8 |
| `scripts/_b_long.py` | 改 | 加 --segments 参数 |
| `tests/load/red-line.md` | 改 | 重测 5min/15min 视频，验证分段并行有效 |

## 验收门

| 指标 | 当前 (rev16) | rev17 目标 |
|---|---|---|
| 5 min 视频 render 总耗时 | 50+ min 卡 timeout | ≤ 10 min |
| 15 min 视频 render 总耗时 | (估 3-5h) | ≤ 30 min |
| 系统 CPU P95 | 91% (单跑) | ≤ 95% (并行) |
| 内存峰值 | 14GB / 16GB | ≤ 12GB |
| 失败重试 | run_node retry 3 次 | 保留 |

## 风险与回退

| 风险 | 缓解 |
|---|---|
| ffmpeg concat 段间帧率/分辨率不一致 | 每段统一 720p 30fps; render props 锁定 |
| Chrome 多 context 内存峰值过高 | P=8 段同时上限; OS swap 监控 |
| segment Remotion 组件未拆干净报错 | 沿用现有 Main 组件，仅传 scenes 子集数组 |
| 段间 transition 转场丢失 | rev17 暂禁用 slide-right 等非 none transition; 加 note 到 README |
| Concurrency 与 render_node 重试冲突 | segment 失败重试时整段重新 render |

## 时间线

- B1 (本文档): 30 min
- B2 segment_dispatcher.py: 2 h
- B3 render_node 接 dispatcher: 2 h
- B4 ffmpeg_concat.py: 1 h
- B5 测试 + 重测: 1-2 h
- B6 README rev17: 30 min

合计: 7-8 小时开发 + 1-2 小时重测。今日完成 B1-B5，明日 B6 重测。
