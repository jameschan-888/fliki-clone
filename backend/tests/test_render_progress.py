import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import main


class RenderProgressTest(unittest.TestCase):
    def test_timeout_callback_marks_timeout_and_terminates_tree(self):
        expire_process = getattr(main, "expire_render_process", None)
        self.assertIsNotNone(expire_process)

        timed_out = main.threading.Event()
        fake_process = object()
        with patch.object(main, "terminate_process_tree", return_value=True) as terminate:
            self.assertTrue(expire_process(fake_process, timed_out))
        self.assertTrue(timed_out.is_set())
        terminate.assert_called_once_with(fake_process)
    def test_cancel_endpoint_marks_job_and_terminates_registered_process(self):
        cancel_body = getattr(main, "RenderCancelBody", None)
        cancel_render = getattr(main, "render_cancel", None)
        self.assertIsNotNone(cancel_body)
        self.assertIsNotNone(cancel_render)

        with tempfile.TemporaryDirectory() as temp_dir:
            original_db_path = main.config["DB_PATH"]
            main.config["DB_PATH"] = str(Path(temp_dir) / "app.db")
            try:
                main.init_db()
                conn = sqlite3.connect(main.config["DB_PATH"])
                conn.execute(
                    """
                    INSERT INTO render_jobs
                    (_id, playback_id, status, progress, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ("job-1", "playback-1", "processing", 44, "2026-07-23T00:00:00Z"),
                )
                conn.commit()
                conn.close()

                fake_process = object()
                main.ACTIVE_RENDER_PROCESSES["job-1"] = fake_process
                with patch.object(main, "terminate_process_tree", return_value=True) as terminate:
                    result = cancel_render(cancel_body(job_id="job-1"))
                terminate.assert_called_once_with(fake_process)

                self.assertEqual(result["status"], "cancelled")
                self.assertTrue(result["terminated"])
                conn = sqlite3.connect(main.config["DB_PATH"])
                status, message = conn.execute(
                    "SELECT status, message FROM render_jobs WHERE _id=?", ("job-1",)
                ).fetchone()
                conn.close()
                self.assertEqual((status, message), ("failed", "Cancelled by user"))
            finally:
                main.ACTIVE_RENDER_PROCESSES.pop("job-1", None)
                main.config["DB_PATH"] = original_db_path
    def test_windows_termination_kills_entire_process_tree(self):
        terminate_tree = getattr(main, "terminate_process_tree", None)
        self.assertIsNotNone(terminate_tree)

        class FakeProcess:
            pid = 4321

            @staticmethod
            def poll():
                return None

        with patch.object(main.platform, "system", return_value="Windows"):
            with patch.object(main.subprocess, "run") as run:
                self.assertTrue(terminate_tree(FakeProcess()))

        run.assert_called_once_with(
            ["taskkill", "/PID", "4321", "/T", "/F"],
            capture_output=True,
            text=True,
        )
    def test_cancel_marks_active_job_failed_with_explicit_message(self):
        mark_cancelled = getattr(main, "mark_render_cancelled", None)
        self.assertIsNotNone(mark_cancelled)

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE render_jobs (
                _id TEXT PRIMARY KEY,
                status TEXT,
                progress INTEGER,
                message TEXT,
                finished_at TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO render_jobs (_id, status, progress) VALUES (?, ?, ?)",
            ("job-1", "processing", 44),
        )

        self.assertTrue(mark_cancelled(conn, "job-1"))
        status, progress, message, finished_at = conn.execute(
            "SELECT status, progress, message, finished_at FROM render_jobs WHERE _id=?",
            ("job-1",),
        ).fetchone()
        self.assertEqual(status, "failed")
        self.assertEqual(progress, 44)
        self.assertEqual(message, "Cancelled by user")
        self.assertIsNotNone(finished_at)
        conn.close()
    def test_worker_progress_keeps_job_processing_until_completion(self):
        apply_progress = getattr(main, "apply_worker_progress", None)
        self.assertIsNotNone(apply_progress)

        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE render_jobs (_id TEXT PRIMARY KEY, status TEXT, progress INTEGER)"
        )
        conn.execute(
            "INSERT INTO render_jobs (_id, status, progress) VALUES (?, ?, ?)",
            ("job-1", "processing", 0),
        )

        self.assertTrue(apply_progress(conn, "job-1", "[render-progress] 93"))
        self.assertEqual(
            conn.execute(
                "SELECT status, progress FROM render_jobs WHERE _id=?", ("job-1",)
            ).fetchone(),
            ("processing", 93),
        )
        self.assertTrue(apply_progress(conn, "job-1", "[render-progress] 100"))
        self.assertEqual(
            conn.execute(
                "SELECT status, progress FROM render_jobs WHERE _id=?", ("job-1",)
            ).fetchone(),
            ("processing", 100),
        )
        self.assertFalse(apply_progress(conn, "job-1", "ordinary worker output"))
        conn.close()


if __name__ == "__main__":
    unittest.main()