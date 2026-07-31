import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from providers.base import ProviderError
from providers.tts.minimax_tts import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    MAX_AUDIO_BYTES,
    MiniMaxTTSError,
    MiniMaxTTSProvider,
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


def _fake_ok_audio(num_bytes=512):
    payload = b"\x42" * num_bytes
    return _FakeResponse(
        status_code=200,
        json_payload={
            "data": {"audio": payload.hex(), "status": 2},
            "extra_info": {"audio_length": 1000, "audio_sample_rate": 32000},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        },
    )


class MiniMaxTTSProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "out.mp3"
        self.ref_audio = Path(self.tmp.name) / "ref.mp3"
        self.ref_audio.write_bytes(b"RIFF" + b"\x00" * 200)
        # 强制注入 API key (测试环境)
        os.environ["MINIMAX_API_KEY"] = "test-key-do-not-use-real"

    def tearDown(self):
        os.environ.pop("MINIMAX_API_KEY", None)
        self.tmp.cleanup()

    def test_missing_api_key_raises(self):
        os.environ.pop("MINIMAX_API_KEY", None)
        with self.assertRaises(ProviderError):
            MiniMaxTTSProvider()

    def test_synthesize_writes_mp3_on_success(self):
        provider = MiniMaxTTSProvider()
        fake_post = MagicMock(return_value=_fake_ok_audio())
        with patch("providers.tts.minimax_tts.httpx.post", fake_post):
            result = provider.synthesize("你好世界", self.dest, voice="male-qn-qingse")
        self.assertEqual(result["provider"], "minimax")
        self.assertEqual(result["voice"], "male-qn-qingse")
        self.assertEqual(result["language"], "zh")
        self.assertEqual(result["bytes"], 512)
        self.assertTrue(self.dest.exists())
        self.assertEqual(self.dest.stat().st_size, 512)
        # 确认 Authorization header 注入正确
        kwargs = fake_post.call_args.kwargs
        self.assertIn("Bearer test-key-do-not-use-real", kwargs["headers"]["Authorization"])
        # 确认 payload
        body = kwargs["json"]
        self.assertEqual(body["model"], DEFAULT_MODEL)
        self.assertEqual(body["voice_setting"]["voice_id"], "male-qn-qingse")
        self.assertEqual(body["text"], "你好世界")
        self.assertFalse(body["stream"])

    def test_synthesize_401_raises_minimax_error(self):
        provider = MiniMaxTTSProvider()
        fake_post = MagicMock(return_value=_FakeResponse(status_code=401, text="invalid api key"))
        with patch("providers.tts.minimax_tts.httpx.post", fake_post):
            with self.assertRaises(MiniMaxTTSError) as ctx:
                provider.synthesize("hi", self.dest)
        self.assertIn("auth failed", str(ctx.exception).lower())

    def test_synthesize_network_error_raises(self):
        import httpx as _hx
        provider = MiniMaxTTSProvider()
        fake_post = MagicMock(side_effect=_hx.ConnectError("Connection refused"))
        with patch("providers.tts.minimax_tts.httpx.post", fake_post):
            with self.assertRaises(MiniMaxTTSError) as ctx:
                provider.synthesize("hi", self.dest)
        self.assertIn("http call failed", str(ctx.exception).lower())

    def test_synthesize_bad_hex_raises(self):
        provider = MiniMaxTTSProvider()
        bad = _FakeResponse(json_payload={
            "data": {"audio": "ZZZZNOTHEX", "status": 2},
            "extra_info": {},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        fake_post = MagicMock(return_value=bad)
        with patch("providers.tts.minimax_tts.httpx.post", fake_post):
            with self.assertRaises(MiniMaxTTSError) as ctx:
                provider.synthesize("hi", self.dest)
        self.assertIn("hex", str(ctx.exception).lower())

    def test_synthesize_base_resp_nonzero_raises(self):
        provider = MiniMaxTTSProvider()
        bad = _FakeResponse(json_payload={
            "data": {"audio": "", "status": 1},
            "base_resp": {"status_code": 1004, "status_msg": "voice not found"},
        })
        fake_post = MagicMock(return_value=bad)
        with patch("providers.tts.minimax_tts.httpx.post", fake_post):
            with self.assertRaises(MiniMaxTTSError) as ctx:
                provider.synthesize("hi", self.dest, voice="nope")
        self.assertIn("voice not found", str(ctx.exception))

    def test_synthesize_empty_text_raises(self):
        provider = MiniMaxTTSProvider()
        with self.assertRaises(ProviderError):
            provider.synthesize("   ", self.dest)

    def test_synthesize_with_refs_uploads_then_t2a(self):
        provider = MiniMaxTTSProvider()
        # 第1次: file upload 返回 file_id; 第2次: voice_clone 返回 success; 第3次: t2a_v2 返回 audio
        upload_resp = _FakeResponse(json_payload={"file": {"file_id": 99999}})
        clone_resp = _FakeResponse(json_payload={"base_resp": {"status_code": 0, "status_msg": "success"}})
        t2a_resp = _fake_ok_audio(256)
        fake_post = MagicMock(side_effect=[upload_resp, clone_resp, t2a_resp])
        with patch("providers.tts.minimax_tts.httpx.post", fake_post):
            result = provider.synthesize_with_refs(
                "克隆声音", self.dest,
                ref_audio_path=str(self.ref_audio), ref_text="参考文字", language="zh",
            )
        self.assertEqual(result["provider"], "minimax")
        self.assertTrue(result["voice"].startswith("clone:fliki_"))
        self.assertTrue(self.dest.exists())
        self.assertEqual(self.dest.stat().st_size, 256)
        # 确认调用了 3 次 (upload + clone + t2a)
        self.assertEqual(fake_post.call_count, 3)
        # 第二次调用 (voice_clone) 的 url 应是 /v1/voice_clone
        clone_url = fake_post.call_args_list[1].args[0]
        self.assertTrue(clone_url.endswith("/v1/voice_clone"))

    def test_synthesize_with_refs_uses_cached_voice_id(self):
        provider = MiniMaxTTSProvider()
        upload_resp = _FakeResponse(json_payload={"file": {"file_id": 111}})
        clone_resp = _FakeResponse(json_payload={"base_resp": {"status_code": 0, "status_msg": "success"}})
        t2a_resp = _fake_ok_audio(128)
        fake_post = MagicMock(side_effect=[upload_resp, clone_resp, t2a_resp, t2a_resp])
        with patch("providers.tts.minimax_tts.httpx.post", fake_post):
            # 第一次: 3 次调用 (upload + clone + t2a)
            provider.synthesize_with_refs("first", self.dest, ref_audio_path=str(self.ref_audio), ref_text="ref")
            # 第二次: 只 1 次调用 (t2a, 缓存命中)
            provider.synthesize_with_refs("second", self.dest, ref_audio_path=str(self.ref_audio), ref_text="ref")
        self.assertEqual(fake_post.call_count, 4)  # 3 + 1

    def test_healthcheck_ok(self):
        provider = MiniMaxTTSProvider()
        fake_post = MagicMock(return_value=_fake_ok_audio(64))
        with patch("providers.tts.minimax_tts.httpx.post", fake_post):
            r = provider.healthcheck()
        self.assertTrue(r["ok"])
        self.assertEqual(r["http_status"], 200)
        self.assertIn("base_url", r)
        self.assertGreaterEqual(r["latency_ms"], 0)

    def test_healthcheck_401(self):
        provider = MiniMaxTTSProvider()
        fake_post = MagicMock(return_value=_FakeResponse(status_code=401))
        with patch("providers.tts.minimax_tts.httpx.post", fake_post):
            r = provider.healthcheck()
        self.assertFalse(r["ok"])
        self.assertEqual(r["http_status"], 401)
        self.assertIn("invalid", r["error"])

    def test_healthcheck_network_error(self):
        import httpx as _hx
        provider = MiniMaxTTSProvider()
        fake_post = MagicMock(side_effect=_hx.ConnectError("boom"))
        with patch("providers.tts.minimax_tts.httpx.post", fake_post):
            r = provider.healthcheck()
        self.assertFalse(r["ok"])
        self.assertIn("boom", r["error"])
