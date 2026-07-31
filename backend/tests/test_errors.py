"""rev24 阶段 D D3: test_errors.py 重写测当前 errors.py API."""
import unittest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from errors import (
    ERR_BAD_REQUEST,
    ERR_INVALID_CREDENTIALS,
    ERR_MISSING_TOKEN,
    ERR_TOKEN_EXPIRED,
    ERR_ADMIN_ONLY,
    ERR_FORBIDDEN,
    ERR_NOT_FOUND,
    ERR_USER_NOT_FOUND,
    ERR_RESOURCE_NOT_FOUND,
    ERR_CONFLICT,
    ERR_EMAIL_EXISTS,
    ERR_ALREADY_EXISTS,
    ERR_INVALID_STATE,
    ERR_VALIDATION_ERROR,
    ERR_RATE_LIMITED,
    ERR_INTERNAL_ERROR,
    ERR_PROVIDER_DOWN,
    ERR_SERVICE_UNAVAILABLE,
    ERR_UNKNOWN,
    DEFAULT_ERROR_CODE_BY_STATUS,
    make_error_response,
    normalize_http_exception_detail,
    register_error_handlers,
)


class ErrorsConstantsTest(unittest.TestCase):
    """D2-1 错误码常量应全 snake_case + 18 个."""

    def test_all_error_codes_are_snake_case_strings(self):
        names = [
            ERR_BAD_REQUEST, ERR_INVALID_CREDENTIALS, ERR_MISSING_TOKEN, ERR_TOKEN_EXPIRED,
            ERR_ADMIN_ONLY, ERR_FORBIDDEN, ERR_NOT_FOUND, ERR_USER_NOT_FOUND,
            ERR_RESOURCE_NOT_FOUND, ERR_CONFLICT, ERR_EMAIL_EXISTS,
            ERR_ALREADY_EXISTS, ERR_INVALID_STATE, ERR_VALIDATION_ERROR,
            ERR_RATE_LIMITED, ERR_INTERNAL_ERROR, ERR_PROVIDER_DOWN,
            ERR_SERVICE_UNAVAILABLE, ERR_UNKNOWN,
        ]
        for code in names:
            self.assertIsInstance(code, str)
            self.assertTrue(code.replace("_", "").isalnum(),
                            "must be snake_case alnum: " + code)
        self.assertEqual(len(names), 19)

    def test_default_code_by_status_keys(self):
        """DEFAULT_ERROR_CODE_BY_STATUS 应覆盖 400/401/403/404/409/422/429/500/502/503."""
        for status in (400, 401, 403, 404, 409, 422, 429, 500, 502, 503):
            self.assertIn(status, DEFAULT_ERROR_CODE_BY_STATUS)
            self.assertIsInstance(DEFAULT_ERROR_CODE_BY_STATUS[status], str)


class MakeErrorResponseTest(unittest.TestCase):
    def test_full_args(self):
        body = make_error_response(
            409, ERR_CONFLICT, "email 已存在", "换邮箱", {"email": "x@y.z"}
        )
        self.assertEqual(body["error_code"], ERR_CONFLICT)
        self.assertEqual(body["message"], "email 已存在")
        self.assertEqual(body["hint"], "换邮箱")
        self.assertEqual(body["details"], {"email": "x@y.z"})
        self.assertEqual(body["status"], 409)

    def test_minimal_args(self):
        body = make_error_response(404)
        self.assertEqual(body["error_code"], ERR_NOT_FOUND)
        self.assertEqual(body["message"], "")
        self.assertEqual(body["hint"], "")
        self.assertEqual(body["details"], {})
        self.assertEqual(body["status"], 404)

    def test_unknown_status_uses_unknown_code(self):
        body = make_error_response(418)
        self.assertEqual(body["error_code"], ERR_UNKNOWN)


class NormalizeHttpExceptionDetailTest(unittest.TestCase):
    def test_dict_passthrough(self):
        d = {"error_code": ERR_VALIDATION_ERROR, "message": "x", "hint": "y", "details": {"a": 1}, "status": 422}
        out = normalize_http_exception_detail(d)
        self.assertEqual(out["error_code"], ERR_VALIDATION_ERROR)
        self.assertEqual(out["message"], "x")
        self.assertEqual(out["details"], {"a": 1})

    def test_dict_partial_filled(self):
        out = normalize_http_exception_detail({"message": "hi"})
        self.assertEqual(out["error_code"], "")
        self.assertEqual(out["message"], "hi")
        self.assertEqual(out["details"], {})

    def test_string_wraps_to_message(self):
        out = normalize_http_exception_detail("not found")
        self.assertEqual(out["error_code"], "")
        self.assertEqual(out["message"], "not found")

    def test_none_returns_empty(self):
        out = normalize_http_exception_detail(None)
        self.assertEqual(out["message"], "")

    def test_non_str_non_dict_stringified(self):
        out = normalize_http_exception_detail(42)
        self.assertEqual(out["message"], "42")


class RegisterErrorHandlersTest(unittest.TestCase):
    """注册 3 个 handler, 验证真实 HTTPException 走统一格式."""

    def _make_app(self):
        app = FastAPI()
        register_error_handlers(app)

        @app.get("/raise-http")
        def _raise_http():
            raise HTTPException(status_code=409, detail="email 已存在")

        @app.get("/raise-dict")
        def _raise_dict():
            raise HTTPException(
                status_code=422,
                detail={"error_code": ERR_VALIDATION_ERROR, "message": "x", "hint": "y", "details": {"a": 1}},
            )

        @app.get("/raise-unhandled")
        def _raise_unhandled():
            raise RuntimeError("boom")

        return app

    def test_http_exception_string_detail(self):
        app = self._make_app()
        client = TestClient(app)
        r = client.get("/raise-http")
        self.assertEqual(r.status_code, 409)
        body = r.json()
        self.assertEqual(body["error_code"], ERR_CONFLICT)
        self.assertEqual(body["message"], "email 已存在")
        self.assertEqual(body["status"], 409)

    def test_http_exception_dict_detail_passthrough(self):
        app = self._make_app()
        client = TestClient(app)
        r = client.get("/raise-dict")
        self.assertEqual(r.status_code, 422)
        body = r.json()
        self.assertEqual(body["error_code"], ERR_VALIDATION_ERROR)
        self.assertEqual(body["details"], {"a": 1})

    def test_unhandled_exception_returns_500(self):
        app = self._make_app()
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/raise-unhandled")
        self.assertEqual(r.status_code, 500)
        body = r.json()
        self.assertEqual(body["error_code"], ERR_INTERNAL_ERROR)
        # 不应泄露 stack 信息
        self.assertNotIn("traceback", body)
        self.assertNotIn("RuntimeError", str(body.get("message", "")))


if __name__ == "__main__":
    unittest.main()
