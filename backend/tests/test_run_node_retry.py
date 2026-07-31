"""run_node 自动重试测试.

构造会失败的 work 函数:
  - 第一次抛错 → attempt=1, status=failed
  - 第二次抛错 → attempt=2, status=failed
  - 第三次成功 → attempt=3, status=success
"""
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class RunNodeRetryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = main.config["DB_PATH"]
        main.original_env = os.environ.get("FLIKI_NODE_MAX_ATTEMPTS")
        os.environ["FLIKI_NODE_MAX_ATTEMPTS"] = "3"
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "app.db")
        main.init_db()
        # 创建一个 workflow_run + workflow_node 让 run_node 找到
        conn = sqlite3.connect(main.config["DB_PATH"])
        try:
            run_id = "test-run-1"
            scene_id = "test-scene-1"
            conn.execute(
                "INSERT INTO workflow_drafts (id, title, source_script, language, status, version, created_at, updated_at) VALUES (?, ?, ?, ?, 'draft', 1, ?, ?)",
                ("draft-1", "t", "s", "zh-CN", "2025", "2025"),
            )
            conn.execute(
                "INSERT INTO workflow_runs (id, workflow_draft_id, status, progress, created_at, updated_at) VALUES (?, ?, 'queued', 0, ?, ?)",
                (run_id, "draft-1", "2025", "2025"),
            )
            conn.execute(
                "INSERT INTO workflow_nodes (id, workflow_run_id, scene_draft_id, node_type, status, progress, attempt, created_at, updated_at) VALUES (?, ?, ?, 'tts', 'queued', 0, 0, '2025', '2025')",
                ("node-1", run_id, scene_id),
            )
            conn.commit()
        finally:
            conn.close()
        # 屏蔽真实 sleep 让测试快
        self.sleep_patcher = patch("time.sleep", return_value=None)
        self.sleep_patcher.start()

    def tearDown(self):
        self.sleep_patcher.stop()
        main.config["DB_PATH"] = self.original_db_path
        if main.original_env is None:
            os.environ.pop("FLIKI_NODE_MAX_ATTEMPTS", None)
        else:
            os.environ["FLIKI_NODE_MAX_ATTEMPTS"] = main.original_env
        self.temp_dir.cleanup()

    def _fetch_node(self):
        conn = sqlite3.connect(main.config["DB_PATH"])
        try:
            row = conn.execute("SELECT status, attempt, message FROM workflow_nodes WHERE id='node-1'").fetchone()
            return {"status": row[0], "attempt": row[1], "message": row[2]}
        finally:
            conn.close()

    def test_succeeds_after_two_failures(self):
        from workflow_pipeline import run_node
        conn = sqlite3.connect(main.config["DB_PATH"])
        conn.row_factory = sqlite3.Row
        try:
            node = conn.execute("SELECT * FROM workflow_nodes WHERE id='node-1'").fetchone()
            calls = {"count": 0}
            def work():
                calls["count"] += 1
                if calls["count"] < 3:
                    raise RuntimeError(f"transient failure {calls['count']}")
                return ("mock", {"ok": True, "attempt_succeeded": calls["count"]})
            result = run_node(conn, node, work)
            self.assertEqual(result["attempt_succeeded"], 3)
            state = self._fetch_node()
            self.assertEqual(state["status"], "success")
            self.assertEqual(state["attempt"], 3)
        finally:
            try: conn.close()
            except Exception: pass

    def test_gives_up_after_max_attempts(self):
        from workflow_pipeline import run_node
        conn = sqlite3.connect(main.config["DB_PATH"])
        conn.row_factory = sqlite3.Row
        try:
            node = conn.execute("SELECT * FROM workflow_nodes WHERE id='node-1'").fetchone()
            def always_fail():
                raise RuntimeError("persistent failure")
            with self.assertRaises(RuntimeError) as cm:
                run_node(conn, node, always_fail)
            self.assertIn("persistent failure", str(cm.exception))
            state = self._fetch_node()
            self.assertEqual(state["status"], "failed")
            self.assertEqual(state["attempt"], 3)
            self.assertIn("after 3 attempts", state["message"])
        finally:
            try: conn.close()
            except Exception: pass

    def test_skips_when_already_success(self):
        from workflow_pipeline import run_node
        conn = sqlite3.connect(main.config["DB_PATH"])
        conn.row_factory = sqlite3.Row
        try:
            # 把节点改成 success
            conn.execute("UPDATE workflow_nodes SET status='success', result_json=? WHERE id='node-1'",
                         ('{"cached": true}',))
            conn.commit()
            node = conn.execute("SELECT * FROM workflow_nodes WHERE id='node-1'").fetchone()
            calls = {"count": 0}
            def work():
                calls["count"] += 1
                return ("mock", {"ok": True})
            result = run_node(conn, node, work)
            self.assertEqual(calls["count"], 0, "work() should not be invoked when node is already success")
            self.assertEqual(result, {"cached": True})
        finally:
            try: conn.close()
            except Exception: pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
