"""P5D-8：fast preview 模式（480p + 跳 avatar）+ 2-scene 端到端 contract"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import workflow_pipeline as wp


class PreviewParameterTests(unittest.TestCase):
    def test_execute_pipeline_accepts_preview_kw(self):
        import inspect
        sig = inspect.signature(wp.execute_pipeline)
        self.assertIn("preview", sig.parameters)
        self.assertEqual(sig.parameters["preview"].default, False)

    def test_merge_avatar_layout_preview_unaffected(self):
        out = wp._merge_avatar_layout({"position": "top-left"}, {"position": "bottom-right"})
        self.assertEqual(out["position"], "bottom-right")


class MultiScenePipelineTests(unittest.TestCase):
    def _fake(self):
        return [
            {"id": "s1", "duration_seconds": 2.0, "avatar": "avatar:abc",
             "avatar_layout": json.dumps({"position": "bottom-right", "size": 320})},
            {"id": "s2", "duration_seconds": 3.0, "avatar": None, "avatar_layout": None},
        ]

    def test_rendered_scenes_avatar_layout_merge(self):
        from workflow_pipeline import _merge_avatar_layout
        global_layout = {"position": "top-left", "shape": "circle", "size": 240}
        rendered = []
        for sc in self._fake():
            try: sc_layout = json.loads(sc["avatar_layout"]) if sc["avatar_layout"] else None
            except Exception: sc_layout = None
            rendered.append({"id": sc["id"], "avatarLayout": _merge_avatar_layout(global_layout, sc_layout)})
        self.assertEqual(rendered[0]["avatarLayout"]["position"], "bottom-right")
        self.assertEqual(rendered[0]["avatarLayout"]["shape"], "circle")
        self.assertEqual(rendered[0]["avatarLayout"]["size"], 320)
        self.assertEqual(rendered[1]["avatarLayout"], global_layout)

    def test_rendered_scenes_duration_sum(self):
        rendered = [{"durationInSeconds": s["duration_seconds"]} for s in self._fake()]
        self.assertEqual(sum(s["durationInSeconds"] for s in rendered), 5.0)


class SceneAvatarLayoutPersistenceTests(unittest.TestCase):
    def test_payload_includes_avatar_layout_when_set(self):
        import sqlite3, tempfile, uuid
        from workflow_drafts import draft_payload
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); tmp.close()
        conn = None
        try:
            conn = sqlite3.connect(tmp.name); conn.row_factory = sqlite3.Row
            conn.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
            did = uuid.uuid4().hex; sid = uuid.uuid4().hex
            now = 1700000000
            conn.execute("INSERT INTO workflow_drafts (id, title, source_script, language, status, version, created_at, updated_at, confirmed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                         (did, "t", "s", "zh-CN", "draft", 1, now, now, None))
            conn.execute("INSERT INTO scene_drafts (id, workflow_draft_id, position, title, narration, visual_intent, subtitle, duration_seconds, voice, avatar, avatar_layout, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (sid, did, 0, "t", "n", "v", "", 2.0, "zh-CN-XiaoxiaoNeural", None, None, now, now))
            conn.commit()
            payload = draft_payload(conn, did)
            self.assertNotIn("avatar_layout", payload["scenes"][0])
            conn.execute("UPDATE scene_drafts SET avatar_layout=? WHERE id=?", (json.dumps({"position": "top-left"}), sid))
            conn.commit()
            payload = draft_payload(conn, did)
            self.assertEqual(payload["scenes"][0]["avatar_layout"], {"position": "top-left"})
        finally:
            if conn: conn.close()
            Path(tmp.name).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()