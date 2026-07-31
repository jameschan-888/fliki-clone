import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from providers.base import ProviderError
from providers.music.minimax_music import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    MAX_AUDIO_BYTES,
    MiniMaxMusicError,
    MiniMaxMusicProvider,
)


class _FakeResponse:
    def __init__(self, status_code=200, json_payload=None, text=""):
        self.status_code = status_code
        self.text = text
        self._json = json_payload or {}
        self.headers = {"content-type": "application/json"}

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


def _fake_ok_audio(num_bytes=2048):
    payload = b"\x42" * num_bytes
    return _FakeResponse(json_payload={
        "data": {"audio": payload.hex()},
        "extra_info": {"audio_length": 30000},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    })


class MiniMaxMusicProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "out.mp3"
        os.environ["MINIMAX_API_KEY"] = "test-key-music"

    def tearDown(self):
        os.environ.pop("MINIMAX_API_KEY", None)
        self.tmp.cleanup()

    def test_missing_api_key_raises(self):
        os.environ.pop("MINIMAX_API_KEY", None)
        with self.assertRaises(ProviderError):
            MiniMaxMusicProvider()

    def test_fetch_writes_mp3_on_success(self):
        provider = MiniMaxMusicProvider()
        fake_post = MagicMock(return_value=_fake_ok_audio(4096))
        with patch("providers.music.minimax_music.httpx.post", fake_post):
            result = provider.fetch("独立民谣,忧郁", self.dest)
        self.assertEqual(result["provider"], "minimax_music")
        self.assertEqual(result["prompt"], "独立民谣,忧郁")
        self.assertEqual(result["bytes"], 4096)
        self.assertEqual(result["audio_length_ms"], 30000)
        self.assertTrue(self.dest.exists())
        self.assertEqual(self.dest.stat().st_size, 4096)
        # 验证 payload
        kwargs = fake_post.call_args.kwargs
        body = kwargs["json"]
        self.assertEqual(body["model"], DEFAULT_MODEL)
        self.assertEqual(body["prompt"], "独立民谣,忧郁")
        self.assertNotIn("lyrics", body)
        self.assertEqual(body["audio_setting"]["format"], "mp3")
        self.assertEqual(body["audio_setting"]["sample_rate"], 44100)
        # 验证 Authorization
        self.assertIn("Bearer test-key-music", kwargs["headers"]["Authorization"])
        # 验证 URL
        called_url = fake_post.call_args.args[0]
        self.assertTrue(called_url.endswith("/v1/music_generation"))

    def test_fetch_with_lyrics_includes_lyrics(self):
        provider = MiniMaxMusicProvider()
        fake_post = MagicMock(return_value=_fake_ok_audio(2048))
        lyrics = "[verse]\n路灯微亮晚风轻抚\n影子拉长独自漫步\n[chorus]\n推开木门香气弥漫"
        with patch("providers.music.minimax_music.httpx.post", fake_post):
            r = provider.fetch("独立民谣", self.dest, lyrics=lyrics)
        body = fake_post.call_args.kwargs["json"]
        self.assertEqual(body["lyrics"], lyrics)
        self.assertEqual(r["lyrics"], lyrics)

    def test_fetch_with_duration(self):
        provider = MiniMaxMusicProvider()
        fake_post = MagicMock(return_value=_fake_ok_audio())
        with patch("providers.music.minimax_music.httpx.post", fake_post):
            provider.fetch("epic orchestral", self.dest, duration_seconds=30)
        body = fake_post.call_args.kwargs["json"]
        self.assertEqual(body["duration"], 30)

    def test_fetch_empty_query_raises(self):
        provider = MiniMaxMusicProvider()
        with self.assertRaises(ProviderError):
            provider.fetch("   ", self.dest)

    def test_fetch_401_raises(self):
        provider = MiniMaxMusicProvider()
        fake_post = MagicMock(return_value=_FakeResponse(status_code=401, text="invalid"))
        with patch("providers.music.minimax_music.httpx.post", fake_post):
            with self.assertRaises(MiniMaxMusicError) as ctx:
                provider.fetch("pop", self.dest)
        self.assertIn("auth failed", str(ctx.exception).lower())

    def test_fetch_network_error_raises(self):
        import httpx as _hx
        provider = MiniMaxMusicProvider()
        fake_post = MagicMock(side_effect=_hx.ConnectError("boom"))
        with patch("providers.music.minimax_music.httpx.post", fake_post):
            with self.assertRaises(MiniMaxMusicError):
                provider.fetch("rock", self.dest)

    def test_fetch_bad_hex_raises(self):
        provider = MiniMaxMusicProvider()
        bad = _FakeResponse(json_payload={
            "data": {"audio": "NOTHEX!!!"},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        fake_post = MagicMock(return_value=bad)
        with patch("providers.music.minimax_music.httpx.post", fake_post):
            with self.assertRaises(MiniMaxMusicError) as ctx:
                provider.fetch("pop", self.dest)
        self.assertIn("hex", str(ctx.exception).lower())

    def test_fetch_audio_url_fallback(self):
        provider = MiniMaxMusicProvider()
        # 第一次: music_generation 返回 audio_url (无 hex)
        first = _FakeResponse(json_payload={
            "data": {"audio_url": "https://example.com/music.mp3"},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        # 第二次: URL 下载返回 mp3 bytes
        class _StreamResponse:
            def __init__(self, content):
                self.content = content
                self.status_code = 200
            def raise_for_status(self): pass
            def json(self): return {}
        second = MagicMock(return_value=_StreamResponse(b"\x42" * 1024))
        with patch("providers.music.minimax_music.httpx.post", MagicMock(return_value=first)):
            with patch("providers.music.minimax_music.httpx.get", second):
                result = provider.fetch("jazz", self.dest)
        self.assertEqual(result["bytes"], 1024)
        self.assertTrue(self.dest.exists())

    def test_fetch_base_resp_nonzero_raises(self):
        provider = MiniMaxMusicProvider()
        bad = _FakeResponse(json_payload={
            "data": {},
            "base_resp": {"status_code": 1004, "status_msg": "insufficient balance"},
        })
        fake_post = MagicMock(return_value=bad)
        with patch("providers.music.minimax_music.httpx.post", fake_post):
            with self.assertRaises(MiniMaxMusicError) as ctx:
                provider.fetch("pop", self.dest)
        self.assertIn("insufficient balance", str(ctx.exception))

    def test_healthcheck_ok(self):
        provider = MiniMaxMusicProvider()
        fake_post = MagicMock(return_value=_fake_ok_audio(512))
        with patch("providers.music.minimax_music.httpx.post", fake_post):
            r = provider.healthcheck()
        self.assertTrue(r["ok"])
        self.assertEqual(r["http_status"], 200)
        self.assertEqual(r["model"], DEFAULT_MODEL)
        self.assertIn("minimaxi.com", r["base_url"])

    def test_healthcheck_401(self):
        provider = MiniMaxMusicProvider()
        fake_post = MagicMock(return_value=_FakeResponse(status_code=401))
        with patch("providers.music.minimax_music.httpx.post", fake_post):
            r = provider.healthcheck()
        self.assertFalse(r["ok"])
        self.assertEqual(r["http_status"], 401)
        self.assertIn("invalid", r["error"])
