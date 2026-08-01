import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient
from pathlib import Path

import main
from workflow_drafts import DraftCreateBody, ScenePatchBody


def _patch_body(**kwargs):
    return ScenePatchBody(**kwargs)


class MockProviderGateTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "app.db")
        main.init_db()
        # 重置 seed（init_db 不会重写，但我们要保证 mock seed 在）
        from provider_config import seed_runtime_providers
        with main.get_db() as connection:
            seed_runtime_providers(connection)
            # 把 tts 默认切到 mock，模拟"用 mock 配置去 confirm"
            connection.execute(
                "UPDATE provider_configs SET is_default=1 WHERE category='tts' AND name='mock'"
            )
            connection.execute(
                "UPDATE provider_configs SET is_default=0 WHERE category='tts' AND name='edge_tts'"
            )
            connection.commit()
        self.routes = {
            (method, route.path): route.endpoint
            for route in main.app.routes
            if hasattr(route, "endpoint")
            for method in (getattr(route, "methods", None) or [])
        }

        # D3: 设 token + _FakeRequest, 避免后续路由 _require_draft_owner 401
        import auth_router
        self._secret = "test-mock-gate-" + str(Path(self.temp_dir.name).name)
        self._orig_secret = auth_router.JWT_SECRET
        auth_router.JWT_SECRET = self._secret
        self.tok = auth_router._make_token("user-mock", "user")

        class _FakeReq:
            def __init__(self, t):
                self.headers = {"Authorization": "Bearer " + t} if t else {}
        self._FakeRequest = _FakeReq

    def tearDown(self):
        main.config["DB_PATH"] = self.original_db_path
        import auth_router
        auth_router.JWT_SECRET = self._orig_secret
        # 强制 GC 关闭任何残留 sqlite3 连接 (Windows 文件锁延迟)
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except (OSError, PermissionError) as exc:
            # Windows sqlite3 file lock 延迟, 留给 OS 进程退出回收
            import sys
            print(f"[tearDown] {self.__class__.__name__}: temp cleanup 跳过 ({type(exc).__name__}): {exc}", file=sys.stderr)

    def _create_draft(self):
        create = self.routes[("POST", "/workflow-drafts")]
        return create(
            DraftCreateBody(
                source_script="第一段介绍。第二段说明。第三段总结。",
                title="mock-gate test",
            ),
            request=self._FakeRequest(self.tok),
        )

    def test_provider_payload_exposes_is_mock(self):
        list_endpoint = next(
            route.endpoint for route in main.app.routes
            if route.path == "/provider-configs" and "GET" in route.methods
        )
        items = list_endpoint("tts")
        mock_item = next(item for item in items if item["name"] == "mock")
        self.assertTrue(mock_item["is_mock"])
        real_item = next(item for item in items if item["name"] == "edge_tts")
        self.assertFalse(real_item["is_mock"])

    def test_confirm_blocks_when_default_provider_is_mock(self):
        draft = self._create_draft()
        try:
            self.routes[("POST", "/workflow-drafts/{draft_id}/confirm")](draft["id"], request=self._FakeRequest(self.tok))
            self.fail("Expected LingjianError when tts default is mock")
        except Exception as exc:
            self.assertEqual(getattr(exc, "error_code", None), "MOCK_PROVIDER_BLOCKS_RELEASE")
            self.assertEqual(exc.status_code, 409)
            self.assertEqual(exc.details["mock_providers"][0]["category"], "tts")
            self.assertEqual(exc.details["mock_providers"][0]["name"], "mock")

    def test_confirm_http_response_uses_409_for_mock_provider(self):
        draft = self._create_draft()
        client = TestClient(main.app, raise_server_exceptions=False)
        response = client.post(
            "/workflow-drafts/" + draft["id"] + "/confirm",
            headers={"Authorization": "Bearer " + self.tok},
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["error_code"], "MOCK_PROVIDER_BLOCKS_RELEASE")
        self.assertEqual(body["status"], 409)
        self.assertEqual(body["details"]["mock_providers"][0]["category"], "tts")

    def test_confirm_passes_when_all_defaults_are_real(self):
        with main.get_db() as connection:
            connection.execute(
                "UPDATE provider_configs SET is_default=1 WHERE category='tts' AND name='edge_tts'"
            )
            connection.execute(
                "UPDATE provider_configs SET is_default=0 WHERE category='tts' AND name='mock'"
            )
            connection.commit()
        draft = self._create_draft()
        confirmed = self.routes[("POST", "/workflow-drafts/{draft_id}/confirm")](draft["id"], request=self._FakeRequest(self.tok))
        self.assertEqual(confirmed["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
