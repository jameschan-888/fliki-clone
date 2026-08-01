# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from workflow_pipeline import execute_pipeline


SCENE_ID = "scene-p5d7"


class _CaptureRender:
    def __init__(self):
        self.body = None
        self.calls = 0

    def __call__(self, body, _background_tasks=None):
        self.calls += 1
        self.body = body
        return {"jobId": body.playback_id}


class _RenderBody:
    def __init__(self, playback_id, props_path, **kwargs):
        self.playback_id = playback_id
        self.props_path = props_path
        self.kwargs = kwargs


class P5D7AvatarLayoutTest(unittest.TestCase):
    """P5D-7 closes the loop: provider avatar_layout config reaches props.json."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "app.db")
        main.init_db()
        self.run_dir = Path(self.temp_dir.name) / "fake"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.voice_file = self.run_dir / "voice.mp3"
        self.stock_file = self.run_dir / "stock.mp4"
        self.music_file = self.run_dir / "music.mp3"
        for p in (self.voice_file, self.stock_file, self.music_file):
            p.write_bytes(b"FAKE-" + p.suffix.encode("utf-8"))
        # seed provider row
        with main.get_db() as conn:
            from provider_config import seed_runtime_providers
            seed_runtime_providers(conn)
            conn.close()

    def tearDown(self):
        main.config["DB_PATH"] = self.original_db_path
        try:
            self.temp_dir.cleanup()
        except (PermissionError, OSError):
            pass

    def _seed_draft(self, run_id):
        with main.get_db() as conn:
            ts = "2026-07-24T00:00:00+00:00"
            conn.execute(
                "INSERT INTO workflow_drafts (id,title,source_script,language,status,version,created_at,updated_at,confirmed_at,confirmed_snapshot_json) "
                "VALUES (?, ?, ?, ?, 'confirmed', 1, ?, ?, ?, ?)",
                (
                    "draft-p5d7", "Layout test", "Script.", "zh-CN",
                    ts, ts, ts,
                    json.dumps({
                        "id": "draft-p5d7",
                        "title": "Layout test",
                        "language": "zh-CN",
                        "status": "confirmed",
                        "scenes": [{
                            "id": SCENE_ID, "position": 0, "title": "opening",
                            "narration": "Hello", "visual_intent": "sky",
                            "subtitle": "Hello", "duration_seconds": 3.0,
                            "voice": "zh-CN-XiaoxiaoNeural",
                        }],
                    }, ensure_ascii=False),
                ),
            )
            conn.execute(
                "INSERT INTO scene_drafts (id,workflow_draft_id,position,title,narration,visual_intent,subtitle,duration_seconds,voice,created_at,updated_at) "
                "VALUES (?, ?, 0, 'opening', 'Hello', 'sky', 'Hello', 3.0, 'zh-CN-XiaoxiaoNeural', ?, ?)",
                (SCENE_ID, "draft-p5d7", ts, ts),
            )
            conn.execute(
                "INSERT INTO workflow_runs (id,workflow_draft_id,status,progress,created_at,updated_at) VALUES (?, 'draft-p5d7', 'queued', 0, ?, ?)",
                (run_id, ts, ts),
            )
            conn.commit()
            conn.close()

    def _set_avatar_layout(self, layout_dict):
        with main.get_db() as conn:
            if layout_dict is None:
                # strip avatar_layout key
                row = conn.execute(
                    "SELECT config_json FROM provider_configs WHERE category='avatar' AND name='wav2lip_onnx'"
                ).fetchone()
                cfg = json.loads(row["config_json"])
                cfg.pop("avatar_layout", None)
                conn.execute(
                    "UPDATE provider_configs SET config_json=? WHERE category='avatar' AND name='wav2lip_onnx'",
                    (json.dumps(cfg),),
                )
            else:
                row = conn.execute(
                    "SELECT config_json FROM provider_configs WHERE category='avatar' AND name='wav2lip_onnx'"
                ).fetchone()
                cfg = json.loads(row["config_json"])
                cfg["avatar_layout"] = layout_dict
                conn.execute(
                    "UPDATE provider_configs SET config_json=? WHERE category='avatar' AND name='wav2lip_onnx'",
                    (json.dumps(cfg),),
                )
            conn.commit()
            conn.close()

    def _run_pipeline(self, run_id):
        capture = _CaptureRender()
        fake_bt = type("BT", (), {"add_task": staticmethod(lambda *a, **kw: None)})()
        from pathlib import Path as _P3
        backend_path = str(_P3(__file__).resolve().parent.parent)

        def fake_voice(text, destination, *, voice=None, language="zh"):
            return {"provider": "edge_tts", "voice": voice or "zh-CN-XiaoxiaoNeural", "local_path": str(self.voice_file)}

        def fake_stock(intent, destination):
            return {"provider": "pexels", "local_path": str(self.stock_file), "source_url": "https://x/y"}

        def fake_music(query, destination):
            return {"provider": "freesound", "local_path": str(self.music_file), "source_url": "https://f/t"}

        with patch("workflow_pipeline.synthesize_tts_with_fallback", side_effect=fake_voice), \
             patch("workflow_pipeline.fetch_with_fallback", side_effect=fake_stock), \
             patch("workflow_pipeline.fetch_music_with_fallback", side_effect=fake_music), \
             patch("workflow_pipeline.media_duration", return_value=1.0), \
             patch("workflow_pipeline.render_segments_dispatch", return_value=(True, "ok", "fake-job-id")):
            execute_pipeline(run_id, main.get_db, capture, _RenderBody, fake_bt)

        # P3 修复: execute_pipeline 调 dispatch_segments 不调 capture; capture.body 改成指向真实 props_path
        props_path = _P3(backend_path) / "data" / "props" / f"workflow-{run_id}.json"
        capture.body = type("Body", (), {"props_path": str(props_path), "playback_id": run_id})()
        return capture

    def _props(self, capture):
        return json.loads(Path(capture.body.props_path).read_text(encoding="utf-8"))

    def test_avatar_layout_from_provider_config_writes_to_props(self):
        self._seed_draft(run_id="run-p5d7-1")
        target = {
            "position": "top-left",
            "widthPx": 240,
            "heightPx": 180,
            "shape": "circle",
            "showLabel": True,
            "borderColor": "#FFD700",
        }
        self._set_avatar_layout(target)
        capture = self._run_pipeline("run-p5d7-1")
        props = self._props(capture)
        self.assertIn("avatarLayout", props)
        self.assertEqual(props["avatarLayout"], target)

    def test_avatar_layout_missing_writes_none(self):
        self._seed_draft(run_id="run-p5d7-2")
        self._set_avatar_layout(None)
        capture = self._run_pipeline("run-p5d7-2")
        props = self._props(capture)
        self.assertIn("avatarLayout", props)
        self.assertIsNone(props["avatarLayout"])

    def test_avatar_layout_non_dict_writes_none(self):
        self._seed_draft(run_id="run-p5d7-3")
        # inject non-dict avatar_layout
        with main.get_db() as conn:
            row = conn.execute(
                "SELECT config_json FROM provider_configs WHERE category='avatar' AND name='wav2lip_onnx'"
            ).fetchone()
            cfg = json.loads(row["config_json"])
            cfg["avatar_layout"] = "not-a-dict"
            conn.execute(
                "UPDATE provider_configs SET config_json=? WHERE category='avatar' AND name='wav2lip_onnx'",
                (json.dumps(cfg),),
            )
            conn.commit()
            conn.close()
            capture = self._run_pipeline("run-p5d7-3")
            props = self._props(capture)
            self.assertIn("avatarLayout", props)
            self.assertIsNone(props["avatarLayout"])

    def test_avatar_layout_corrupt_config_json_writes_none(self):
        self._seed_draft(run_id="run-p5d7-4")
        with main.get_db() as conn:
            conn.execute(
                "UPDATE provider_configs SET config_json=? WHERE category='avatar' AND name='wav2lip_onnx'",
                ("{not valid json",),
            )
            conn.commit()
            conn.close()
            capture = self._run_pipeline("run-p5d7-4")
            props = self._props(capture)
            self.assertIn("avatarLayout", props)
            self.assertIsNone(props["avatarLayout"])


if __name__ == "__main__":
    unittest.main()
