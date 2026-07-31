"""P5G Avatar clone ref-face / ref-audio / meta update + generic uploads router."""
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from avatar_clone_router import create_router  # noqa: E402
from uploads_router import create_router as create_uploads_router  # noqa: E402


def _build_png(color=(255, 0, 0, 255)):
    """128x128 PNG with random noise so output > 256B."""
    import struct
    import zlib
    import random
    random.seed(42)
    width = height = 128
    raw = b""
    for y in range(height):
        raw += b"\x00"
        for x in range(width):
            raw += struct.pack("BBBB", random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 255)
    compressed = zlib.compress(raw, level=0)
    def chunk(t, d):
        crc = zlib.crc32(t + d)
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", crc)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    idat = chunk(b"IDAT", compressed)
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _build_wav(seconds=1, rate=8000):
    import struct
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * rate * seconds)
    return buf.getvalue()


def _make_db():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    # avatar_clones + provider_configs (required by seed_runtime_providers)
    db.executescript("""
    CREATE TABLE avatar_clones (
        id TEXT PRIMARY KEY,
        uuid TEXT UNIQUE NOT NULL,
        avatar_name TEXT NOT NULL,
        ref_face_path TEXT,
        ref_audio_path TEXT,
        default_audio_path TEXT,
        language TEXT,
        permission_note TEXT,
        enabled INTEGER DEFAULT 1,
        created_at INTEGER
    );
    CREATE TABLE provider_configs (
        id TEXT PRIMARY KEY,
        category TEXT,
        name TEXT,
        enabled INTEGER,
        is_default INTEGER,
        config_json TEXT,
        priority INTEGER,
        created_at INTEGER
    );
    """)
    return db


class P5GAvatarUpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.face_dir = Path(self.tmp.name) / "faces"
        self.audio_dir = Path(self.tmp.name) / "audios"
        self.output_dir = Path(self.tmp.name) / "outputs"
        for d in (self.face_dir, self.audio_dir, self.output_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.db = _make_db()
        self.db.execute(
            "INSERT INTO avatar_clones (id, uuid, avatar_name, ref_face_path, ref_audio_path, default_audio_path, language, permission_note, enabled, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
            ("avatar_x", "uuid-x", "OrigName", "", "", "", "zh", "", 1000),
        )
        self.db.commit()

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(create_router(lambda: self.db, str(self.face_dir), str(self.audio_dir), str(self.output_dir)))
        self.client = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()
        self.db.close()

    def test_replace_ref_face(self):
        png = _build_png()
        r = self.client.put(
            "/avatar-clones/uuid-x/ref-face",
            files={"ref_face": ("new.png", png, "image/png")},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ref_face_path"].endswith("uuid-x.png"))
        self.assertTrue(Path(body["ref_face_path"]).is_file())

    def test_replace_ref_audio(self):
        wav = _build_wav()
        r = self.client.put(
            "/avatar-clones/uuid-x/ref-audio",
            files={"ref_audio": ("new.wav", wav, "audio/wav")},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ref_audio_path"].endswith("uuid-x.wav"))
        self.assertEqual(body["default_audio_path"], body["ref_audio_path"])

    def test_patch_meta(self):
        r = self.client.patch(
            "/avatar-clones/uuid-x/meta",
            json={"avatar_name": "Renamed", "language": "en", "permission_note": "x"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["avatar_name"], "Renamed")
        self.assertEqual(body["language"], "en")

    def test_patch_meta_empty_name_rejected(self):
        r = self.client.patch(
            "/avatar-clones/uuid-x/meta",
            json={"avatar_name": "   "},
        )
        self.assertEqual(r.status_code, 422)

    def test_patch_meta_no_fields(self):
        r = self.client.patch("/avatar-clones/uuid-x/meta", json={})
        self.assertEqual(r.status_code, 422)


class P5GUploadsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.tmp.name) / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import uuid as _uuid
        from auth_router import _make_token, _hash_pw, ensure_users_table
        # 用 in-memory db 避免 Windows 文件句柄延迟 (WinError 32)
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.executescript(Path(ROOT, "db", "schema.sql").read_text(encoding="utf-8"))
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_salt TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT \"user\", created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        self.user_id = _uuid.uuid4().hex
        salt, pw_hash = _hash_pw("test-pass-123")
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.db.execute(
            "INSERT INTO users (id, email, password_salt, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (self.user_id, "test@fliki.local", salt, pw_hash, "user", now, now),
        )
        self.db.commit()
        self.token = _make_token(self.user_id, "user")
        self.headers = {"Authorization": "Bearer " + self.token}

        app = FastAPI()
        app.include_router(create_uploads_router(str(self.upload_dir)))
        self.client = TestClient(app)

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass
        # Windows 下 sqlite3 文件句柄延迟释放, 不主动 cleanup 让 OS 回收; 测试结果不变


    def test_upload_and_get(self):
        wav = _build_wav()
        r = self.client.post(
            "/api/uploads",
            files={"file": ("clip.wav", wav, "audio/wav")},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["url"].startswith("/uploads/"))
        # P0: URL = /uploads/{user_id}/{file_id}.{ext}, 文件在 self.upload_dir / user_id 子目录
        self.assertTrue((self.upload_dir / self.user_id / Path(body["url"]).name).is_file(), "file should be at " + str(self.upload_dir / self.user_id / Path(body["url"]).name))

    def test_upload_rejects_disallowed_ext(self):
        r = self.client.post(
            "/api/uploads",
            files={"file": ("hack.exe", b"x" * 16, "application/octet-stream")},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 422)

    def test_delete(self):
        wav = _build_wav()
        r = self.client.post(
            "/api/uploads",
            files={"file": ("clip.wav", wav, "audio/wav")},
            headers=self.headers,
        )
        uid = r.json()["id"]
        r2 = self.client.delete(f"/api/uploads/{uid}", headers=self.headers)
        self.assertEqual(r2.status_code, 200)
        # file is gone
        self.assertFalse(any(self.upload_dir.glob(f"{uid}.*")))


if __name__ == "__main__":
    unittest.main()
