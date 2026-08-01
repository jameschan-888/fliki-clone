"""rev35 P0-3: SlidingWindowLimiter 单测."""
import time
import unittest

from rate_limit import SlidingWindowLimiter


class SlidingWindowLimiterTest(unittest.TestCase):
    def test_allows_under_limit(self):
        limiter = SlidingWindowLimiter(max_hits=3, window_seconds=1.0)
        for _ in range(3):
            blocked, remaining = limiter.hit("ip-1")
            self.assertFalse(blocked)
        self.assertEqual(remaining, 0)

    def test_blocks_over_limit(self):
        limiter = SlidingWindowLimiter(max_hits=2, window_seconds=10.0)
        self.assertFalse(limiter.hit("ip-1")[0])
        self.assertFalse(limiter.hit("ip-1")[0])
        blocked, remaining = limiter.hit("ip-1")
        self.assertTrue(blocked)
        self.assertEqual(remaining, 0)

    def test_separate_keys_are_independent(self):
        limiter = SlidingWindowLimiter(max_hits=1, window_seconds=10.0)
        self.assertFalse(limiter.hit("ip-1")[0])
        self.assertTrue(limiter.hit("ip-1")[0])
        self.assertFalse(limiter.hit("ip-2")[0])

    def test_window_resets_after_expiry(self):
        limiter = SlidingWindowLimiter(max_hits=2, window_seconds=0.05)
        self.assertFalse(limiter.hit("ip-1")[0])
        self.assertFalse(limiter.hit("ip-1")[0])
        self.assertTrue(limiter.hit("ip-1")[0])
        time.sleep(0.07)
        self.assertFalse(limiter.hit("ip-1")[0])

    def test_reset_clears_bucket(self):
        limiter = SlidingWindowLimiter(max_hits=1, window_seconds=10.0)
        limiter.hit("ip-1")
        self.assertTrue(limiter.hit("ip-1")[0])
        limiter.reset("ip-1")
        self.assertFalse(limiter.hit("ip-1")[0])
