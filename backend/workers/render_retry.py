"""P1#5: render retry helper (独立模块, 不动 render_manager).

提供 run_with_retry(callable, max_retries=1) -> (attempts, exception):
- 第一次失败时退避 1s 重试
- 第二次失败时退避 2s ... (max_retries=1 实际只退避 1s 一次)
- 指数退避: base_seconds * (2 ** attempt)
- 可被业务代码 (routers/render.py) 包 background task 复用

不动 schema / render_manager.run_render_job, 避免破坏现有 569 个 test.
仅做 retry 编排; 业务层 run_render_job 内部仍 try/except 兜住所有异常,
retry 通过 callable 重复执行达到重跑效果.
"""
import logging
import time

log = logging.getLogger("render_retry")

DEFAULT_BASE_BACKOFF = 1.0
DEFAULT_MAX_RETRIES = 1


def run_with_retry(callable_fn, args=None, kwargs=None, max_retries=1, base_backoff=DEFAULT_BASE_BACKOFF, sleeper=time.sleep):
    """Run callable with exponential backoff retry on exception.

    callable_fn: zero-arg-or-args callable. If args/kwargs provided, called as fn(*args, **kwargs).
    max_retries: int, 0 = no retry (single attempt), 1 = retry once after first fail.
    base_backoff: float, first retry waits this many seconds; subsequent retries * 2.
    sleeper: injectable sleep function for test.

    Returns: (attempts: int, last_exception: Exception|None)
    - attempts = number of times fn was invoked
    - last_exception = exception from last attempt, or None if all succeeded
    """
    attempts = 0
    last_exc = None
    bound = max_retries + 1  # total attempts
    for attempt in range(bound):
        attempts += 1
        try:
            if args is None and kwargs is None:
                callable_fn()
            else:
                callable_fn(*(args or ()), **(kwargs or {}))
            return attempts, None
        except Exception as exc:
            last_exc = exc
            log.warning("render_retry: attempt %d/%d failed: %s", attempt + 1, bound, exc)
            if attempt < max_retries:
                backoff = base_backoff * (2 ** attempt)
                sleeper(backoff)
    return attempts, last_exc
