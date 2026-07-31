# 阶段 C 云端 renderer 架构 (rev24)

## 目标
在多租户 / 多 draft 场景下，渲染不被单机的 Chrome 进程池拖死；遇到 5min/15min
长视频时，能切到云端（Remotion Lambda / GCP / 自建 GPU）而无需改业务层。

## 关键模块
- `backend/workers/cloud_renderer.py`
  - `CloudProvider` 抽象：`submit` / `poll` / `download` 三接口
  - `MockProvider`：默认离线实现，产出 placeholder mp4
  - `LambdaProvider`：通过 `CLOUD_LAMBDA_URL` 调 Remotion Lambda 风格
    `POST /renders`、`GET /renders/{id}`、`download outputUrl`
  - `get_provider(name=None)`：name 走 cache，env `CLOUD_RENDER_PROVIDER`
    默认 mock
  - `run_provider_render(...)`：把老的 `run_cloud_render_job` 调用面收敛到统一
    `(ok, msg, output_path, started, finished)` 返回值；现有 `main.run_render_job`
    继续走 legacy mock 路径保持兼容

- `backend/workers/segment_dispatcher.py`
  - 新增 `_needs_chrome_slot(renderer)`：cloud / lambda / mock 不再消耗本地
    Chrome 槽位
  - 新增 `ffmpeg_concat_with_retry`：ffmpeg 拼接短暂文件锁时的有界重试
  - `dispatch_segments` 新增 `max_concurrent` 参数 + `RENDER_SEGMENT_MAX_CONCURRENT`
    环境变量；本机默认 K 段全开，但云端 provider 可被限到 N
  - 工作线程改为 `_sem = BoundedSemaphore(max_concurrent)`；每个 seg worker
    调 `_run_segment`，由它决定是否进入 Chrome render slot

## 端到端协议
1. 业务 (`workflow_pipeline.execute_pipeline`) 不再关心 provider 细节，
   一律 `render_segments_dispatch(renderer=…)`
2. dispatcher 根据 `RENDER_PROVIDER` 路由到 local / cloud
3. cloud 路径下，每段由云端 producer 异步跑，主线程只 poll
4. chrome slot（`render_queue.MAX_CONCURRENT`）只服务于真本地渲染

## 环境变量
- `CLOUD_RENDER_PROVIDER`：mock（默认）| lambda
- `CLOUD_LAMBDA_URL`：Lambda 网关根地址
- `CLOUD_LAMBDA_AUTH`：Bearer token（可选）
- `CLOUD_LAMBDA_POLL_SECONDS`：默认 5
- `CLOUD_LAMBDA_TIMEOUT`：默认 5400s
- `RENDER_SEGMENT_MAX_CONCURRENT`：云端段渲染额外限流（默认 = K）
- `RENDER_FORCE_CHROME_SLOT=1`：测试/排错时强制走本地 slot

## 单元测试
- `tests/test_cloud_provider.py`：9 个 case，覆盖 mock/lambda 协议、
  unknown provider、payload 注入
- `tests/test_segment_dispatcher_stage_c.py`：6 个 case，覆盖
  - chrome slot 决策（cloud/local）
  - ffmpeg 重试成功 / 失败
  - dispatch 4 段 cloud 全过
  - `max_concurrent=2` 限制峰值并发

## 切换到真 Lambda
1. `CLOUD_RENDER_PROVIDER=lambda`
2. `CLOUD_LAMBDA_URL=https://your-lambda.example.com`
3. `CLOUD_LAMBDA_AUTH=<token>`
4. 不需要改业务代码；dispatcher 会自动走 Lambda provider

## 已知短板
- `LambdaProvider.download` 当前不重试 / 不分片（云端超过 1GB 输出可能
  失败；后续加 Range 续传）
- `get_provider` 缓存 key 不区分 props 内容；同一 provider 多次切换需
  设 `_PROVIDER_CACHE_OVERRIDE=True`（默认 False）
- mock 输出是 testsrc 720p，对外观没有参考价值；真 Lambda 接入后这层
  会被天然绕过
