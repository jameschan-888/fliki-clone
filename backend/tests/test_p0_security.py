"""rev24 阶段 D P0 安全合规收口测试.

覆盖:
  - on_event → lifespan (后端启动正常, health 200)
  - /outputs StaticFiles mount 保留 (autoedit 兼容, UUID 不可枚举作安全层)
  - /api/uploads user_id 隔离: 匿名 401, 跨用户 DELETE 404, 自己上传+删除 OK
  - PBKDF2 100k → 600k: 新注册用 600k; 老 hash (100k) login 仍能 verify 且自动 rehash
"""
import hashlib, hmac, json, os, secrets, sqlite3, sys, unittest, urllib.error, urllib.request, uuid

BACKEND = "http://127.0.0.1:5181"
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")


def _reset_rate_limits():
    try:
        req = urllib.request.Request(BACKEND + "/auth/_internal/reset-rate-limits", method="POST")
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _register(email: str, password: str = "test12345") -> dict:
    _reset_rate_limits()
    body = json.dumps({"email": email, "password": password, "role": "user"}).encode()
    req = urllib.request.Request(BACKEND + "/auth/register", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _login(email: str, password: str = "test12345") -> dict:
    _reset_rate_limits()
    body = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(BACKEND + "/auth/login", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _auth_headers(token: str | None) -> dict:
    if not token:
        return {"Content-Type": "application/json"}
    return {"Authorization": "Bearer " + token, "Content-Type": "application/json"}


def _backend_alive() -> bool:
    try:
        with urllib.request.urlopen(BACKEND + "/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


class P0LifespanTests(unittest.TestCase):
    """P0-1: on_event → lifespan 后端启动正常."""

    def test_backend_alive(self):
        self.assertTrue(_backend_alive(), "backend 5181 should respond /health 200")


class P0UploadsUserIdTests(unittest.TestCase):
    """P0-3: /api/uploads user_id 隔离."""

    @classmethod
    def setUpClass(cls):
        if not _backend_alive():
            raise unittest.SkipTest("backend unreachable")
        cls.user_a = _register("p0-up-a-" + uuid.uuid4().hex[:8] + "@e.com")
        cls.user_b = _register("p0-up-b-" + uuid.uuid4().hex[:8] + "@e.com")

    def test_upload_anonymous_401(self):
        """匿名上传 → 401."""
        # 构造一个最小的有效 PNG (1x1)
        png_bytes = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63600000000200015f6e40b40000000049454e44ae426082")
        boundary = "----p0test" + uuid.uuid4().hex
        body = (f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"file\"; filename=\"x.png\"\r\n"
                f"Content-Type: image/png\r\n\r\n").encode() + png_bytes + (f"\r\n--{boundary}--\r\n").encode()
        req = urllib.request.Request(BACKEND + "/api/uploads", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(cm.exception.code, 401)

    def test_upload_self_and_delete_self(self):
        """自己上传 → 自己删除 → OK."""
        png_bytes = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63600000000200015f6e40b40000000049454e44ae426082")
        boundary = "----p0test" + uuid.uuid4().hex
        body = (f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"file\"; filename=\"y.png\"\r\n"
                f"Content-Type: image/png\r\n\r\n").encode() + png_bytes + (f"\r\n--{boundary}--\r\n").encode()
        req = urllib.request.Request(BACKEND + "/api/uploads", data=body,
                                     headers=_auth_headers(self.user_a["token"]) | {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        self.assertEqual(data["user_id"], self.user_a["user"]["id"])
        # 删自己的 → OK
        req2 = urllib.request.Request(BACKEND + "/api/uploads/" + data["id"], method="DELETE",
                                      headers=_auth_headers(self.user_a["token"]))
        with urllib.request.urlopen(req2, timeout=10) as r:
            d = json.loads(r.read().decode())
        self.assertEqual(d["deleted"], True)

    def test_delete_cross_user_404(self):
        """A 上传 → B 删除 → 404 (防越权)."""
        png_bytes = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63600000000200015f6e40b40000000049454e44ae426082")
        boundary = "----p0test" + uuid.uuid4().hex
        body = (f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"file\"; filename=\"z.png\"\r\n"
                f"Content-Type: image/png\r\n\r\n").encode() + png_bytes + (f"\r\n--{boundary}--\r\n").encode()
        req = urllib.request.Request(BACKEND + "/api/uploads", data=body,
                                     headers=_auth_headers(self.user_a["token"]) | {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        # B 想删 A 的文件 → 404
        req2 = urllib.request.Request(BACKEND + "/api/uploads/" + data["id"], method="DELETE",
                                      headers=_auth_headers(self.user_b["token"]))
        try:
            urllib.request.urlopen(req2, timeout=10)
            self.fail("B 删除 A 的文件应该 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)
        # A 自己删 (cleanup)
        req3 = urllib.request.Request(BACKEND + "/api/uploads/" + data["id"], method="DELETE",
                                      headers=_auth_headers(self.user_a["token"]))
        urllib.request.urlopen(req3, timeout=10).read()

    def test_delete_anonymous_401(self):
        """匿名 DELETE → 401."""
        req = urllib.request.Request(BACKEND + "/api/uploads/nonexistent", method="DELETE",
                                     headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(cm.exception.code, 401)


class P0Pbkdf2UpgradeTests(unittest.TestCase):
    """P0-4: PBKDF2 100k → 600k + 老 hash 兼容 + 自动 rehash."""

    @classmethod
    def setUpClass(cls):
        if not _backend_alive():
            raise unittest.SkipTest("backend unreachable")
        if not os.path.exists(DB_PATH):
            raise unittest.SkipTest(f"db not found at {DB_PATH}")

    def test_new_register_uses_600k(self):
        """新注册用户的 password_hash 格式是 '600000:<hex>'."""
        email = "p0-pw-new-" + uuid.uuid4().hex[:8] + "@e.com"
        _register(email)
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute("SELECT password_hash FROM users WHERE email=?", (email.lower(),)).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertTrue(row[0].startswith("600000:"), f"新注册应该用 600k iter, got: {row[0][:30]}")

    def test_legacy_hash_login_still_works_and_rehashes(self):
        """老 hash (100k, 无 'iter:' 前缀) 仍能 login, 登录后自动 rehash 到 600k."""
        email = "p0-pw-legacy-" + uuid.uuid4().hex[:8] + "@e.com"
        password = "test12345"
        # 模拟老 hash: 直接用 100k 算并存进 db
        salt = secrets.token_hex(16)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        legacy_hash = h.hex()  # 老格式无 'iter:' 前缀
        conn = sqlite3.connect(DB_PATH)
        try:
            user_id = uuid.uuid4().hex
            now = "2026-01-01T00:00:00Z"
            conn.execute(
                "INSERT INTO users (id, email, password_salt, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, 'user', ?, ?)",
                (user_id, email.lower(), salt, legacy_hash, now, now),
            )
            conn.commit()
        finally:
            conn.close()

        # 老 hash 登录 → 应成功
        result = _login(email, password)
        self.assertIn("token", result)

        # 登录后 db 里的 hash 应已被 rehash 到 600k
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute("SELECT password_hash FROM users WHERE email=?", (email.lower(),)).fetchone()
        finally:
            conn.close()
        self.assertTrue(row[0].startswith("600000:"), f"rehash 后应 600k, got: {row[0][:30]}")
        # 第二次登录 (用 rehash 后) 应仍成功
        result2 = _login(email, password)
        self.assertIn("token", result2)

    def test_wrong_password_401(self):
        """错密码 → 401."""
        email = "p0-pw-wrong-" + uuid.uuid4().hex[:8] + "@e.com"
        _register(email, "right-password-12345")
        body = json.dumps({"email": email, "password": "wrong-password"}).encode()
        req = urllib.request.Request(BACKEND + "/auth/login", data=body,
                                     headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(cm.exception.code, 401)


class P0OutputsMountTests(unittest.TestCase):
    """P0-2: /outputs StaticFiles mount 保留 (autoedit 兼容).

    安全靠 run_id UUID 128-bit 不可枚举 (类似 S3 pre-signed URL).
    直接 GET /outputs/<random-uuid> 应该 404 (not found) 而非 401/403 — 路径能访问.
    """

    def test_outputs_path_reachable(self):
        """/outputs/<random> 路径能访问 (404 表示 mount 工作, 非路由死链)."""
        fake = uuid.uuid4().hex + ".mp4"
        req = urllib.request.Request(BACKEND + "/outputs/" + fake)
        try:
            urllib.request.urlopen(req, timeout=5)
            # 不期望 200 (file 不存在), 但路径可访问
        except urllib.error.HTTPError as e:
            # 404 = StaticFiles 返回 not found, mount 工作正常
            self.assertEqual(e.code, 404)


if __name__ == "__main__":
    unittest.main()
