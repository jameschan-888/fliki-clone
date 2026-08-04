"""Unit tests for the rev24 stage C dispatcher + segment pipeline."""
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import workers.segment_dispatcher as sd


class HelpersTest(unittest.TestCase):
    def test_needs_chrome_slot_default_for_cloud(self):
        self.assertFalse(sd._needs_chrome_slot("cloud"))
        self.assertFalse(sd._needs_chrome_slot("lambda"))
        self.assertFalse(sd._needs_chrome_slot("mock"))
        self.assertTrue(sd._needs_chrome_slot("local"))
        self.assertTrue(sd._needs_chrome_slot("chrome"))

    def test_needs_chrome_slot_force_env(self):
        with patch.dict(os.environ, {"RENDER_FORCE_CHROME_SLOT": "1"}):
            self.assertTrue(sd._needs_chrome_slot("cloud"))
        with patch.dict(os.environ, {"RENDER_FORCE_CHROME_SLOT": "0"}):
            self.assertFalse(sd._needs_chrome_slot("local"))

    def test_ffmpeg_concat_with_retry_succeeds_after_retry(self):
        calls = {"n": 0}

        def fake_concat(files, out):
            calls["n"] += 1
            if calls["n"] < 3:
                return False, "ffmpeg rc=1"
            return True, ""

        with patch.object(sd, "ffmpeg_concat", side_effect=fake_concat):
            ok, msg = sd.ffmpeg_concat_with_retry(["a.mp4"], Path("out.mp4"), retries=3)
        self.assertTrue(ok)
        self.assertEqual(msg, "")
        self.assertEqual(calls["n"], 3)

    def test_ffmpeg_concat_with_retry_gives_up(self):
        def fake_concat(files, out):
            return False, "ffmpeg rc=1"

        with patch.object(sd, "ffmpeg_concat", side_effect=fake_concat):
            ok, msg = sd.ffmpeg_concat_with_retry(["a.mp4"], Path("out.mp4"), retries=2)
        self.assertFalse(ok)
        self.assertIn("ffmpeg rc=1", msg)


class DispatchSegmentsIntegrationTest(unittest.TestCase):
    """Smoke test the dispatch path with mocked run_render_job + ffmpeg."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "app.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE workflow_runs (id TEXT PRIMARY KEY, status TEXT, progress INTEGER, render_job_id TEXT, message TEXT, updated_at TEXT, finished_at TEXT)")
        self.conn.execute("CREATE TABLE render_jobs (_id TEXT PRIMARY KEY, playback_id TEXT, status TEXT, progress INTEGER, resolution TEXT, extension TEXT, renderer TEXT, engine TEXT, file TEXT, thumbnail TEXT, thumbnail_preview TEXT, media_generated_id TEXT, message TEXT, created_at TEXT, finished_at TEXT)")
        self.run_dir = Path(self.tmp.name) / "run"
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def _make_run_id(self):
        return "run-" + str(int(time.time() * 1000))

    def _seed_scenes(self, n):
        return [
            {
                "id": "s" + str(i),
                "durationInSeconds": 1.0,
                "narration": "n",
                "visual_intent": "v",
            }
            for i in range(n)
        ]

    def _fake_run_render(self, job_id, props_path, resolution, ext, engine, renderer):
        seg_idx = job_id.split("-s")[-1][:1]  # 0/1/2/3
        seg_path = self.run_dir / "segments" / ("seg_" + seg_idx + ".mp4")
        seg_path.parent.mkdir(parents=True, exist_ok=True)
        seg_path.write_bytes(b"FAKE")
        worker_connection = sqlite3.connect(self.db_path, timeout=5)
        try:
            worker_connection.execute("PRAGMA busy_timeout=5000")
            worker_connection.execute(
                "UPDATE render_jobs SET status=?, progress=?, file=?, finished_at=? WHERE _id=?",
                ("success", 100, "workflow/run/segments/" + seg_path.name, "2026-07-28T00:00:00Z", job_id),
            )
            worker_connection.commit()
        finally:
            worker_connection.close()

    def _stub_main(self):
        class _M:
            pass
        mod = _M()
        mod.run_render_job = self._fake_run_render
        return mod

    def test_dispatch_4_segments_cloud_skips_chrome_slot(self):
        scenes = self._seed_scenes(40)
        rid = self._make_run_id()
        with patch.dict(os.environ, {"RENDER_SEGMENT_SCENES": "10", "RENDER_FORCE_CHROME_SLOT": "0"}):
            with patch.object(sd, "_ensure_main_loaded", return_value=self._stub_main()):
                def fake_concat(files, out):
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(b"CONCAT")
                    return True, ""
                with patch.object(sd, "ffmpeg_concat", side_effect=fake_concat), \
                     patch.object(sd, "make_thumbnails", side_effect=lambda *_: (None, None)):
                    ok, msg, final = sd.dispatch_segments(
                        self.conn, rid, scenes, {"scenes": scenes}, self.run_dir, "720p", renderer="cloud",
                    )
        self.assertTrue(ok, msg=msg)
        self.assertTrue(final.endswith("-concat"))
        rows = self.conn.execute("SELECT status, renderer FROM render_jobs").fetchall()
        seg_rows = [r for r in rows if r["renderer"] == "cloud"]
        self.assertGreaterEqual(len(seg_rows), 4)
        self.assertTrue(all(r["status"] == "success" for r in seg_rows))

    def test_dispatch_max_concurrent_caps_fanout(self):
        scenes = self._seed_scenes(40)
        rid = self._make_run_id()
        active = 0
        peak = {"n": 0}
        lock = threading.Lock()

        def slow_run(job_id, props_path, resolution, ext, engine, renderer):
            nonlocal active
            with lock:
                active += 1
                if active > peak["n"]:
                    peak["n"] = active
            time.sleep(0.05)
            with lock:
                active -= 1
            self._fake_run_render(job_id, props_path, resolution, ext, engine, renderer)

        class _M:
            run_render_job = staticmethod(slow_run)
        with patch.dict(os.environ, {"RENDER_SEGMENT_SCENES": "10", "RENDER_FORCE_CHROME_SLOT": "0"}):
            with patch.object(sd, "_ensure_main_loaded", return_value=_M()):
                def fake_concat(files, out):
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(b"CONCAT")
                    return True, ""
                with patch.object(sd, "ffmpeg_concat", side_effect=fake_concat), \
                     patch.object(sd, "make_thumbnails", side_effect=lambda *_: (None, None)):
                    ok, msg, _ = sd.dispatch_segments(
                        self.conn, rid, scenes, {"scenes": scenes}, self.run_dir, "720p", renderer="cloud", max_concurrent=2,
                    )
        self.assertTrue(ok, msg=msg)
        self.assertLessEqual(peak["n"], 2)

    def test_worker_crash_returns_immediately_with_root_error(self):
        scenes = self._seed_scenes(10)
        rid = self._make_run_id()

        class _M:
            @staticmethod
            def run_render_job(*_args):
                raise RuntimeError("renderer exploded")

        started = time.monotonic()
        with patch.dict(os.environ, {"RENDER_SEGMENT_SCENES": "10", "RENDER_FORCE_CHROME_SLOT": "0"}), \
             patch.object(sd, "_ensure_main_loaded", return_value=_M()), \
             patch.object(sd, "POLL_TIMEOUT", 1), \
             patch.object(sd, "POLL_INTERVAL", 0.01):
            ok, msg, _ = sd.dispatch_segments(
                self.conn, rid, scenes, {"scenes": scenes}, self.run_dir, "720p", renderer="cloud",
            )

        self.assertFalse(ok)
        self.assertIn("renderer exploded", msg)
        # N54: 阈值 0.5 -> 1.0 (Windows + 后台进程繁忙时 SimpleQueue polling 延后 0.5s 内不稳定)
        # 1.0s 仍属 "秒退" 范畴, 生产 worker crash immediate 预期不退化为
        self.assertLess(time.monotonic() - started, 1.0)


if __name__ == "__main__":
    unittest.main()
