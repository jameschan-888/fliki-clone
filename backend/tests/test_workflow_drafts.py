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
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "app.db")
        main.init_db()
        self.routes = {
            (method, route.path): route.endpoint
            for route in main.app.routes
            if hasattr(route, "endpoint")
            for method in (getattr(route, "methods", None) or [])
        }

        import auth_router
        self._orig_secret = auth_router.JWT_SECRET
        auth_router.JWT_SECRET = "test-workflow-drafts-" + Path(self.temp_dir.name).name
        self.tok = auth_router._make_token("user-workflow", "user")

        class _FakeRequest:
            def __init__(self, token):
                if token is None:
                    self.headers = {}
                else:
                    self.headers = {"Authorization": "Bearer " + token}
        self._FakeRequest = _FakeRequest

    def tearDown(self):
        main.config["DB_PATH"] = self.original_db_path
        import auth_router
        auth_router.JWT_SECRET = self._orig_secret
        self.temp_dir.cleanup()

    def create_draft(self):
        script = "第一段介绍产品。第二段说明场景草稿。第三段强调确认后才渲染。"
        return self.routes[("POST", "/workflow-drafts")](
            DraftCreateBody(source_script=script, title="节省算力"),
            request=self._FakeRequest(self.tok),
        )

    def test_create_returns_editable_scenes_without_expensive_jobs(self):
        result = self.create_draft()
        self.assertEqual(result["status"], "draft")
        self.assertEqual(len(result["scenes"]), 3)
        self.assertTrue(all(scene["voice"] == DEFAULT_VOICE for scene in result["scenes"]))
        self.assertTrue(all(scene["camera_motion"] == "zoom-in" for scene in result["scenes"]))
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
            ScenePatchBody(title="开场", duration_seconds=5.5, voice="zh-CN-YunxiNeural", camera_motion="pan-left"),
            request=self._FakeRequest(self.tok),
        )
        self.assertEqual(updated["scenes"][0]["title"], "开场")
        self.assertEqual(updated["scenes"][0]["voice"], "zh-CN-YunxiNeural")
        self.assertEqual(updated["scenes"][0]["camera_motion"], "pan-left")
        self.assertEqual(updated["version"], 2)

        added = self.routes[("POST", "/workflow-drafts/{draft_id}/scenes")](
            draft_id,
            SceneCreateBody(
                title="收尾",
                narration="感谢观看。",
                visual_intent="品牌收尾",
                voice="zh-CN-XiaoyiNeural",
            ),
            request=self._FakeRequest(self.tok),
        )
        self.assertEqual(added["scenes"][-1]["voice"], "zh-CN-XiaoyiNeural")

        reversed_ids = [scene["id"] for scene in reversed(added["scenes"])]
        reordered = self.routes[("POST", "/workflow-drafts/{draft_id}/reorder")](
            draft_id,
            ReorderBody(scene_ids=reversed_ids),
            request=self._FakeRequest(self.tok),
        )
        self.assertEqual([scene["id"] for scene in reordered["scenes"]], reversed_ids)
        confirmed = self.routes[("POST", "/workflow-drafts/{draft_id}/confirm")](draft_id, request=self._FakeRequest(self.tok))
        confirmed_again = self.routes[("POST", "/workflow-drafts/{draft_id}/confirm")](draft_id, request=self._FakeRequest(self.tok))
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertEqual(confirmed, confirmed_again)
        with self.assertRaises(HTTPException) as context:
            self.routes[("PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}")](
                draft_id,
                reversed_ids[0],
                ScenePatchBody(title="不应成功"),
                request=self._FakeRequest(self.tok),
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_confirm_rejects_known_voice_locale_mismatch(self):
        created = self.create_draft()
        first_scene = created["scenes"][0]
        updated = self.routes[("PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}")](
            created["id"],
            first_scene["id"],
            ScenePatchBody(voice="en-US-JennyNeural"),
            request=self._FakeRequest(self.tok),
        )
        self.assertEqual(updated["scenes"][0]["voice"], "en-US-JennyNeural")
        with self.assertRaises(HTTPException) as context:
            self.routes[("POST", "/workflow-drafts/{draft_id}/confirm")](created["id"], request=self._FakeRequest(self.tok))
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
        self.assertIn("stock_url", columns)
        self.assertIn("camera_motion", columns)

    def test_avatar_field_round_trip(self):
        created = self.create_draft()
        first_scene = created["scenes"][0]
        self.assertIn("avatar", first_scene)
        self.assertIsNone(first_scene["avatar"])

        updated = self.routes[("PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}")](
            created["id"],
            first_scene["id"],
            ScenePatchBody(avatar="avatar:12345678-aaaa-bbbb-cccc-dddddddddddd"),
            request=self._FakeRequest(self.tok),
        )
        self.assertEqual(updated["scenes"][0]["avatar"], "avatar:12345678-aaaa-bbbb-cccc-dddddddddddd")

        fetched = self.routes[("GET", "/workflow-drafts/{draft_id}")](created["id"], request=self._FakeRequest(self.tok))
        self.assertEqual(fetched["scenes"][0]["avatar"], "avatar:12345678-aaaa-bbbb-cccc-dddddddddddd")

        cleared = self.routes[("PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}")](
            created["id"],
            first_scene["id"],
            ScenePatchBody(avatar=None),
            request=self._FakeRequest(self.tok),
        )
        self.assertIsNone(cleared["scenes"][0]["avatar"])

    def test_create_draft_initial_avatar_is_null(self):
        created = self.create_draft()
        for scene in created["scenes"]:
            self.assertIn("avatar", scene)
            self.assertIsNone(scene["avatar"])


    def test_anonymous_create_rejected(self):
        """P1 修复: 无 token 创建草稿必须 401, 防止匿名孤儿草稿 (user_id=None 永不可达)."""
        with self.assertRaises(HTTPException) as ctx:
            self.routes[("POST", "/workflow-drafts")](
                DraftCreateBody(source_script="匿名草稿", title="x"),
                request=self._FakeRequest(None),
            )
        self.assertEqual(ctx.exception.status_code, 401)

    def test_delete_draft_removes_and_404_after(self):
        created = self.create_draft()
        result = self.routes[("DELETE", "/workflow-drafts/{draft_id}")](created["id"], request=self._FakeRequest(self.tok))
        self.assertTrue(result["deleted"])
        with self.assertRaises(HTTPException) as ctx:
            self.routes[("GET", "/workflow-drafts/{draft_id}")](created["id"], request=self._FakeRequest(self.tok))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_draft_with_runs_rejected_409(self):
        created = self.create_draft()
        import sqlite3 as _sq
        conn = _sq.connect(main.config["DB_PATH"])
        conn.execute("INSERT INTO workflow_runs (id, workflow_draft_id, status, created_at, updated_at) VALUES (?, ?, 'queued', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')", ("run-del-1", created["id"]))
        conn.commit()
        conn.close()
        with self.assertRaises(HTTPException) as ctx:
            self.routes[("DELETE", "/workflow-drafts/{draft_id}")](created["id"], request=self._FakeRequest(self.tok))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_delete_draft_anonymous_rejected(self):
        created = self.create_draft()
        with self.assertRaises(HTTPException) as ctx:
            self.routes[("DELETE", "/workflow-drafts/{draft_id}")](created["id"], request=self._FakeRequest(None))
        self.assertEqual(ctx.exception.status_code, 401)

if __name__ == "__main__":
    unittest.main()
