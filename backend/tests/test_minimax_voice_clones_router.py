# P7-Persist: minimax voice clones router + 持久化 cache wiring 测试.
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from minimax_voice_clones_router import create_router as create_minimax_router
from providers.base import ProviderError
from providers.tts.minimax_tts import (
    MiniMaxTTSProvider,
    derive_voice_id,
    sha256_of_file,
)


def _setup_db():
    """建一个临时 SQLite, 跑一次 schema.sql, 加 minimax provider config."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    schema = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(schema.read_text(encoding="utf-8"))
    # 种子 minimax provider config (mock 不让它真去 .env)
    conn.execute(
        "INSERT INTO provider_configs (id, category, name, enabled, is_default, priority, config_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "provider_tts_minimax",
            "tts",
            "minimax",
            1,
            1,
            40,
            json.dumps({"model": "speech-02-turbo", "api_key_env": "MINIMAX_API_KEY", "base_url": "https://api.minimaxi.com"}),
            1,
        ),
    )
    conn.commit()
    conn.close()
    return path


def _make_client(db_path: str, ref_dir: str, preview_dir: str):
    def _get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    app = FastAPI()
    app.include_router(create_minimax_router(_get_db, ref_dir, preview_dir))
    return TestClient(app)


def _write_audio(directory: Path, name: str, content: bytes = b"RIFF" + b"\x00" * 200) -> Path:
    p = directory / name
    p.write_bytes(content)
    return p


class MiniMaxVoiceClonesRouterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = _setup_db()
        self.ref_dir = Path(self.tmp.name) / "refs"
        self.preview_dir = Path(self.tmp.name) / "previews"
        self.ref_dir.mkdir(parents=True, exist_ok=True)
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        os.environ["MINIMAX_API_KEY"] = "test-key-do-not-use-real"
        self.client = _make_client(self.db_path, str(self.ref_dir), str(self.preview_dir))

    def tearDown(self):
        os.environ.pop("MINIMAX_API_KEY", None)
        self.tmp.cleanup()
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    # ---- 列表 ----
    def test_list_empty(self):
        r = self.client.get("/minimax-voice-clones")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    # ---- 创建 ----
    def test_create_clone_persists_to_db(self):
        ref = _write_audio(self.ref_dir, "ref.wav", b"RIFF" + b"\x11" * 4096)
        upload_payload = {"ref_audio": ("ref.wav", ref.read_bytes(), "audio/wav")}
        with patch("minimax_voice_clones_router.build_minimax_provider") as build:
            provider = MagicMock()
            provider.clone_voice.return_value = {
                "voice_id": "fliki_ref_aaaaaaaaaaaaaaaa",
                "sha256": sha256_of_file(ref),
                "cached": False,
                "model": "speech-02-turbo",
            }
            build.return_value = provider
            r = self.client.post(
                "/minimax-voice-clones",
                data={"cloned_name": "Alice", "ref_text": "你好", "language": "zh"},
                files=upload_payload,
            )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertFalse(body["duplicate"])
        voice = body["voice"]
        self.assertEqual(voice["voice_id"], "fliki_ref_aaaaaaaaaaaaaaaa")
        self.assertEqual(voice["model"], "speech-02-turbo")
        self.assertEqual(voice["provider"], "minimax")
        self.assertTrue(voice["voice"].startswith("minimax-clone:"))
        # DB 落盘
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM minimax_voice_clones WHERE uuid=?", (voice["uuid"],)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["voice_id"], "fliki_ref_aaaaaaaaaaaaaaaa")
        self.assertEqual(row["language"], "zh")

    def test_create_clone_duplicate_by_sha256_returns_existing(self):
        content = b"RIFF" + b"\x22" * 4096
        ref1 = _write_audio(self.ref_dir, "ref1.wav", content)
        ref2 = _write_audio(self.ref_dir, "ref2.wav", content)
        with patch("minimax_voice_clones_router.build_minimax_provider") as build:
            provider = MagicMock()
            provider.clone_voice.return_value = {
                "voice_id": "fliki_ref_bbbbbbbbbbbbbbbb",
                "sha256": sha256_of_file(ref1),
                "cached": False,
                "model": "speech-02-turbo",
            }
            build.return_value = provider
            r1 = self.client.post(
                "/minimax-voice-clones",
                data={"cloned_name": "first"},
                files={"ref_audio": ("ref1.wav", ref1.read_bytes(), "audio/wav")},
            )
            self.assertEqual(r1.status_code, 200, r1.text)
            # 第二次同 sha256 (但文件名不同) → 不会真调 clone
            provider.clone_voice.reset_mock()
            r2 = self.client.post(
                "/minimax-voice-clones",
                data={"cloned_name": "second"},
                files={"ref_audio": ("ref2.wav", ref2.read_bytes(), "audio/wav")},
            )
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertTrue(r2.json()["duplicate"])
        # 关键: 第二次没真正调用 MiniMax clone
        provider.clone_voice.assert_not_called()
        # DB 只有 1 行
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        n = conn.execute("SELECT COUNT(*) FROM minimax_voice_clones").fetchone()[0]
        conn.close()
        self.assertEqual(n, 1)

    def test_create_clone_unsupported_ext_422(self):
        ref = _write_audio(self.ref_dir, "ref.txt", b"hello")
        r = self.client.post(
            "/minimax-voice-clones",
            data={"cloned_name": "x"},
            files={"ref_audio": ("ref.txt", ref.read_bytes(), "text/plain")},
        )
        self.assertEqual(r.status_code, 422)

    def test_create_clone_too_small_422(self):
        ref = _write_audio(self.ref_dir, "ref.wav", b"RIFF")
        r = self.client.post(
            "/minimax-voice-clones",
            data={"cloned_name": "x"},
            files={"ref_audio": ("ref.wav", ref.read_bytes(), "audio/wav")},
        )
        self.assertEqual(r.status_code, 422)

    def test_create_clone_provider_error_502(self):
        ref = _write_audio(self.ref_dir, "ref.wav", b"RIFF" + b"\x33" * 4096)
        with patch("minimax_voice_clones_router.build_minimax_provider") as build:
            provider = MagicMock()
            provider.clone_voice.side_effect = ProviderError("MiniMax clone failed: 401")
            build.return_value = provider
            r = self.client.post(
                "/minimax-voice-clones",
                data={"cloned_name": "x"},
                files={"ref_audio": ("ref.wav", ref.read_bytes(), "audio/wav")},
            )
        self.assertEqual(r.status_code, 502, r.text)
        self.assertIn("MiniMax clone failed", r.text)

    # ---- 获取 / 删除 ----
    def test_get_clone_404(self):
        r = self.client.get("/minimax-voice-clones/nonexistent")
        self.assertEqual(r.status_code, 404)

    def test_delete_clone_removes_row_and_file(self):
        ref = _write_audio(self.ref_dir, "ref.wav", b"RIFF" + b"\x44" * 4096)
        with patch("minimax_voice_clones_router.build_minimax_provider") as build:
            provider = MagicMock()
            provider.clone_voice.return_value = {
                "voice_id": "fliki_ref_cccccccccccccccc",
                "sha256": sha256_of_file(ref),
                "cached": False,
                "model": "speech-02-turbo",
            }
            build.return_value = provider
            r = self.client.post(
                "/minimax-voice-clones",
                data={"cloned_name": "Bob"},
                files={"ref_audio": ("ref.wav", ref.read_bytes(), "audio/wav")},
            )
            uuid = r.json()["voice"]["uuid"]
        d = self.client.delete(f"/minimax-voice-clones/{uuid}")
        self.assertEqual(d.status_code, 200)
        g = self.client.get(f"/minimax-voice-clones/{uuid}")
        self.assertEqual(g.status_code, 404)

    # ---- 试听 ----
    def test_preview_uses_cached_voice_id_no_upload(self):
        ref = _write_audio(self.ref_dir, "ref.wav", b"RIFF" + b"\x55" * 4096)
        sha = sha256_of_file(ref)
        voice_id = "fliki_ref_dddddddddddddddd"
        with patch("minimax_voice_clones_router.build_minimax_provider") as build:
            provider = MagicMock()
            provider.clone_voice.return_value = {
                "voice_id": voice_id,
                "sha256": sha,
                "cached": False,
                "model": "speech-02-turbo",
            }
            provider.synthesize_with_voice_id.return_value = {
                "provider": "minimax",
                "voice": voice_id,
                "language": "zh",
                "local_path": str(self.preview_dir / "preview.mp3"),
                "bytes": 1024,
            }
            build.return_value = provider
            r = self.client.post(
                "/minimax-voice-clones",
                data={"cloned_name": "Preview", "sample_text": "试听样本"},
                files={"ref_audio": ("ref.wav", ref.read_bytes(), "audio/wav")},
            )
            uuid = r.json()["voice"]["uuid"]
            # 关键: 试听不应再触发 clone_voice (只走 synthesize_with_voice_id)
            provider.clone_voice.reset_mock()
            p = self.client.post(f"/minimax-voice-clones/{uuid}/preview")
        self.assertEqual(p.status_code, 200, p.text)
        self.assertEqual(p.json()["bytes"], 1024)
        provider.clone_voice.assert_not_called()
        provider.synthesize_with_voice_id.assert_called_once()


class MiniMaxTTSCacheWiringTest(unittest.TestCase):
    """验证 provider.load_cache / cache_snapshot + sha256 派生."""

    def setUp(self):
        os.environ["MINIMAX_API_KEY"] = "test-key-do-not-use-real"
        self.tmp = tempfile.TemporaryDirectory()
        self.ref = Path(self.tmp.name) / "ref.wav"
        self.ref.write_bytes(b"RIFF" + b"\x00" * 1024)

    def tearDown(self):
        os.environ.pop("MINIMAX_API_KEY", None)
        self.tmp.cleanup()

    def test_load_cache_seeds_voice_id(self):
        provider = MiniMaxTTSProvider()
        sha = sha256_of_file(self.ref)
        derived = derive_voice_id(sha, self.ref)
        # 预填后, clone_voice 不调 upload/clone API
        provider.load_cache({sha: derived})
        with patch("providers.tts.minimax_tts.httpx.post") as fake_post:
            result = provider.clone_voice(ref_audio_path=str(self.ref), ref_text="x")
        self.assertTrue(result["cached"])
        self.assertEqual(result["voice_id"], derived)
        fake_post.assert_not_called()

    def test_cache_snapshot_round_trip(self):
        provider = MiniMaxTTSProvider()
        sha = sha256_of_file(self.ref)
        provider.load_cache({sha: "fliki_ref_xyz"})
        snap = provider.cache_snapshot()
        self.assertEqual(snap[sha], "fliki_ref_xyz")
        # 注入到新 provider → 命中
        provider2 = MiniMaxTTSProvider()
        provider2.load_cache(snap)
        with patch("providers.tts.minimax_tts.httpx.post") as fake_post:
            result = provider2.clone_voice(ref_audio_path=str(self.ref))
        self.assertTrue(result["cached"])
        self.assertEqual(result["voice_id"], "fliki_ref_xyz")
        fake_post.assert_not_called()

    def test_derive_voice_id_is_deterministic_by_sha256(self):
        """同一 sha256 内容 → 跨 path 也得到同一 voice_id (关键持久化保证)."""
        sha = sha256_of_file(self.ref)
        v1 = derive_voice_id(sha, self.ref)
        fake_path = Path("/tmp/no-such-file.mp3")
        v2 = derive_voice_id(sha, fake_path)
        # sha 一样, voice_id 一样 (虽然路径不同)
        self.assertEqual(v1, v2)
        self.assertTrue(v1.startswith("fliki_"))

    def test_derive_voice_id_changes_when_sha_changes(self):
        v1 = derive_voice_id("a" * 64, self.ref)
        v2 = derive_voice_id("b" * 64, self.ref)
        self.assertNotEqual(v1, v2)


if __name__ == "__main__":
    unittest.main()
