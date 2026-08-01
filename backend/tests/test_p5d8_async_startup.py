"""P5D-8：后端 startup 异步化"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main as main_mod
from routers import startup as startup_mod


class AsyncStartupTests(unittest.TestCase):
    def test_status_initial_pending(self):
        # 模块加载时状态应为 pending（后台线程未启动）
        s = startup_mod._startup_diagnostic_status
        self.assertIn("state", s)
        self.assertIn("finished_at", s)
        self.assertIn("error", s)

    def test_background_diagnostic_runs(self):
        """后台线程同步执行完成且更新状态（_background_diagnostic 不阻塞）"""
        import time
        calls = {"count": 0, "report": {"warnings": [], "capabilities": {}}}
        with patch.object(startup_mod, "write_startup_diagnostic", return_value=calls["report"]):
            t0 = time.time()
            startup_mod._diagnose_sync()
            dur = time.time() - t0
            self.assertLess(dur, 1.0, "_background_diagnostic should be fast under test")
        status = startup_mod._startup_diagnostic_status
        self.assertEqual(status["state"], "ready")
        self.assertIsNotNone(status["finished_at"])

    def test_background_diagnostic_handles_error(self):
        with patch.object(startup_mod, "write_startup_diagnostic", return_value={"error": "boom"}):
            startup_mod._diagnose_sync()
        status = startup_mod._startup_diagnostic_status
        self.assertEqual(status["state"], "error")
        self.assertEqual(status["error"], "boom")

    def test_background_diagnostic_handles_exception(self):
        with patch.object(startup_mod, "write_startup_diagnostic", side_effect=RuntimeError("crash")):
            startup_mod._diagnose_sync()
        status = startup_mod._startup_diagnostic_status
        self.assertEqual(status["state"], "error")
        self.assertEqual(status["error"], "crash")


if __name__ == "__main__":
    unittest.main()