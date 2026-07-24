import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

import main
from providers.tts import DEFAULT_VOICE
from workflow_drafts import DraftCreateBody, ReorderBody, SceneCreateBody, ScenePatchBody


class WorkflowDraftsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "app.db")
        main.init_db()
        self.routes = {
            (method, route.path): route.endpoint
            for route in main.app.routes
            if hasattr(route, "endpoint")
            for method in (getattr(route, "methods", None) or [])
        }

    def tearDown(self):
        main.config["DB_PATH"] = self.original_db_path
        self.temp_dir.cleanup()

    def create_draft(self):
        script = "第一段介绍产品。第二段说明场景草稿。第三段强调确认后才渲染。"
        return self.routes[("POST", "/workflow-drafts")](DraftCreateBody(source_script=script, title="节省算力"))

    def test_create_returns_editable_scenes_without_expensive_jobs(self):
        result = self.create_draft()
        self.assertEqual(result["status"], "draft")
        self.assertEqual(len(result["scenes"]), 3)
        self.assertTrue(all(scene["voice"] == DEFAULT_VOICE for scene in result["scenes"]))
        connection = sqlite3.connect(main.config["DB_PATH"])
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM render_jobs").fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM media_assets").fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)
        connection.close()

    def test_edit_add_reorder_and_confirm_are_persistent_and_idempotent(self):
        created = self.create_draft()
        draft_id = created["id"]
        first_scene = created["scenes"][0]
        updated = self.routes[("PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}")](
            draft_id,
            first_scene["id"],
            ScenePatchBody(title="开场", duration_seconds=5.5, voice="zh-CN-YunxiNeural"),
        )
        self.assertEqual(updated["scenes"][0]["title"], "开场")
        self.assertEqual(updated["scenes"][0]["voice"], "zh-CN-YunxiNeural")
        self.assertEqual(updated["version"], 2)

        added = self.routes[("POST", "/workflow-drafts/{draft_id}/scenes")](
            draft_id,
            SceneCreateBody(
                title="收尾",
                narration="感谢观看。",
                visual_intent="品牌收尾",
                voice="zh-CN-XiaoyiNeural",
            ),
        )
        self.assertEqual(added["scenes"][-1]["voice"], "zh-CN-XiaoyiNeural")

        reversed_ids = [scene["id"] for scene in reversed(added["scenes"])]
        reordered = self.routes[("POST", "/workflow-drafts/{draft_id}/reorder")](
            draft_id,
            ReorderBody(scene_ids=reversed_ids),
        )
        self.assertEqual([scene["id"] for scene in reordered["scenes"]], reversed_ids)
        confirmed = self.routes[("POST", "/workflow-drafts/{draft_id}/confirm")](draft_id)
        confirmed_again = self.routes[("POST", "/workflow-drafts/{draft_id}/confirm")](draft_id)
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertEqual(confirmed, confirmed_again)
        with self.assertRaises(HTTPException) as context:
            self.routes[("PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}")](
                draft_id,
                reversed_ids[0],
                ScenePatchBody(title="不应成功"),
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_confirm_rejects_known_voice_locale_mismatch(self):
        created = self.create_draft()
        first_scene = created["scenes"][0]
        updated = self.routes[("PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}")](
            created["id"],
            first_scene["id"],
            ScenePatchBody(voice="en-US-JennyNeural"),
        )
        self.assertEqual(updated["scenes"][0]["voice"], "en-US-JennyNeural")
        with self.assertRaises(HTTPException) as context:
            self.routes[("POST", "/workflow-drafts/{draft_id}/confirm")](created["id"])
        self.assertEqual(context.exception.status_code, 422)
        self.assertIn("zh-CN", context.exception.detail)

    def test_init_db_migrates_legacy_scene_table(self):
        connection = sqlite3.connect(main.config["DB_PATH"])
        connection.execute("DROP TABLE scene_drafts")
        connection.executescript(
            """
            CREATE TABLE scene_drafts (
              id TEXT PRIMARY KEY,
              workflow_draft_id TEXT NOT NULL,
              position INTEGER NOT NULL,
              title TEXT NOT NULL,
              narration TEXT NOT NULL,
              visual_intent TEXT NOT NULL,
              subtitle TEXT NOT NULL,
              duration_seconds REAL NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(workflow_draft_id, position)
            );
            """
        )
        connection.close()

        self.assertTrue(main.init_db())
        connection = sqlite3.connect(main.config["DB_PATH"])
        columns = [row[1] for row in connection.execute("PRAGMA table_info(scene_drafts)")]
        connection.close()
        self.assertIn("voice", columns)
        self.assertIn("avatar", columns)

    def test_avatar_field_round_trip(self):
        created = self.create_draft()
        first_scene = created["scenes"][0]
        self.assertIn("avatar", first_scene)
        self.assertIsNone(first_scene["avatar"])

        updated = self.routes[("PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}")](
            created["id"],
            first_scene["id"],
            ScenePatchBody(avatar="avatar:12345678-aaaa-bbbb-cccc-dddddddddddd"),
        )
        self.assertEqual(updated["scenes"][0]["avatar"], "avatar:12345678-aaaa-bbbb-cccc-dddddddddddd")

        fetched = self.routes[("GET", "/workflow-drafts/{draft_id}")](created["id"])
        self.assertEqual(fetched["scenes"][0]["avatar"], "avatar:12345678-aaaa-bbbb-cccc-dddddddddddd")

        cleared = self.routes[("PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}")](
            created["id"],
            first_scene["id"],
            ScenePatchBody(avatar=None),
        )
        self.assertIsNone(cleared["scenes"][0]["avatar"])

    def test_create_draft_initial_avatar_is_null(self):
        created = self.create_draft()
        for scene in created["scenes"]:
            self.assertIn("avatar", scene)
            self.assertIsNone(scene["avatar"])


if __name__ == "__main__":
    unittest.main()
