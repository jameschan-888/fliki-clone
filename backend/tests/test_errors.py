import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from errors import (
    LingjianError,
    ErrorResult,
    MOCK_PROVIDER_BLOCKS_RELEASE,
    to_http_exception,
    register_error_handlers,
)


class LingjianErrorTest(unittest.TestCase):
    def test_to_result_carries_all_fields(self):
        exc = LingjianError(
            error_code=MOCK_PROVIDER_BLOCKS_RELEASE,
            message_zh="Mock provider 不能 release",
            hint="在 .env 替换为真实 API Key",
            details={"category": "tts", "provider": "edge_tts"},
            status_code=409,
        )
        result = exc.to_result()
        self.assertIsInstance(result, ErrorResult)
        self.assertEqual(result.error_code, MOCK_PROVIDER_BLOCKS_RELEASE)
        self.assertEqual(result.message_zh, "Mock provider 不能 release")
        self.assertEqual(result.hint, "在 .env 替换为真实 API Key")
        self.assertEqual(result.details["provider"], "edge_tts")

    def test_default_status_and_details(self):
        exc = LingjianError("X", "msg")
        self.assertEqual(exc.status_code, 400)
        self.assertEqual(exc.details, {})

    def test_to_http_exception_wraps_dict_detail(self):
        exc = LingjianError("E1", "中文消息", hint="hint", details={"a": 1}, status_code=422)
        http_exc = to_http_exception(exc)
        self.assertEqual(http_exc.status_code, 422)
        self.assertIn("error_code", http_exc.detail)
        self.assertEqual(http_exc.detail["message_zh"], "中文消息")


class RegisterErrorHandlersTest(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        register_error_handlers(self.app)
        self.client = TestClient(self.app, raise_server_exceptions=False)

        @self.app.get("/lingjian")
        def _lingjian():
            raise LingjianError(
                "PROVIDER_AUTH_FAILED",
                "Provider 鉴权失败",
                hint="检查 API Key",
                details={"provider": "pexels"},
                status_code=401,
            )

        @self.app.get("/legacy")
        def _legacy():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="not found string")

        @self.app.get("/boom")
        def _boom():
            raise RuntimeError("oops")

    def test_lingjian_handler_returns_unified_body(self):
        response = self.client.get("/lingjian")
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error_code"], "PROVIDER_AUTH_FAILED")
        self.assertEqual(body["message"], "Provider 鉴权失败")
        self.assertEqual(body["hint"], "检查 API Key")
        self.assertEqual(body["details"]["provider"], "pexels")

    def test_legacy_http_exception_wraps_string_detail(self):
        response = self.client.get("/legacy")
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["error_code"], "NOT_FOUND")
        self.assertEqual(body["message"], "not found string")

    def test_unhandled_exception_returns_unknown_error(self):
        response = self.client.get("/boom")
        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["error_code"], "UNKNOWN_ERROR")
        self.assertIn("oops", body["message"])


if __name__ == "__main__":
    unittest.main()
