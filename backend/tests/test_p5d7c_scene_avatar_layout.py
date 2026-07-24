"""P5D-7 后续：scene 级 avatar_layout 覆盖"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from workflow_drafts import (
    draft_payload, scene_from_row, ScenePatchBody, create_router as create_drafts_router,
)
from workflow_pipeline import _merge_avatar_layout
from provider_config import seed_runtime_providers


def _fresh_db():
    import sqlite3, tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.row_factory = sqlite3.Row
    schema = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    return conn, tmp.name


def _make_drafts(conn):
    import uuid
    draft_id = uuid.uuid4().hex
    now = 1700000000
    conn.execute("INSERT INTO workflow_drafts (id, title, source_script, language, status, version, created_at, updated_at) VALUES (?, ?, ?, ?, 'draft', 1, ?, ?)",
                 (draft_id, "t", "s", "zh-CN", now, now))
    sid = uuid.uuid4().hex
    conn.execute("INSERT INTO scene_drafts (id, workflow_draft_id, position, title, narration, visual_intent, subtitle, duration_seconds, voice, avatar, avatar_layout, created_at, updated_at) VALUES (?, ?, 0, 't', 'n', 'v', '', 3.0, 'zh-CN-XiaoxiaoNeural', NULL, NULL, ?, ?)",
                 (sid, draft_id, now, now))
    conn.commit()
    return draft_id, sid


class MergeLayoutTests(unittest.TestCase):
    def test_global_only(self):
        self.assertEqual(_merge_avatar_layout({"position": "top-left"}, None), {"position": "top-left"})

    def test_scene_overrides_top_level(self):
        out = _merge_avatar_layout({"position": "top-left", "size": 240}, {"position": "bottom-right"})
        self.assertEqual(out, {"position": "bottom-right", "size": 240})

    def test_scene_dict_merges_nested(self):
        out = _merge_avatar_layout({"position": "top-left", "size": {"width": 240, "height": 240}}, {"size": {"width": 320}})
        self.assertEqual(out["position"], "top-left")
        self.assertEqual(out["size"], {"width": 320, "height": 240})

    def test_invalid_inputs(self):
        self.assertIsNone(_merge_avatar_layout(None, None))
        self.assertEqual(_merge_avatar_layout(None, {"position": "x"}), {"position": "x"})
        self.assertEqual(_merge_avatar_layout({"position": "x"}, "bad"), {"position": "x"})

    def test_no_global_scene_only(self):
        out = _merge_avatar_layout(None, {"position": "top-left", "size": 320})
        self.assertEqual(out, {"position": "top-left", "size": 320})


class ScenePatchAvatarLayoutTests(unittest.TestCase):
    def setUp(self):
        self.conn, self.db_path = _fresh_db()
        self.draft_id, self.scene_id = _make_drafts(self.conn)

    def tearDown(self):
        self.conn.close()
        Path(self.db_path).unlink(missing_ok=True)

    def _patch(self, **fields):
        body = ScenePatchBody(**fields)
        values = body.model_dump(exclude_unset=True)
        if "avatar_layout" in values and values["avatar_layout"] is not None:
            values["avatar_layout"] = json.dumps(values["avatar_layout"], ensure_ascii=False)
        assignments = ", ".join(f"{name}=?" for name in values)
        self.conn.execute(f"UPDATE scene_drafts SET {assignments}, updated_at=? WHERE id=?",
                          (*values.values(), 1700000001, self.scene_id))
        self.conn.commit()
        row = self.conn.execute("SELECT avatar_layout FROM scene_drafts WHERE id=?", (self.scene_id,)).fetchone()
        return row["avatar_layout"]

    def test_set_scene_layout(self):
        layout = {"position": "bottom-right", "size": 320, "shape": "circle"}
        raw = self._patch(avatar_layout=layout)
        self.assertEqual(json.loads(raw), layout)

    def test_clear_scene_layout(self):
        self._patch(avatar_layout={"position": "x"})
        self._patch(avatar_layout=None)
        row = self.conn.execute("SELECT avatar_layout FROM scene_drafts WHERE id=?", (self.scene_id,)).fetchone()
        self.assertIsNone(row["avatar_layout"])

    def test_payload_returns_parsed(self):
        layout = {"position": "top-left", "shape": "rounded", "size": 256}
        self._patch(avatar_layout=layout)
        payload = draft_payload(self.conn, self.draft_id)
        scene = payload["scenes"][0]
        self.assertEqual(scene["avatar_layout"], layout)

    def test_payload_no_field_when_null(self):
        payload = draft_payload(self.conn, self.draft_id)
        scene = payload["scenes"][0]
        self.assertNotIn("avatar_layout", scene)

    def test_payload_invalid_json_becomes_none(self):
        self.conn.execute("UPDATE scene_drafts SET avatar_layout=? WHERE id=?", ("{not json", self.scene_id))
        self.conn.commit()
        payload = draft_payload(self.conn, self.draft_id)
        self.assertIsNone(payload["scenes"][0].get("avatar_layout"))


class ScenePatchBodyValidationTests(unittest.TestCase):
    def test_accepts_dict(self):
        body = ScenePatchBody(avatar_layout={"position": "top-left"})
        self.assertEqual(body.avatar_layout, {"position": "top-left"})

    def test_accepts_none(self):
        body = ScenePatchBody(avatar=None)
        self.assertIsNone(body.avatar)

    def test_require_at_least_one_field(self):
        with self.assertRaises(Exception):
            ScenePatchBody()


if __name__ == "__main__":
    unittest.main()