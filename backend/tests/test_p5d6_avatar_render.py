import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from workflow_pipeline import execute_pipeline


AVATAR_UUID = "11111111-2222-3333-4444-555555555555"


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


class P5D6AvatarRenderTest(unittest.TestCase):
    """P5D-6 closes the loop from P5D-5: avatar fields actually reach Remotion props.json."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "app.db")
        main.init_db()
        self.run_dir = Path(self.temp_dir.name) / "fake"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.voice_file = self.run_dir / "voice.mp3"
        self.stock_file = self.run_dir / "stock.mp4"
        self.avatar_file = self.run_dir / "avatar.mp4"
        self.music_file = self.run_dir / "music.mp3"
        for p in (self.voice_file, self.stock_file, self.avatar_file, self.music_file):
            p.write_bytes(b"FAKE-" + p.suffix.encode("utf-8"))

    def tearDown(self):
        main.config["DB_PATH"] = self.original_db_path
        try:
            self.temp_dir.cleanup()
        except (PermissionError, OSError):
            pass

    def _seed_draft_with_avatar(self, run_id, scene_id, has_avatar):
        with main.get_db() as conn:
            ts = "2026-07-24T00:00:00+00:00"
            avatar_value = f"avatar:{AVATAR_UUID}" if has_avatar else None
            conn.execute(
                "INSERT INTO workflow_drafts (id,title,source_script,language,status,version,created_at,updated_at,confirmed_at,confirmed_snapshot_json) "
                "VALUES (?, ?, ?, ?, 'confirmed', 1, ?, ?, ?, ?)",
                (
                    "draft",
                    "Avatar render",
                    "Script.",
                    "zh-CN",
                    ts,
                    ts,
                    ts,
                    json.dumps({
                        "id": "draft",
                        "title": "Avatar render",
                        "language": "zh-CN",
                        "status": "confirmed",
                        "scenes": [{
                            "id": scene_id, "position": 0, "title": "opening",
                            "narration": "Hello", "visual_intent": "sky",
                            "subtitle": "Hello", "duration_seconds": 3.0,
                            "voice": "zh-CN-XiaoxiaoNeural", "avatar": avatar_value,
                        }],
                    }, ensure_ascii=False),
                ),
            )
            conn.execute(
                "INSERT INTO scene_drafts (id,workflow_draft_id,position,title,narration,visual_intent,subtitle,duration_seconds,voice,avatar,created_at,updated_at) "
                "VALUES (?, ?, 0, 'opening', 'Hello', 'sky', 'Hello', 3.0, 'zh-CN-XiaoxiaoNeural', ?, ?, ?)",
                (scene_id, "draft", avatar_value, ts, ts),
            )
            conn.execute(
                "INSERT INTO workflow_runs (id,workflow_draft_id,status,progress,created_at,updated_at) VALUES (?, 'draft', 'queued', 0, ?, ?)",
                (run_id, ts, ts),
            )
            conn.commit()
            conn.close()

    def _run_pipeline(self, run_id):
        capture = _CaptureRender()
        fake_bt = type("BT", (), {"add_task": staticmethod(lambda *a, **kw: None)})()
        from pathlib import Path as _P2
        backend_path = str(_P2(__file__).resolve().parent.parent)

        def fake_voice(text, destination, *, voice=None, language="zh"):
            return {"provider": "edge_tts", "voice": voice or "zh-CN-XiaoxiaoNeural", "local_path": str(self.voice_file)}

        def fake_stock(intent, destination):
            return {"provider": "pexels", "local_path": str(self.stock_file), "source_url": "https://x/y"}

        def fake_avatar(scene, audio_source, destination, connection=None, config=None):
            return {
                "provider": "wav2lip_onnx",
                "mode": "static_avatar",
                "fallback_used": True,
                "model_present": False,
                "elapsed_seconds": 0.1,
                "local_path": str(self.avatar_file),
                "avatar_uuid": AVATAR_UUID,
                "avatar_name": "test_avatar",
            }

        def fake_music(query, destination):
            return {"provider": "freesound", "local_path": str(self.music_file), "source_url": "https://f/t"}

        with patch("workflow_pipeline.synthesize_tts_with_fallback", side_effect=fake_voice), \
             patch("workflow_pipeline.fetch_with_fallback", side_effect=fake_stock), \
             patch("workflow_pipeline.synthesize_scene_avatar", side_effect=fake_avatar), \
             patch("workflow_pipeline.fetch_music_with_fallback", side_effect=fake_music), \
             patch("workflow_pipeline.media_duration", return_value=1.0), \
             patch("workflow_pipeline.render_segments_dispatch", return_value=(True, "ok", "fake-job-id")):
            # mock_music_cls removed (fetch_music_with_fallback mocked above)
            execute_pipeline(run_id, main.get_db, capture, _RenderBody, fake_bt)

        # P3 修复: execute_pipeline 不再调 render_create (用 dispatch_segments), capture 永远 0 calls.
        # 改为: 直接从 execute_pipeline 写的 props_path 构造 capture.body, 让原断言 capture.body.props_path 仍工作.
        from pathlib import Path as _P
        props_path = _P(backend_path) / "data" / "props" / f"workflow-{run_id}.json"
        capture.body = type("Body", (), {"props_path": str(props_path), "playback_id": run_id})()
        return capture

    def test_execute_pipeline_writes_avatar_fields_to_props(self):
        self._seed_draft_with_avatar(run_id="run-1", scene_id="scene-1", has_avatar=True)
        capture = self._run_pipeline("run-1")
        # P3 修复: execute_pipeline 调 dispatch_segments, 不调 capture; capture.calls 永远 0.
        # 已改为 _run_pipeline 内部从 props_path 构造 capture.body.
        self.assertTrue(capture.body.props_path.endswith(".json"))
        self.assertTrue(Path(capture.body.props_path).is_file())
        props = json.loads(Path(capture.body.props_path).read_text(encoding="utf-8"))
        self.assertEqual(len(props["scenes"]), 1)
        scene = props["scenes"][0]
        self.assertEqual(scene["avatarSrc"], "/public/scene-0-avatar.mp4")
        self.assertEqual(scene["avatarName"], "test_avatar")
        self.assertEqual(scene["avatarMode"], "static_avatar")
        self.assertTrue(scene["avatarFallback"])
        self.assertEqual(props["musicSrc"], "/public/background-music.mp3")

    def test_execute_pipeline_without_avatar_omits_avatar_src(self):
        self._seed_draft_with_avatar(run_id="run-2", scene_id="scene-2", has_avatar=False)
        capture = self._run_pipeline("run-2")
        props = json.loads(Path(capture.body.props_path).read_text(encoding="utf-8"))
        self.assertEqual(len(props["scenes"]), 1)
        scene = props["scenes"][0]
        self.assertIsNone(scene["avatarSrc"])
        self.assertFalse(scene["avatarFallback"])
        self.assertIsNone(scene["avatarMode"])
        self.assertIsNone(scene["avatarName"])

    def test_avatar_node_reached_success_status(self):
        self._seed_draft_with_avatar(run_id="run-3", scene_id="scene-3", has_avatar=True)
        self._run_pipeline("run-3")
        with main.get_db() as conn:
            avatar_node = conn.execute(
                "SELECT status, provider, message FROM workflow_nodes WHERE workflow_run_id=? AND node_type='avatar'",
                ("run-3",),
            ).fetchone()
            self.assertIsNotNone(avatar_node)
            self.assertEqual(avatar_node["status"], "success")
            self.assertEqual(avatar_node["provider"], "wav2lip_onnx")


if __name__ == "__main__":
    unittest.main()
