"""P1#5: render queue 并发上限 + retry helper 测试.

覆盖 10 个 test:
- MAX_CONCURRENT default 4
- get_max_concurrent() / get_active_count / get_active_slots / get_queue_stats
- acquire_slot 单个 / context manager 自动 release
- N+1 个 acquire 阻塞 (用小超时验证)
- run_with_retry 成功 / 失败 retry 1 次后成功 / 两次失败放弃
- exponential backoff 时序 (mock sleeper)
"""
import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, "backend")

import workers.render_queue as rq
from workers.render_retry import run_with_retry


class MaxConcurrentConfigTest(unittest.TestCase):
    "MAX_CONCURRENT 配置测试."

    def test_default_max_concurrent_is_4(self):
        "P1#5: default 4 (覆盖了 rev18 default 3)."
        os.environ.pop("RENDER_QUEUE_MAX_CONCURRENT", None)
        import importlib
        importlib.reload(rq)
        self.assertEqual(rq.MAX_CONCURRENT, 4)

    def test_get_max_concurrent_returns_configured(self):
        os.environ["RENDER_QUEUE_MAX_CONCURRENT"] = "7"
        try:
            import importlib
            importlib.reload(rq)
            self.assertEqual(rq.get_max_concurrent(), 7)
        finally:
            os.environ.pop("RENDER_QUEUE_MAX_CONCURRENT", None)
            import importlib
            importlib.reload(rq)

    def test_min_max_concurrent_is_1(self):
        "即使配 0 或负数, 也至少给 1 个 slot."
        os.environ["RENDER_QUEUE_MAX_CONCURRENT"] = "0"
        try:
            import importlib
            importlib.reload(rq)
            self.assertEqual(rq.MAX_CONCURRENT, 1)
        finally:
            os.environ.pop("RENDER_QUEUE_MAX_CONCURRENT", None)
            import importlib
            importlib.reload(rq)


class AcquireReleaseTest(unittest.TestCase):
    "Slot 获取/释放生命周期."

    def setUp(self):
        rq._ACTIVE_SLOTS.clear()

    def test_single_acquire_and_release(self):
        ok, msg = rq.acquire_slot("job-A", timeout=5)
        self.assertTrue(ok)
        self.assertEqual(rq.get_active_count(), 1)
        self.assertIn("job-A", rq.get_active_slots())
        rq.release_slot("job-A", "done")
        self.assertEqual(rq.get_active_count(), 0)

    def test_context_manager_auto_release(self):
        with rq.render_slot("job-CM"):
            self.assertEqual(rq.get_active_count(), 1)
        self.assertEqual(rq.get_active_count(), 0)

    def test_release_unknown_job_id_is_noop(self):
        "释放不存在的 job_id 不报错 (容错)."
        rq.release_slot("never-acquired")
        self.assertEqual(rq.get_active_count(), 0)

    def test_concurrency_limit_blocks_extra_acquire(self):
        "P1#5: N+1 个 acquire 在 max=N 时第 N+1 个必阻塞/超时."
        bound = rq.MAX_CONCURRENT
        acquired = []
        for i in range(bound):
            ok, _ = rq.acquire_slot("job-bulk-" + str(i), timeout=2)
            self.assertTrue(ok, "slot " + str(i) + " should acquire")
            acquired.append(i)
        t0 = time.time()
        ok, msg = rq.acquire_slot("job-extra", timeout=2)
        elapsed = time.time() - t0
        self.assertFalse(ok)
        self.assertIn("timeout", msg)
        self.assertGreaterEqual(elapsed, 1.5)
        for i in acquired:
            rq.release_slot("job-bulk-" + str(i))


class QueueStatsTest(unittest.TestCase):
    "get_queue_stats 返回 status 分布."

    def test_stats_after_acquire_release(self):
        rq._ACTIVE_SLOTS.clear()
        rq.acquire_slot("job-stats", timeout=5)
        stats = rq.get_queue_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn("running", stats)
        rq.release_slot("job-stats")


class RunWithRetryTest(unittest.TestCase):
    "P1#5: retry 1 次 + 指数退避 helper."

    def test_success_no_retry(self):
        fn = MagicMock(return_value=None)
        attempts, exc = run_with_retry(fn, max_retries=1, sleeper=lambda s: None)
        self.assertEqual(attempts, 1)
        self.assertIsNone(exc)
        self.assertEqual(fn.call_count, 1)

    def test_fail_then_succeed_retries_once(self):
        "第一次失败, 第二次成功, attempts=2."
        fn = MagicMock(side_effect=[RuntimeError("fail"), None])
        attempts, exc = run_with_retry(fn, max_retries=1, sleeper=lambda s: None)
        self.assertEqual(attempts, 2)
        self.assertIsNone(exc)
        self.assertEqual(fn.call_count, 2)

    def test_two_failures_gives_up(self):
        "max_retries=1 时连续失败 2 次放弃, 返回 last exception."
        exc1 = RuntimeError("first")
        exc2 = RuntimeError("second")
        fn = MagicMock(side_effect=[exc1, exc2])
        attempts, last = run_with_retry(fn, max_retries=1, sleeper=lambda s: None)
        self.assertEqual(attempts, 2)
        self.assertIs(last, exc2)
        self.assertEqual(fn.call_count, 2)

    def test_exponential_backoff_timing(self):
        "max_retries=2 时退避 1s + 2s = 3s 总 sleep, 第 3 次失败后放弃."
        sleeps = []
        fn = MagicMock(side_effect=RuntimeError("always"))
        attempts, last = run_with_retry(fn, max_retries=2, sleeper=lambda s: sleeps.append(s))
        self.assertEqual(attempts, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_max_retries_zero_no_retry(self):
        "max_retries=0 等同不重试, 一次失败即放弃."
        exc = RuntimeError("once")
        fn = MagicMock(side_effect=exc)
        attempts, last = run_with_retry(fn, max_retries=0, sleeper=lambda s: None)
        self.assertEqual(attempts, 1)
        self.assertIs(last, exc)
        self.assertEqual(fn.call_count, 1)

    def test_passes_args_and_kwargs(self):
        "args/kwargs 透传给 callable."
        fn = MagicMock(return_value=None)
        run_with_retry(fn, args=(1, 2), kwargs=dict(k="v"), max_retries=0, sleeper=lambda s: None)
        fn.assert_called_once_with(1, 2, k="v")


if __name__ == "__main__":
    unittest.main()
