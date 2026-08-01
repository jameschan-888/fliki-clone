"""rev33 P1-B: /auth/refresh + _decode_token_lenient 测试."""
import os, sqlite3, sys, time, unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth_router


class _FakeRequest:
    def __init__(self, token=None):
        self.headers = {'Authorization': 'Bearer ' + token} if token else {}


def _patch_secret():
    s = "test-refresh-secret-" + str(os.getpid())
    auth_router.JWT_SECRET = s
    os.environ['FLIKI_JWT_SECRET'] = s
    return s


class DecodeTokenLenientTest(unittest.TestCase):
    def setUp(self):
        self._orig_secret = _patch_secret()

    def tearDown(self):
        auth_router.JWT_SECRET = self._orig_secret

    def test_unexpired_token_decodes(self):
        tok = auth_router._make_token("u-1", "user")
        p = auth_router._decode_token_lenient(tok)
        self.assertIsNotNone(p)
        self.assertEqual(p["sub"], "u-1")
        self.assertEqual(p["role"], "user")

    def test_expired_within_grace_decodes(self):
        # exp 已过 1 天, grace 默认 30 天, 应通过.
        tok = auth_router._make_token("u-2", "user")
        # 手造过期 token
        import hmac, hashlib, json
        header = json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",",":")).encode()
        past = int(time.time()) - 86400
        payload = json.dumps({"sub":"u-2","role":"user","iat":past-100,"exp":past}, separators=(",",":")).encode()
        h64 = auth_router._b64u(header)
        p64 = auth_router._b64u(payload)
        sig = hmac.new(auth_router.JWT_SECRET.encode(), f"{h64}.{p64}".encode(), hashlib.sha256).digest()
        expired_tok = f"{h64}.{p64}.{auth_router._b64u_bytes(sig)}"
        p = auth_router._decode_token_lenient(expired_tok)
        self.assertIsNotNone(p)
        self.assertEqual(p["sub"], "u-2")

    def test_expired_beyond_grace_returns_none(self):
        import hmac, hashlib, json
        past = int(time.time()) - 60 * 60 * 24 * 60  # 60 天前
        header = json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",",":")).encode()
        payload = json.dumps({"sub":"u-3","role":"user","iat":past-100,"exp":past}, separators=(",",":")).encode()
        h64 = auth_router._b64u(header)
        p64 = auth_router._b64u(payload)
        sig = hmac.new(auth_router.JWT_SECRET.encode(), f"{h64}.{p64}".encode(), hashlib.sha256).digest()
        old_tok = f"{h64}.{p64}.{auth_router._b64u_bytes(sig)}"
        self.assertIsNone(auth_router._decode_token_lenient(old_tok))

    def test_tampered_signature_returns_none(self):
        tok = auth_router._make_token("u-4", "user")
        h, p, s = tok.split(".")
        bad = h + "." + p + "." + ("A" * len(s))
        self.assertIsNone(auth_router._decode_token_lenient(bad))


class RefreshEndpointTest(unittest.TestCase):
    """测 /auth/refresh 端点: valid token + 存在 user 返回新 token."""

    def setUp(self):
        self._orig_secret = _patch_secret()
        # 准备 in-memory users db
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE, password_salt TEXT, password_hash TEXT, role TEXT, created_at TEXT, updated_at TEXT)")
        self.db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)", ("u-x", "x@x", "salt", "hash", "user", "t", "t"))
        self.db.commit()

    def tearDown(self):
        auth_router.JWT_SECRET = self._orig_secret
        self.db.close()

    def test_valid_token_returns_new_token(self):
        import main
        tok = auth_router._make_token("u-x", "user")
        req = _FakeRequest(tok)
        with mock.patch.object(main, "get_db", return_value=self.db):
            from fastapi import HTTPException
            # 直接调路由函数 (FastAPI Depends 解析会有问题, 直接 invoke 即可)
            result = auth_router.refresh(req)
        self.assertIn("token", result)
        self.assertEqual(result["user"]["id"], "u-x")
        # 新 token 也要能解
        self.assertIsNotNone(auth_router._decode_token(result["token"]))

    def test_missing_bearer_returns_401(self):
        import main
        req = _FakeRequest(None)
        with mock.patch.object(main, "get_db", return_value=self.db):
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as ctx:
                auth_router.refresh(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail["error_code"], "MISSING_TOKEN")

    def test_unknown_user_returns_401(self):
        import main
        tok = auth_router._make_token("u-deleted", "user")
        req = _FakeRequest(tok)
        with mock.patch.object(main, "get_db", return_value=self.db):
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as ctx:
                auth_router.refresh(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail["error_code"], "USER_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
