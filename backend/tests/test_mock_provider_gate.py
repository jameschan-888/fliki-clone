import sqlite3
import tempfile
import unittest
from pathlib import Path

import main
from workflow_drafts import DraftCreateBody, ScenePatchBody


def _patch_body(**kwargs):
    return ScenePatchBody(**kwargs)


class MockProviderGateTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "app.db")
        main.init_db()
        # 重置 seed（init_db 不会重写，但我们要保证 mock seed 在）
        from provider_config import seed_runtime_providers
        connection = main.get_db()
        try:
            seed_runtime_providers(connection)
            # 把 tts 默认切到 mock，模拟"用 mock 配置去 confirm"
            connection.execute(
                "UPDATE provider_configs SET is_default=1 WHERE category='tts' AND name='mock'"
            )
            connection.execute(
                "UPDATE provider_configs SET is_default=0 WHERE category='tts' AND name='edge_tts'"
            )
            connection.commit()
        finally:
            connection.close()
        self.routes = {
            (method, route.path): route.endpoint
            for route in main.app.routes
            if hasattr(route, "endpoint")
            for method in (getattr(route, "methods", None) or [])
        }

    def tearDown(self):
        main.config["DB_PATH"] = self.original_db_path
        self.temp_dir.cleanup()

    def _create_draft(self):
        create = self.routes[("POST", "/workflow-drafts")]
        return create(DraftCreateBody(
            source_script="第一段介绍。第二段说明。第三段总结。",
            title="mock-gate test",
        ))

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
            self.routes[("POST", "/workflow-drafts/{draft_id}/confirm")](draft["id"])
            self.fail("Expected LingjianError when tts default is mock")
        except Exception as exc:
            self.assertEqual(getattr(exc, "error_code", None), "MOCK_PROVIDER_BLOCKS_RELEASE")
            self.assertEqual(exc.status_code, 409)
            self.assertEqual(exc.details["mock_providers"][0]["category"], "tts")
            self.assertEqual(exc.details["mock_providers"][0]["name"], "mock")

    def test_confirm_passes_when_all_defaults_are_real(self):
        connection = main.get_db()
        try:
            connection.execute(
                "UPDATE provider_configs SET is_default=1 WHERE category='tts' AND name='edge_tts'"
            )
            connection.execute(
                "UPDATE provider_configs SET is_default=0 WHERE category='tts' AND name='mock'"
            )
            connection.commit()
        finally:
            connection.close()
        draft = self._create_draft()
        confirmed = self.routes[("POST", "/workflow-drafts/{draft_id}/confirm")](draft["id"])
        self.assertEqual(confirmed["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
