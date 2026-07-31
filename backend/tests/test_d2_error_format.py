"""rev24 阶段 D D2-1: 统一错误响应格式."""
import json
import time
import unittest
import urllib.request
import urllib.error

BACKEND = "http://127.0.0.1:5181"


def _req(method, path, data=None, headers=None):
    url = BACKEND + path
    body = json.dumps(data).encode() if data is not None else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}


def _register_and_login():
    email = "d2test_" + str(int(time.time() * 1000)) + "@fliki.com"
    _req("POST", "/auth/register", {"email": email, "password": "test12345"})
    s2, d2 = _req("POST", "/auth/login", {"email": email, "password": "test12345"})
    return d2.get("token") or ""


class D2ErrorFormatTests(unittest.TestCase):
    def test_401_missing_token_has_error_code(self):
        status, body = _req("GET", "/auth/me")
        self.assertEqual(status, 401)
        self.assertIn("error_code", body)
        self.assertEqual(body["error_code"], "MISSING_TOKEN")
        self.assertIn("message", body)
        self.assertIn("hint", body)
        self.assertIn("details", body)
        self.assertEqual(body["status"], 401)

    def test_401_wrong_password_has_error_code(self):
        status, body = _req("POST", "/auth/login", {"email": "nobody@xxx.com", "password": "wrong"})
        self.assertEqual(status, 401)
        self.assertEqual(body["error_code"], "INVALID_CREDENTIALS")
        self.assertIn("message", body)
        self.assertIn("hint", body)

    def test_409_email_exists_has_error_code(self):
        email = "d2dup_" + str(int(time.time() * 1000)) + "@fliki.com"
        s1, _ = _req("POST", "/auth/register", {"email": email, "password": "test12345"})
        self.assertEqual(s1, 200)
        s2, body = _req("POST", "/auth/register", {"email": email, "password": "test12345"})
        self.assertEqual(s2, 409)
        self.assertEqual(body["error_code"], "EMAIL_EXISTS")
        self.assertIn("message", body)
        self.assertIn("hint", body)

    def test_404_resource_not_found_has_error_code(self):
        status, body = _req("GET", "/render-jobs/bogus-id-xxx")
        self.assertEqual(status, 404)
        self.assertIn("error_code", body)
        self.assertEqual(body["error_code"], "NOT_FOUND")
        self.assertIn("message", body)
        self.assertEqual(body["status"], 404)

    def test_403_admin_only_has_error_code(self):
        tok = _register_and_login()
        self.assertTrue(tok)
        status, body = _req("GET", "/auth/users", headers={"Authorization": "Bearer " + tok})
        self.assertEqual(status, 403)
        self.assertEqual(body["error_code"], "ADMIN_ONLY")
        self.assertIn("message", body)

    def test_422_validation_error_has_error_code(self):
        status, body = _req("POST", "/auth/register", {"email": "not-valid-email"})
        self.assertEqual(status, 422)
        self.assertEqual(body["error_code"], "VALIDATION_ERROR")
        self.assertIn("details", body)
        self.assertIn("errors", body["details"])

    def test_200_success_no_error_code(self):
        status, body = _req("GET", "/health")
        self.assertEqual(status, 200)
        self.assertNotIn("error_code", body)
        self.assertEqual(body.get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
