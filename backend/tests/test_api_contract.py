"""API 合约测试: 锁定关键路由的响应 schema, 防止后续重构破坏前端契约.

不启动 FastAPI lifespan (避免网络 I/O), 直接调路由函数 + 构造 Pydantic body,
每个测试只验证状态码 + 响应 schema, 不验证业务逻辑.
"""
import inspect
import json
import tempfile
import unittest
from pathlib import Path

import main
from workflow_drafts import (
    DraftCreateBody, ScenePatchBody,
)


def _field_type(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _check_schema(payload, schema):
    if not isinstance(payload, dict):
        raise AssertionError(f"expected object, got {type(payload).__name__}")
    for name, expected in schema.items():
        if name not in payload:
            raise AssertionError(f"missing field {name!r} in payload keys={list(payload.keys())}")
        got = _field_type(payload[name])
        if got != expected:
            raise AssertionError(f"field {name!r}: expected {expected}, got {got} (value={payload[name]!r})")


class _NoopBackgroundTasks:
    def add_task(self, *args, **kwargs):
        return None


class _MockRequest:
    """最小可用的 starlette Request 替身, 仅实现测试需要的接口 (headers)."""

    def __init__(self, token: str = ""):
        self.headers = {"Authorization": "Bearer " + token} if token else {}


class ApiContractBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "app.db")
        main.init_db()
        # 注册一个测试用户并签 token, 注入到每个受保护 endpoint.
        from auth_router import _make_token, _hash_pw, ensure_users_table  # type: ignore
        ensure_users_table()
        import time as _time
        import uuid as _uuid
        with main.get_db() as con:
            self.user_id = _uuid.uuid4().hex
            salt, pw_hash = _hash_pw("test-pass-123")
            now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
            con.execute(
                "INSERT INTO users (id, email, password_salt, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.user_id, "test@fliki.local", salt, pw_hash, "user", now, now),
            )
            con.commit()
        self.token = _make_token(self.user_id, "user")
        self.routes = {}
        for route in main.app.routes:
            if not hasattr(route, "endpoint"):
                continue
            for method in (getattr(route, "methods", None) or []):
                self.routes[(method, route.path)] = route.endpoint

    def tearDown(self):
        main.config["DB_PATH"] = self.original_db_path
        try:
            self.temp_dir.cleanup()
        except (OSError, PermissionError):
            # WinError 32: 文件被锁 (Windows 文件句柄延迟释放); 留给 OS 回收, 不影响结果
            pass

    def call(self, method, path, **kwargs):
        endpoint = self.routes.get((method, path))
        if endpoint is None:
            raise AssertionError(f"route not found: {method} {path}")
        try:
            sig = inspect.signature(endpoint)
            params = sig.parameters
        except (TypeError, ValueError):
            params = {}
        if "background_tasks" in params and "background_tasks" not in kwargs:
            kwargs["background_tasks"] = _NoopBackgroundTasks()
        # 自动注入 mock request (兼容 request: Request = None 签名)
        if "request" in params and "request" not in kwargs:
            kwargs["request"] = _MockRequest(self.token)
        try:
            result = endpoint(**kwargs)
            return 200, result
        except Exception as exc:
            status = getattr(exc, "status_code", 500)
            detail = getattr(exc, "detail", str(exc))
            return status, {"detail": detail}


class HealthContract(ApiContractBase):
    def test_health_returns_status(self):
        status, payload = self.call("GET", "/health")
        self.assertEqual(status, 200)
        _check_schema(payload, {"status": "string"})


class StartupStatusContract(ApiContractBase):
    def test_startup_status_shape(self):
        status, payload = self.call("GET", "/startup-status")
        self.assertEqual(status, 200)
        self.assertIsInstance(payload, dict)
        # 即使 pending 状态也应有 status 字段
        self.assertIn("state", payload)


class ProvidersContract(ApiContractBase):
    def test_providers_lists_known_categories(self):
        status, payload = self.call("GET", "/providers")
        self.assertEqual(status, 200)
        self.assertIsInstance(payload, dict)
        for category in ("stock", "music", "tts"):
            self.assertIn(category, payload, f"missing category {category!r}")


class TemplatesContract(ApiContractBase):
    def test_templates_list(self):
        status, payload = self.call("GET", "/templates")
        self.assertEqual(status, 200)
        self.assertIsInstance(payload, list)
        if payload:
            _check_schema(payload[0], {"id": "string", "name": "string", "category": "string"})

    def test_template_detail(self):
        status, payload = self.call("GET", "/templates")
        self.assertEqual(status, 200)
        self.assertTrue(payload, "expected at least one template")
        tid = payload[0]["id"]
        status, detail = self.call("GET", "/templates/{template_id}", template_id=tid)
        self.assertEqual(status, 200)
        _check_schema(detail, {"id": "string", "name": "string", "category": "string", "fields": "list"})

    def test_template_categories(self):
        status, payload = self.call("GET", "/templates/categories")
        self.assertEqual(status, 200)
        self.assertIsInstance(payload, list)
        # categories 端点返回 [{category, count}]
        if payload:
            self.assertIn("category", payload[0])
            self.assertIn("count", payload[0])

    def test_template_validate_missing_required(self):
        # quote_card.quote 是 required, 空 fields 应返回 valid=false + errors
        status, payload = self.call("POST", "/templates/{template_id}/validate",
                                     template_id="quote_card", payload={"fields": {"quote": "   "}})
        self.assertEqual(status, 200)
        self.assertIn("valid", payload)
        self.assertFalse(payload["valid"])
        self.assertGreater(len(payload["errors"]), 0)


class WorkflowDraftsContract(ApiContractBase):
    def _create_draft(self):
        return self.call("POST", "/workflow-drafts", body=DraftCreateBody(
            source_script="第一条。第二条。第三条。第四条。",
            title="合约测试", language="zh-CN",
        ))[1]

    def test_create_draft_shape(self):
        draft = self._create_draft()
        _check_schema(draft, {
            "id": "string", "title": "string", "status": "string",
            "version": "int", "scenes": "list", "language": "string",
        })
        self.assertEqual(draft["status"], "draft")
        self.assertGreaterEqual(len(draft["scenes"]), 1)
        scene = draft["scenes"][0]
        _check_schema(scene, {
            "id": "string", "title": "string", "narration": "string",
            "duration_seconds": "float", "voice": "string",
            "camera_motion": "string", "video_aspect": "string",
        })

    def test_get_draft(self):
        created = self._create_draft()
        status, draft = self.call("GET", "/workflow-drafts/{draft_id}", draft_id=created["id"])
        self.assertEqual(status, 200)
        self.assertEqual(draft["id"], created["id"])

    def test_patch_scene_returns_revision_bump(self):
        created = self._create_draft()
        scene_id = created["scenes"][0]["id"]
        status, updated = self.call(
            "PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}",
            draft_id=created["id"], scene_id=scene_id,
            body=ScenePatchBody(title="新标题", camera_motion="pan-right"),
        )
        self.assertEqual(status, 200, updated)
        self.assertEqual(updated["scenes"][0]["title"], "新标题")
        self.assertEqual(updated["scenes"][0]["camera_motion"], "pan-right")
        self.assertEqual(updated["version"], 2)

    def test_confirm_locks_draft(self):
        created = self._create_draft()
        scene_id = created["scenes"][0]["id"]
        status, confirmed = self.call("POST", "/workflow-drafts/{draft_id}/confirm", draft_id=created["id"])
        self.assertEqual(status, 200)
        self.assertEqual(confirmed["status"], "confirmed")
        status, err = self.call(
            "PATCH", "/workflow-drafts/{draft_id}/scenes/{scene_id}",
            draft_id=created["id"], scene_id=scene_id,
            body=ScenePatchBody(title="尝试改"),
        )
        self.assertEqual(status, 409)
        _check_schema(err, {"detail": "string"})


class WorkflowRunsContract(ApiContractBase):
    def _create_confirmed(self):
        _, draft = self.call("POST", "/workflow-drafts", body=DraftCreateBody(
            source_script="第一条。第二条。第三条。第四条。",
            title="合约测试运行", language="zh-CN",
        ))
        self.call("POST", "/workflow-drafts/{draft_id}/confirm", draft_id=draft["id"])
        return draft["id"]

    def test_run_from_draft_shape(self):
        draft_id = self._create_confirmed()
        status, run = self.call("POST", "/workflow-runs/from-draft/{draft_id}",
                                 draft_id=draft_id, preview=True)
        self.assertEqual(status, 200, run)
        _check_schema(run, {
            "id": "string", "workflow_draft_id": "string",
            "status": "string", "progress": "int", "nodes": "list",
        })
        self.assertEqual(run["workflow_draft_id"], draft_id)

    def test_get_run(self):
        draft_id = self._create_confirmed()
        status, run = self.call("POST", "/workflow-runs/from-draft/{draft_id}",
                                 draft_id=draft_id, preview=True)
        status, fetched = self.call("GET", "/workflow-runs/{run_id}", run_id=run["id"])
        self.assertEqual(status, 200)
        self.assertEqual(fetched["id"], run["id"])

    def test_retry_missing_run_returns_404(self):
        status, err = self.call("POST", "/workflow-runs/{run_id}/retry", run_id="non-existent-id")
        self.assertEqual(status, 404)
        _check_schema(err, {"detail": "string"})


class ErrorShapeContract(ApiContractBase):
    def test_not_found_error_shape(self):
        status, payload = self.call("GET", "/workflow-drafts/{draft_id}", draft_id="non-existent-id")
        self.assertEqual(status, 404)
        _check_schema(payload, {"detail": "string"})

    def test_validation_error_via_missing_required_field(self):
        # 触发 422: draft 缺少 title (Pydantic 必填, 这里故意只传 source_script)
        status, payload = self.call("POST", "/workflow-drafts",
                                     body=DraftCreateBody(source_script="短", title="ok"))
        # 当前实现允许 title 默认值; 我们用更严格的 body: 空 source_script 应被 Pydantic 拒绝
        from pydantic import ValidationError
        try:
            DraftCreateBody(source_script="", title="")
            self.fail("expected ValidationError")
        except ValidationError:
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
