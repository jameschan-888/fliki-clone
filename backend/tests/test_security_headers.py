"""rev35 P0-1: CORS whitelist + security headers 兜底测试.

不动线上请求, 用 TestClient 直接打应用, 校验响应头. CORS 单独构造 Origin 头覆盖.
"""
import os
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# 关闭 main.py 启动时对 .env 的副作用, 用最少依赖构造受测 client.
os.environ.setdefault("FLIKI_JWT_SECRET", "test-cors-secret-32chars-padding-xx")
os.environ.setdefault("FLIKI_ENV", "dev")

from main import app  # noqa: E402  必须在 env 之后 import


class SecurityHeadersContractTest(unittest.TestCase):
    """默认响应必须携带 5 个安全头."""

    def setUp(self):
        self.client = TestClient(app)

    def test_security_headers_present_on_root(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        headers = response.headers
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(headers.get("x-frame-options"), "DENY")
        self.assertEqual(headers.get("referrer-policy"), "no-referrer")
        self.assertIn("content-security-policy", {k.lower() for k in headers})
        csp = headers.get("content-security-policy", "")
        self.assertIn("default-src", csp)
        self.assertIn("frame-ancestors 'none'", csp)

    def test_security_headers_present_on_error(self):
        response = self.client.get("/__nope_does_not_exist__")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(response.headers.get("x-frame-options"), "DENY")


class CorsWhitelistTest(unittest.TestCase):
    """CORS 应当按 env 白名单放行; 不在白名单的 Origin 不带 ACAO 头."""

    def setUp(self):
        os.environ["FLIKI_ALLOWED_ORIGINS"] = "http://127.0.0.1:5180,http://localhost:5180"
        # 重新 import main 让 CORSMiddleware 重新读 env. FastAPI 缓存模块, 只能 reload.
        import importlib
        import main as main_module
        importlib.reload(main_module)
        self.client = TestClient(main_module.app)

    def tearDown(self):
        os.environ.pop("FLIKI_ALLOWED_ORIGINS", None)

    def test_allowed_origin_gets_acao(self):
        response = self.client.get("/health", headers={"Origin": "http://127.0.0.1:5180"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://127.0.0.1:5180")

    def test_disallowed_origin_has_no_acao(self):
        response = self.client.get("/health", headers={"Origin": "https://attacker.example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_preflight_allowed_origin(self):
        response = self.client.options(
            "/auth/login",
            headers={
                "Origin": "http://127.0.0.1:5180",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://127.0.0.1:5180")
        self.assertIn("POST", response.headers.get("access-control-allow-methods", ""))
