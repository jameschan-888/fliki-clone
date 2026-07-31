"""Unit + integration tests for scripts/_b_repeat.py per-round-user logic.

rev24 阶段 C P1-A:
  - get_token_for_round(1) != get_token_for_round(2)  (independent users)
  - same idx returns cached token (no double register)
  - each result row carries user_id/user_email fields
  - 集成测试验证真实 /auth/register 返回 token (3 segments JWT)
"""
import json, os, sys, unittest, urllib.request
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import _b_repeat  # noqa: E402


def _backend_alive() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:5181/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


class TokenPerRoundUnitTests(unittest.TestCase):
    """纯单测: 不连后端, mock 掉 _register_user."""

    def setUp(self):
        _b_repeat._TOKEN_CACHE.clear()

    def test_independent_users_per_round(self):
        counter = {"n": 0}

        def fake_register(idx):
            counter["n"] += 1
            return {"token": f"tok-r{idx}-n{counter['n']}", "user_id": f"u{counter['n']}", "email": f"r{idx}@e.com"}

        with mock.patch.object(_b_repeat, "_register_user", side_effect=fake_register):
            t1 = _b_repeat.get_token_for_round(1)
            t2 = _b_repeat.get_token_for_round(2)
        self.assertNotEqual(t1, t2, "round 1/2 must have different tokens (independent users)")
        self.assertEqual(t1, "tok-r1-n1")
        self.assertEqual(t2, "tok-r2-n2")

    def test_same_round_caches_token(self):
        counter = {"n": 0}

        def fake_register(idx):
            counter["n"] += 1
            return {"token": f"tok-n{counter['n']}", "user_id": f"u{counter['n']}", "email": f"r{idx}@e.com"}

        with mock.patch.object(_b_repeat, "_register_user", side_effect=fake_register):
            t1 = _b_repeat.get_token_for_round(3)
            t2 = _b_repeat.get_token_for_round(3)
        self.assertEqual(t1, t2, "same round must return cached token, not re-register")
        self.assertEqual(counter["n"], 1, "_register_user must be called only once for same round")

    def test_auth_headers_includes_bearer(self):
        with mock.patch.object(_b_repeat, "get_token_for_round", return_value="abc.def.ghi"):
            h = _b_repeat._auth_headers(5)
        self.assertEqual(h, {"Authorization": "Bearer abc.def.ghi"})

    def test_cache_isolates_per_round(self):
        with mock.patch.object(_b_repeat, "_register_user",
                               side_effect=lambda i: {"token": f"t{i}", "user_id": f"u{i}", "email": f"r{i}@e.com"}):
            _b_repeat.get_token_for_round(10)
            _b_repeat.get_token_for_round(11)
            _b_repeat.get_token_for_round(12)
        self.assertEqual(set(_b_repeat._TOKEN_CACHE.keys()), {10, 11, 12})
        self.assertEqual(_b_repeat._TOKEN_CACHE[10]["user_id"], "u10")
        self.assertEqual(_b_repeat._TOKEN_CACHE[11]["user_id"], "u11")
        self.assertEqual(_b_repeat._TOKEN_CACHE[12]["user_id"], "u12")


class TokenPerRoundIntegrationTests(unittest.TestCase):
    """集成测试: 真实连后端 127.0.0.1:5181, 验证 register 返回字段."""

    @classmethod
    def setUpClass(cls):
        if not _backend_alive():
            raise unittest.SkipTest("backend 127.0.0.1:5181 unreachable, skip integration")

    def setUp(self):
        _b_repeat._TOKEN_CACHE.clear()

    def test_real_register_returns_token_and_user(self):
        info = _b_repeat._register_user(999001)
        self.assertIn("token", info)
        self.assertIn("user_id", info)
        self.assertIn("email", info)
        self.assertEqual(len(info["token"].split(".")), 3, "JWT must have 3 segments")
        self.assertTrue(info["user_id"], "user_id must be non-empty")
        self.assertTrue(info["email"].startswith("repeat-r999001-"))

    def test_get_token_for_round_returns_different_users(self):
        a = _b_repeat.get_token_for_round(901001)
        b = _b_repeat.get_token_for_round(901002)
        ua = _b_repeat._TOKEN_CACHE[901001]["user_id"]
        ub = _b_repeat._TOKEN_CACHE[901002]["user_id"]
        self.assertNotEqual(a, b, "tokens differ across rounds")
        self.assertNotEqual(ua, ub, "user_ids differ across rounds")

    def test_token_can_auth_me(self):
        """用注册的 token 调 /auth/me, 验证 token 真能用."""
        info = _b_repeat._register_user(901003)
        req = urllib.request.Request(
            "http://127.0.0.1:5181/auth/me",
            headers={"Authorization": "Bearer " + info["token"]},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            me = json.loads(r.read().decode("utf-8"))
        self.assertEqual(me["user"]["id"], info["user_id"])
        self.assertEqual(me["user"]["email"], info["email"])


if __name__ == "__main__":
    unittest.main()
