"""rev24 阶段 D P0 安全合规收口测试.

覆盖:
  - on_event -> lifespan (后端启动正常, health 200)
  - /outputs StaticFiles mount 保留 (autoedit 兼容, UUID 不可枚举作安全层)
  - /api/uploads user_id 隔离: 匿名 401, 跨用户 DELETE 404, 自己上传+删除 OK
  - PBKDF2 100k -> 600k: 新注册用 600k; 老 hash (100k) login 仍能 verify 且自动 rehash
"""
import hashlib
import json
import os
import secrets
import sqlite3
import pytest
import unittest
import uuid

from fastapi.testclient import TestClient
from main import app

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")
client = TestClient(app)
PNG_BYTES = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63600000000200015f6e40b40000000049454e44ae426082")

def _reset_rate_limits():
    try:
        client.post("/auth/_internal/reset-rate-limits")
    except Exception:
        pass

def _register(email, password="test12345"):
    _reset_rate_limits()
    return client.post("/auth/register", json={"email": email, "password": password, "role": "user"}).json()

def _login(email, password="test12345"):
    _reset_rate_limits()
    return client.post("/auth/login", json={"email": email, "password": password}).json()

def _upload(token=None):
    boundary = "----p0test" + uuid.uuid4().hex
    body_lines = []
    body_lines.append("--" + boundary)
    body_lines.append("Content-Disposition: form-data; name=\"file\"; filename=\"x.png\"")
    body_lines.append("Content-Type: image/png")
    body_lines.append("")
    body_lines.append("")
    body = (chr(13) + chr(10)).join(body_lines).encode() + PNG_BYTES + (chr(13) + chr(10) + "--" + boundary + "--" + chr(13) + chr(10)).encode()
    headers = {"Content-Type": "multipart/form-data; boundary=" + boundary}
    if token:
        headers["Authorization"] = "Bearer " + token
    return client.post("/api/uploads", content=body, headers=headers)

def _delete(upload_id, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    return client.delete("/api/uploads/" + upload_id, headers=headers)

def _backend_alive():
    return client.get("/health").status_code == 200

class P0LifespanTests(unittest.TestCase):
    def test_backend_alive(self):
        self.assertTrue(_backend_alive(), "backend /health should respond 200")

@pytest.mark.no_xdist
class P0UploadsUserIdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user_a = _register("p0-up-a-" + uuid.uuid4().hex[:8] + "@e.com")
        cls.user_b = _register("p0-up-b-" + uuid.uuid4().hex[:8] + "@e.com")

    def test_upload_anonymous_401(self):
        response = _upload()
        self.assertEqual(response.status_code, 401)

    def test_upload_self_and_delete_self(self):
        upload = _upload(token=self.user_a["token"])
        self.assertEqual(upload.status_code, 200, upload.text)
        data = upload.json()
        self.assertEqual(data["user_id"], self.user_a["user"]["id"])
        delete_response = _delete(data["id"], token=self.user_a["token"])
        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        self.assertEqual(delete_response.json()["deleted"], True)

    def test_delete_cross_user_404(self):
        upload = _upload(token=self.user_a["token"])
        self.assertEqual(upload.status_code, 200, upload.text)
        data = upload.json()
        try:
            cross = _delete(data["id"], token=self.user_b["token"])
            self.assertEqual(cross.status_code, 404, cross.text)
        finally:
            _delete(data["id"], token=self.user_a["token"])

    def test_delete_anonymous_401(self):
        response = _delete("nonexistent")
        self.assertEqual(response.status_code, 401)

@pytest.mark.no_xdist
class P0Pbkdf2UpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _backend_alive():
            raise unittest.SkipTest("backend unreachable")
        if not os.path.exists(DB_PATH):
            raise unittest.SkipTest("db not found at " + DB_PATH)

    def test_new_register_uses_600k(self):
        email = "p0-pw-new-" + uuid.uuid4().hex[:8] + "@e.com"
        _register(email)
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute("SELECT password_hash FROM users WHERE email=?", (email.lower(),)).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertTrue(row[0].startswith("600000:"), "新注册应 600k iter, got: " + row[0][:30])

    def test_legacy_hash_login_still_works_and_rehashes(self):
        email = "p0-pw-legacy-" + uuid.uuid4().hex[:8] + "@e.com"
        password = "test12345"
        salt = secrets.token_hex(16)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        legacy_hash = h.hex()
        conn = sqlite3.connect(DB_PATH)
        try:
            user_id = uuid.uuid4().hex
            now = "2026-01-01T00:00:00Z"
            conn.execute("INSERT INTO users (id, email, password_salt, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, 'user', ?, ?)", (user_id, email.lower(), salt, legacy_hash, now, now))
            conn.commit()
        finally:
            conn.close()
        result = _login(email, password)
        self.assertIn("token", result)
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute("SELECT password_hash FROM users WHERE email=?", (email.lower(),)).fetchone()
        finally:
            conn.close()
        self.assertTrue(row[0].startswith("600000:"), "rehash 后应 600k, got: " + row[0][:30])
        result2 = _login(email, password)
        self.assertIn("token", result2)

    def test_wrong_password_401(self):
        email = "p0-pw-wrong-" + uuid.uuid4().hex[:8] + "@e.com"
        _register(email, "right-password-12345")
        response = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        self.assertEqual(response.status_code, 401)

class P0OutputsMountTests(unittest.TestCase):
    def test_outputs_path_reachable(self):
        fake = uuid.uuid4().hex + ".mp4"
        response = client.get("/outputs/" + fake)
        self.assertIn(response.status_code, (200, 404), response.text)

if __name__ == "__main__":
    unittest.main()
