"""rev34 P1: refresh token rotation + logout tests."""
import os, sqlite3, sys, time, unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth_router


def _patch_secret():
    s = "test-rot-secret-" + str(os.getpid())
    auth_router.JWT_SECRET = s
    os.environ['FLIKI_JWT_SECRET'] = s
    return s


class RefreshTokenHelpersTest(unittest.TestCase):
    def setUp(self):
        self._orig_secret = _patch_secret()
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE refresh_tokens (id TEXT PRIMARY KEY, user_id TEXT, expires_at INTEGER, created_at INTEGER, revoked_at INTEGER, replaced_by_id TEXT)")
        self.db.commit()

    def tearDown(self):
        auth_router.JWT_SECRET = self._orig_secret
        self.db.close()

    def test_make_refresh_token_returns_pair(self):
        raw, h = auth_router._make_refresh_token()
        self.assertGreater(len(raw), 30)
        self.assertEqual(len(h), 64)
        self.assertEqual(h, auth_router._hash_refresh_token(raw))

    def test_store_then_find(self):
        raw, h = auth_router._make_refresh_token()
        expires = auth_router._store_refresh_token(self.db, "u-1", h, 60)
        self.assertGreater(expires, int(time.time()))
        row = auth_router._find_refresh_token(self.db, h)
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "u-1")
        self.assertIsNone(row[2])

    def test_revoke_sets_revoked_at(self):
        raw, h = auth_router._make_refresh_token()
        auth_router._store_refresh_token(self.db, "u-2", h, 60)
        ok = auth_router._revoke_refresh_token(self.db, h)
        self.assertTrue(ok)
        row = auth_router._find_refresh_token(self.db, h)
        self.assertIsNotNone(row[2])

    def test_revoke_with_replaced_by(self):
        raw1, h1 = auth_router._make_refresh_token()
        _, h2 = auth_router._make_refresh_token()
        auth_router._store_refresh_token(self.db, "u-3", h1, 60)
        auth_router._revoke_refresh_token(self.db, h1, replaced_by=h2)
        replaced = self.db.execute("SELECT replaced_by_id FROM refresh_tokens WHERE id=?", (h1,)).fetchone()
        self.assertEqual(replaced[0], h2)


class RefreshEndpointRotationTest(unittest.TestCase):
    def setUp(self):
        self._orig_secret = _patch_secret()
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE, password_salt TEXT, password_hash TEXT, role TEXT, created_at TEXT, updated_at TEXT)")
        self.db.execute("CREATE TABLE refresh_tokens (id TEXT PRIMARY KEY, user_id TEXT, expires_at INTEGER, created_at INTEGER, revoked_at INTEGER, replaced_by_id TEXT)")
        self.db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)", ("u-rot", "rot@x", "salt", "hash", "user", "t", "t"))
        self.db.commit()
        self.raw_rt, self.h_rt = auth_router._make_refresh_token()
        auth_router._store_refresh_token(self.db, "u-rot", self.h_rt, 60 * 60 * 24 * 30)

    def tearDown(self):
        auth_router.JWT_SECRET = self._orig_secret
        self.db.close()

    def _refresh(self, raw_token):
        import main
        body = auth_router.RefreshBody(refresh_token=raw_token)
        request = mock.MagicMock()
        request.headers = {}
        wrapper = mock.MagicMock(wraps=self.db)
        wrapper.close = mock.MagicMock()
        with mock.patch.object(main, "get_db", return_value=wrapper):
            return auth_router.refresh(request, body)

    def test_rotation_returns_new_tokens(self):
        import main
        from fastapi import HTTPException
        body = auth_router.RefreshBody(refresh_token=self.raw_rt)
        req = mock.MagicMock()
        req.headers = {}
        wrapper = mock.MagicMock(wraps=self.db)
        wrapper.close = mock.MagicMock()
        with mock.patch.object(main, "get_db", return_value=wrapper):
            result = auth_router.refresh(req, body)
        self.assertIn("token", result)
        self.assertIn("refresh_token", result)
        self.assertNotEqual(result["refresh_token"], self.raw_rt)
        row = self.db.execute("SELECT revoked_at, replaced_by_id FROM refresh_tokens WHERE id=?", (self.h_rt,)).fetchone()
        self.assertIsNotNone(row[0])

    def test_revoked_rt_returns_401(self):
        import main
        from fastapi import HTTPException
        auth_router._revoke_refresh_token(self.db, self.h_rt)
        body = auth_router.RefreshBody(refresh_token=self.raw_rt)
        req = mock.MagicMock()
        req.headers = {}
        wrapper = mock.MagicMock(wraps=self.db)
        wrapper.close = mock.MagicMock()
        with mock.patch.object(main, "get_db", return_value=wrapper):
            with self.assertRaises(HTTPException) as ctx:
                auth_router.refresh(req, body)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail["error_code"], "REFRESH_REVOKED")

    def test_invalid_rt_returns_401(self):
        import main
        from fastapi import HTTPException
        body = auth_router.RefreshBody(refresh_token="not-a-real-token-but-long-enough-padding")
        req = mock.MagicMock()
        req.headers = {}
        with mock.patch.object(main, "get_db", return_value=self.db):
            with self.assertRaises(HTTPException) as ctx:
                auth_router.refresh(req, body)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail["error_code"], "REFRESH_INVALID")

    def test_access_token_grace_path_still_works(self):
        import main
        access_tok = auth_router._make_token("u-rot", "user")
        req = mock.MagicMock()
        req.headers = {"Authorization": "Bearer " + access_tok}
        with mock.patch.object(main, "get_db", return_value=self.db):
            result = auth_router.refresh(req, None)
        self.assertIn("token", result)
        self.assertNotIn("refresh_token", result)

    def test_reused_token_revokes_rotated_descendant(self):
        from fastapi import HTTPException

        rotated = self._refresh(self.raw_rt)
        with self.assertRaises(HTTPException) as reused:
            self._refresh(self.raw_rt)
        self.assertEqual(reused.exception.detail["error_code"], "REFRESH_REUSED")

        with self.assertRaises(HTTPException) as descendant:
            self._refresh(rotated["refresh_token"])
        self.assertEqual(descendant.exception.detail["error_code"], "REFRESH_REVOKED")

    def test_rotation_rolls_back_new_token_when_old_revoke_fails(self):
        self.db.execute(
            """
            CREATE TRIGGER fail_refresh_revoke
            BEFORE UPDATE OF revoked_at ON refresh_tokens
            WHEN OLD.id = '%s'
            BEGIN
                SELECT RAISE(ABORT, 'forced rotation failure');
            END
            """ % self.h_rt
        )
        self.db.commit()

        with self.assertRaises(sqlite3.DatabaseError):
            self._refresh(self.raw_rt)

        rows = self.db.execute(
            "SELECT id, revoked_at FROM refresh_tokens ORDER BY created_at"
        ).fetchall()
        self.assertEqual(rows, [(self.h_rt, None)])


class LogoutEndpointTest(unittest.TestCase):
    def setUp(self):
        self._orig_secret = _patch_secret()
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE refresh_tokens (id TEXT PRIMARY KEY, user_id TEXT, expires_at INTEGER, created_at INTEGER, revoked_at INTEGER, replaced_by_id TEXT)")
        self.db.commit()
        self.raw_rt, self.h_rt = auth_router._make_refresh_token()
        auth_router._store_refresh_token(self.db, "u-x", self.h_rt, 60)

    def tearDown(self):
        auth_router.JWT_SECRET = self._orig_secret
        self.db.close()

    def test_logout_revokes_rt(self):
        import main
        body = auth_router.LogoutBody(refresh_token=self.raw_rt)
        wrapper = mock.MagicMock(wraps=self.db)
        wrapper.close = mock.MagicMock()
        with mock.patch.object(main, "get_db", return_value=wrapper):
            result = auth_router.logout(body)
        self.assertEqual(result, {"revoked": True})
        row = self.db.execute("SELECT revoked_at FROM refresh_tokens WHERE id=?", (self.h_rt,)).fetchone()
        self.assertIsNotNone(row[0])


class PublicRegistrationSecurityTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE, password_salt TEXT, password_hash TEXT, role TEXT, created_at TEXT, updated_at TEXT)")
        self.db.execute("CREATE TABLE refresh_tokens (id TEXT PRIMARY KEY, user_id TEXT, expires_at INTEGER, created_at INTEGER, revoked_at INTEGER, replaced_by_id TEXT)")
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_public_register_rejects_admin_role(self):
        import main
        from fastapi import HTTPException

        body = auth_router.RegisterBody(email="attacker@example.com", password="strong-password", role="admin")
        request = mock.MagicMock()
        wrapper = mock.MagicMock(wraps=self.db)
        wrapper.close = mock.MagicMock()
        with mock.patch.object(main, "get_db", return_value=wrapper):
            with self.assertRaises(HTTPException) as ctx:
                auth_router.register(body, request)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["error_code"], "ADMIN_REGISTRATION_DISABLED")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_register_duplicate_email_is_case_insensitive(self):
        import main
        from fastapi import HTTPException

        self.db.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("existing", "person@example.com", "salt", "hash", "user", "t", "t"),
        )
        self.db.commit()
        body = auth_router.RegisterBody(
            email="PERSON@EXAMPLE.COM",
            password="strong-password",
            role="user",
        )
        request = mock.MagicMock()
        wrapper = mock.MagicMock(wraps=self.db)
        wrapper.close = mock.MagicMock()
        with mock.patch.object(main, "get_db", return_value=wrapper):
            with self.assertRaises(HTTPException) as ctx:
                auth_router.register(body, request)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["error_code"], "EMAIL_EXISTS")


if __name__ == "__main__":
    unittest.main()
