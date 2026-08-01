"""rev24 stage C #8 list-endpoint user_id filter tests.

覆盖:
- GET /workflow-drafts: 按 user_id 严格过滤; 匿名返回空数组
- GET /workflow-runs: 按 user_id 严格过滤; 匿名返回空数组
- GET /render-jobs: 按 user_id 严格过滤; 匿名返回空数组
- 创建 draft 后 user_id 落库正确 (与 #8 FK 一致)
- 跨用户读 isolation: A 看不到 B 的 draft, B 看不到 A 的 render
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth_router
import main
import workflow_drafts


def _route(main_app, method, path):
    for r in main_app.routes:
        if not hasattr(r, "endpoint"):
            continue
        if (method,) == tuple(getattr(r, "methods", set()) or set()) and r.path == path:
            return r.endpoint
    return None  # D3: 找不到 route 不再 raise, 允许端点未注册时 test 自行 skip


class _FakeRequest:
    def __init__(self, token=None):
        self.headers = {"Authorization": "Bearer " + token} if token else {}


class ListFilterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "app.db"
        self._orig_db = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(self.db)
        # init_db idempotent
        main.init_db()
        # jwt
        self.secret = "test-secret-listfilter-" + str(os.getpid())
        self._orig_secret = os.environ.get("FLIKI_JWT_SECRET")
        os.environ["FLIKI_JWT_SECRET"] = self.secret
        self._orig_module_secret = auth_router.JWT_SECRET
        auth_router.JWT_SECRET = self.secret
        # routes
        self.list_drafts = _route(main.app, "GET", "/workflow-drafts")
        self.list_runs = _route(main.app, "GET", "/workflow-runs")
        self.list_jobs = _route(main.app, "GET", "/render-jobs")
        self.create_draft = _route(main.app, "POST", "/workflow-drafts")
        # 创建两个 user
        self.tok_a = auth_router._make_token("user-aaaa", "user")
        self.tok_b = auth_router._make_token("user-bbbb", "user")

    def tearDown(self):
        main.config["DB_PATH"] = self._orig_db
        if self._orig_secret is None:
            os.environ.pop("FLIKI_JWT_SECRET", None)
        else:
            os.environ["FLIKI_JWT_SECRET"] = self._orig_secret
        auth_router.JWT_SECRET = self._orig_module_secret

    def _make_draft(self, token, title):
        return self.create_draft(
            workflow_drafts.DraftCreateBody(source_script="第一句。第二句。第三句。", title=title, language="zh-CN"),
            request=_FakeRequest(token),
        )

    def test_list_drafts_filters_by_user(self):
        da = self._make_draft(self.tok_a, "A 草稿")
        db = self._make_draft(self.tok_b, "B 草稿")
        la = self.list_drafts(request=_FakeRequest(self.tok_a))
        lb = self.list_drafts(request=_FakeRequest(self.tok_b))
        self.assertEqual([d["id"] for d in la], [da["id"]])
        self.assertEqual([d["id"] for d in lb], [db["id"]])

    def test_list_drafts_anon_returns_empty(self):
        self._make_draft(self.tok_a, "A 草稿")
        result = self.list_drafts(request=_FakeRequest(None))
        self.assertEqual(result, [])

    def test_list_drafts_no_request_returns_empty(self):
        # 直调 list_drafts 不传 request (兼容测试): 必须不暴露他人
        self._make_draft(self.tok_a, "A 草稿")
        result = self.list_drafts()
        self.assertEqual(result, [])

    def test_list_runs_filters_by_user(self):
        # 直接往 DB 插两条 workflow_run (A 和 B 各一条), 验证 list_runs 按 user_id 过滤
        now = "2026-07-28T00:00:00Z"
        conn = sqlite3.connect(self.db)
        conn.execute(
            "INSERT INTO workflow_runs (id, workflow_draft_id, status, progress, created_at, updated_at, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-aaaa", "draft-aaaa", "success", 100, now, now, "user-aaaa"),
        )
        conn.execute(
            "INSERT INTO workflow_runs (id, workflow_draft_id, status, progress, created_at, updated_at, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-bbbb", "draft-bbbb", "success", 100, now, now, "user-bbbb"),
        )
        conn.commit()
        conn.close()
        runs_a = self.list_runs(request=_FakeRequest(self.tok_a))
        runs_b = self.list_runs(request=_FakeRequest(self.tok_b))
        self.assertEqual([r["id"] for r in runs_a], ["run-aaaa"])
        self.assertEqual([r["id"] for r in runs_b], ["run-bbbb"])

    def test_list_runs_anon_returns_empty(self):
        result = self.list_runs(request=_FakeRequest(None))
        self.assertEqual(result, [])

    def test_list_runs_no_request_returns_empty(self):
        result = self.list_runs()
        self.assertEqual(result, [])

    def test_list_render_jobs_filters_by_user(self):
        # 直接往 DB 插两条 render_job, 一条 A 一条 B
        now = "2026-07-28T00:00:00Z"
        conn = sqlite3.connect(self.db)
        conn.execute(
            "INSERT INTO render_jobs (_id, playback_id, status, progress, resolution, extension, renderer, engine, user_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("job-aaaa", "play-a", "success", 100, "720p", "mp4", "local", "remotion", "user-aaaa", now),
        )
        conn.execute(
            "INSERT INTO render_jobs (_id, playback_id, status, progress, resolution, extension, renderer, engine, user_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("job-bbbb", "play-b", "success", 100, "720p", "mp4", "local", "remotion", "user-bbbb", now),
        )
        conn.commit()
        conn.close()
        # A 看自己的
        a_jobs = self.list_jobs(request=_FakeRequest(self.tok_a))
        b_jobs = self.list_jobs(request=_FakeRequest(self.tok_b))
        self.assertEqual([j["_id"] for j in a_jobs], ["job-aaaa"])
        self.assertEqual([j["_id"] for j in b_jobs], ["job-bbbb"])

    def test_list_render_jobs_anon_returns_empty(self):
        result = self.list_jobs(request=_FakeRequest(None))
        self.assertEqual(result, [])

    def test_create_draft_user_id_landed(self):
        draft = self._make_draft(self.tok_a, "落库验证")
        conn = sqlite3.connect(self.db)
        row = conn.execute("SELECT user_id FROM workflow_drafts WHERE id=?", (draft["id"],)).fetchone()
        conn.close()
        self.assertEqual(row[0], "user-aaaa")


if __name__ == "__main__":
    unittest.main()


class CrossUserAccessDeniedTest(unittest.TestCase):
    """rev24 stage C #8 收尾: drafts/runs/render 单点端点必须拒绝跨 user 访问."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "app.db"
        self._orig_db = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(self.db)
        main.init_db()
        self.secret = "test-secret-crossuser-" + str(os.getpid())
        self._orig_secret = os.environ.get("FLIKI_JWT_SECRET")
        os.environ["FLIKI_JWT_SECRET"] = self.secret
        self._orig_module_secret = auth_router.JWT_SECRET
        auth_router.JWT_SECRET = self.secret
        self.create_draft = _route(main.app, "POST", "/workflow-drafts")
        self.get_draft = _route(main.app, "GET", "/workflow-drafts/{draft_id}")
        self.patch_scene = _route(main.app, "PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}")
        self.add_scene = _route(main.app, "POST", "/workflow-drafts/{draft_id}/scenes")
        self.delete_scene = _route(main.app, "DELETE", "/workflow-drafts/{draft_id}/scenes/{scene_id}")
        self.confirm_draft = _route(main.app, "POST", "/workflow-drafts/{draft_id}/confirm")
        self.get_run = _route(main.app, "GET", "/workflow-runs/{run_id}")
        self.retry_run = _route(main.app, "POST", "/workflow-runs/{run_id}/retry")
        self.rerender_run = _route(main.app, "POST", "/workflow-runs/{run_id}/rerender")
        self.create_run = _route(main.app, "POST", "/workflow-runs/from-draft/{draft_id}")
        self.render_latest = _route(main.app, "GET", "/render.latest")
        self.tok_a = auth_router._make_token("user-aaaa", "user")
        self.tok_b = auth_router._make_token("user-bbbb", "user")
        # A 创建并 confirm 一个 draft, 跑出 run
        self.draft_a = self.create_draft(
            workflow_drafts.DraftCreateBody(source_script="句一。句二。", title="A 跨用户测", language="zh-CN"),
            request=_FakeRequest(self.tok_a),
        )
        self.confirm_draft(self.draft_a["id"], request=_FakeRequest(self.tok_a))
        self.draft_b = self.create_draft(
            workflow_drafts.DraftCreateBody(source_script="句一。", title="B 草稿", language="zh-CN"),
            request=_FakeRequest(self.tok_b),
        )

    def tearDown(self):
        main.config["DB_PATH"] = self._orig_db
        if self._orig_secret is None:
            os.environ.pop("FLIKI_JWT_SECRET", None)
        else:
            os.environ["FLIKI_JWT_SECRET"] = self._orig_secret
        auth_router.JWT_SECRET = self._orig_module_secret

    # --- drafts 端点跨用户拒绝 ---
    def test_get_draft_cross_user_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.get_draft(self.draft_b["id"], request=_FakeRequest(self.tok_a))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_draft_anon_401(self):
        with self.assertRaises(HTTPException) as ctx:
            self.get_draft(self.draft_a["id"])
        self.assertEqual(ctx.exception.status_code, 401)

    def test_get_draft_owner_ok(self):
        result = self.get_draft(self.draft_a["id"], request=_FakeRequest(self.tok_a))
        self.assertEqual(result["id"], self.draft_a["id"])

    def test_patch_scene_cross_user_404(self):
        sid = self.draft_b["scenes"][0]["id"]
        from workflow_drafts import ScenePatchBody
        with self.assertRaises(HTTPException) as ctx:
            self.patch_scene(
                self.draft_b["id"], sid,
                ScenePatchBody(title="hacked"),
                request=_FakeRequest(self.tok_a),
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_add_scene_cross_user_404(self):
        from workflow_drafts import SceneCreateBody
        with self.assertRaises(HTTPException) as ctx:
            self.add_scene(
                self.draft_b["id"],
                SceneCreateBody(title="hacked", narration="x", visual_intent="y"),
                request=_FakeRequest(self.tok_a),
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_scene_cross_user_404(self):
        sid = self.draft_b["scenes"][0]["id"]
        with self.assertRaises(HTTPException) as ctx:
            self.delete_scene(
                self.draft_b["id"], sid,
                request=_FakeRequest(self.tok_a),
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_confirm_cross_user_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.confirm_draft(self.draft_b["id"], request=_FakeRequest(self.tok_a))
        self.assertEqual(ctx.exception.status_code, 404)

    # --- runs 端点跨用户拒绝 ---
    def test_create_run_cross_user_404(self):
        # B 想跑 A 的 draft
        with self.assertRaises(HTTPException) as ctx:
            self.create_run(self.draft_a["id"], background_tasks=BackgroundTasks(), request=_FakeRequest(self.tok_b))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_create_run_anon_401(self):
        with self.assertRaises(HTTPException) as ctx:
            self.create_run(self.draft_a["id"], background_tasks=BackgroundTasks())
        self.assertEqual(ctx.exception.status_code, 401)

    def test_get_run_cross_user_404(self):
        # A 跑自己的 run (后台任务不真的跑, 因为 BackgroundTasks 不会被同步执行)
        run_a = self.create_run(self.draft_a["id"], background_tasks=BackgroundTasks(), request=_FakeRequest(self.tok_a))
        run_id = run_a["id"]
        # 注: 后端 run payload 字段可能不是 id 而是 run_id 或 runId; 直接查 DB
        import sqlite3
        conn = sqlite3.connect(self.db)
        row = conn.execute("SELECT id FROM workflow_runs WHERE user_id=?", ("user-aaaa",)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        with self.assertRaises(HTTPException) as ctx:
            self.get_run(row[0], request=_FakeRequest(self.tok_b))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_retry_run_cross_user_404(self):
        # 直接 INSERT 一条 failed run 属于 A
        now = "2026-07-29T00:00:00Z"
        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.execute(
            "INSERT INTO workflow_runs (id, workflow_draft_id, status, progress, created_at, updated_at, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-test", self.draft_a["id"], "failed", 0, now, now, "user-aaaa"),
        )
        conn.commit(); conn.close()
        with self.assertRaises(HTTPException) as ctx:
            self.retry_run("run-test", background_tasks=BackgroundTasks(), request=_FakeRequest(self.tok_b))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_rerender_run_cross_user_404(self):
        now = "2026-07-29T00:00:00Z"
        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.execute(
            "INSERT INTO workflow_runs (id, workflow_draft_id, status, progress, created_at, updated_at, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-test-2", self.draft_a["id"], "success", 100, now, now, "user-aaaa"),
        )
        conn.commit(); conn.close()
        # rerender_existing 内部会调 execute_pipeline; 即使校验通过, B 没权限
        with self.assertRaises(HTTPException) as ctx:
            self.rerender_run("run-test-2", background_tasks=BackgroundTasks(), request=_FakeRequest(self.tok_b))
        self.assertEqual(ctx.exception.status_code, 404)

    # --- render.latest 跨用户隐藏 ---
    def test_render_latest_cross_user_hidden(self):
        self.assertIsNotNone(self.render_latest, "/render.latest route must be registered")
        # 直接插一条 render_job 属于 A
        now = "2026-07-29T00:00:00Z"
        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.execute(
            "INSERT INTO render_jobs (_id, playback_id, status, progress, resolution, extension, renderer, engine, user_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("job-priv", "play-priv", "success", 100, "720p", "mp4", "local", "remotion", "user-aaaa", now),
        )
        conn.execute(
            "INSERT INTO render_jobs (_id, playback_id, status, progress, resolution, extension, renderer, engine, user_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("job-new", "play-priv", "processing", 40, "720p", "mp4", "local", "remotion", "user-aaaa", "2026-07-29T00:01:00Z"),
        )
        conn.commit(); conn.close()
        # B 拿 playback_id 查不到 (静默 None)
        result = self.render_latest("play-priv", request=_FakeRequest(self.tok_b))
        self.assertIsNone(result["renderRecent"])
        self.assertIsNone(result["renderSuccess"])
        # A 自己能分别拿到最近任务和最近成功任务
        result = self.render_latest("play-priv", request=_FakeRequest(self.tok_a))
        self.assertEqual(result["renderRecent"]["status"], "processing")
        self.assertEqual(result["renderRecent"]["progress"], 40)
        self.assertEqual(result["renderSuccess"]["status"], "success")
        self.assertEqual(result["renderSuccess"]["progress"], 100)
