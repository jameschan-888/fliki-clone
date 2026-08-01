"""rev35 P0-3: 简单内存滑动窗口限速.

按 (key, window_seconds, max_hits) 维护 deque, 命中超过 max_hits 返 True.
- 多线程 (uvicorn 单进程, worker thread) 安全: 用 threading.Lock.
- 仅供 /auth/login 与 /auth/register; 不替代 nginx/CDN 限流.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque


class SlidingWindowLimiter:
    def __init__(self, max_hits: int, window_seconds: float) -> None:
        self._max_hits = max_hits
        self._window = float(window_seconds)
        self._buckets: dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> tuple[bool, int]:
        """记录一次命中; 返 (是否被限流, 剩余配额)."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and now - bucket[0] > self._window:
                bucket.popleft()
            if len(bucket) >= self._max_hits:
                return True, 0
            bucket.append(now)
            return False, self._max_hits - len(bucket)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)
