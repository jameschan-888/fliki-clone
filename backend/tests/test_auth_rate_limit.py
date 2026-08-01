"""rev35 P0-3: /auth/login + /auth/register 限速 contract."""
import os
import unittest

os.environ.setdefault("FLIKI_JWT_SECRET", "test-rate-secret-32chars-padding-xx")
os.environ.setdefault("FLIKI_ENV", "dev")

import rate_limit  # noqa: F401
from main import app  # noqa: E402
from fastapi.testclient import TestClient


class _BaseRLTest(unittest.TestCase):
    def setUp(self):
        from auth_router import _LOGIN_LIMITER, _REGISTER_LIMITER
        _LOGIN_LIMITER.reset()
        _REGISTER_LIMITER.reset()
        self.client = TestClient(app)

    def assert_rate_limited(self, response):
        self.assertEqual(response.status_code, 429)
        # register_error_handlers 把 detail 序列化为顶层 {error_code, message, ...}
        body = response.json()
        self.assertEqual(body.get("error_code"), "RATE_LIMITED", body)


class LoginRateLimitTest(_BaseRLTest):
    def test_login_rate_limit_after_5_attempts(self):
        for i in range(5):
            response = self.client.post(
                "/auth/login",
                json={"email": f"u{i}@nope.com", "password": "wrong-pw"},
            )
            self.assertIn(response.status_code, (401, 400))
        self.assert_rate_limited(self.client.post(
            "/auth/login",
            json={"email": "u6@nope.com", "password": "wrong-pw"},
        ))


class RegisterRateLimitTest(_BaseRLTest):
    def test_register_rate_limit_after_5_attempts(self):
        for i in range(5):
            response = self.client.post(
                "/auth/register",
                json={"email": f"rl-{i}-{os.urandom(2).hex()}@nope.com", "password": "long-enough-pw"},
            )
            self.assertIn(response.status_code, (200, 409))
        self.assert_rate_limited(self.client.post(
            "/auth/register",
            json={"email": "rl-6@nope.com", "password": "long-enough-pw"},
        ))
