import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from providers.base import ProviderError
from providers.tts.gpt_sovits import (
    DEFAULT_BASE_URL,
    GPTSoVITSError,
    GPTSoVITSProvider,
    MAX_AUDIO_BYTES,
)


class _FakeResponse:
    def __init__(self, content=b"", status_code=200, content_type="audio/wav", text="", json_payload=None):
        self.text = text
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._text = text or ""
        self._json = json_payload

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


class GPTSoVITSProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ref_audio = Path(self.tmp.name) / "ref.wav"
        self.ref_audio.write_bytes(b"RIFF" + b"\x00" * 100)
        self.dest = Path(self.tmp.name) / "out.wav"

    def tearDown(self):
        self.tmp.cleanup()

    def test_synthesize_requires_refs(self):
        p = GPTSoVITSProvider()
        with self.assertRaises(ProviderError):
            p.synthesize("hello", self.dest)

    def test_synthesize_with_refs_writes_wav_when_endpoint_returns_bytes(self):
        provider = GPTSoVITSProvider(base_url="http://test:9880")
        wav_bytes = b"WAVE" + b"\x10" * 200
        fake_post = MagicMock(return_value=_FakeResponse(content=wav_bytes, content_type="audio/wav"))
        with patch("providers.tts.gpt_sovits.httpx.post", fake_post):
            result = provider.synthesize_with_refs(
                "你好世界", self.dest,
                ref_audio_path=str(self.ref_audio), ref_text="参考", language="zh",
            )
        self.assertEqual(result["provider"], "gpt_sovits")
        self.assertEqual(result["language"], "zh")
        self.assertEqual(result["bytes"], len(wav_bytes))
        self.assertTrue(self.dest.exists())
        self.assertEqual(self.dest.read_bytes(), wav_bytes)
        fake_post.assert_called_once()
        request = fake_post.call_args
        self.assertEqual(request.args[0], "http://test:9880/tts")
        kwargs = request.kwargs
        self.assertEqual(kwargs["json"]["text"], "你好世界")
        self.assertEqual(kwargs["json"]["text_lang"], "zh")
        self.assertEqual(kwargs["json"]["ref_audio_path"], str(self.ref_audio))
        self.assertNotIn("refer_wav_path", kwargs["json"])
        self.assertEqual(kwargs["json"]["media_type"], "wav")

    def test_synthesize_with_refs_handles_base64_json_payload(self):
        provider = GPTSoVITSProvider()
        wav_bytes = b"X" * 1500
        b64 = base64.b64encode(wav_bytes).decode("ascii")
        fake_post = MagicMock(return_value=_FakeResponse(content_type="application/json", json_payload={"audio": b64}))
        with patch("providers.tts.gpt_sovits.httpx.post", fake_post):
            result = provider.synthesize_with_refs("hello", self.dest, ref_audio_path=str(self.ref_audio), ref_text="ref")
        self.assertEqual(self.dest.read_bytes(), wav_bytes)
        self.assertEqual(result["bytes"], len(wav_bytes))

    def test_synthesize_with_refs_rejects_missing_ref_audio(self):
        provider = GPTSoVITSProvider()
        with self.assertRaises(ProviderError):
            provider.synthesize_with_refs("hi", self.dest, ref_audio_path=str(Path(self.tmp.name) / "nope.wav"), ref_text="x")

    def test_synthesize_with_refs_rejects_oversized_response(self):
        provider = GPTSoVITSProvider()
        big = b"x" * (MAX_AUDIO_BYTES + 1)
        fake_post = MagicMock(return_value=_FakeResponse(content=big))
        with patch("providers.tts.gpt_sovits.httpx.post", fake_post):
            with self.assertRaises(GPTSoVITSError) as ctx:
                provider.synthesize_with_refs("hi", self.dest, ref_audio_path=str(self.ref_audio), ref_text="ref")
        self.assertIn("too large", str(ctx.exception))

    def test_synthesize_with_refs_surfaces_http_error(self):
        provider = GPTSoVITSProvider()
        fake_post = MagicMock(return_value=_FakeResponse(status_code=503, text="upstream broken", content_type="text/plain"))
        with patch("providers.tts.gpt_sovits.httpx.post", fake_post):
            with self.assertRaises(GPTSoVITSError) as ctx:
                provider.synthesize_with_refs("hi", self.dest, ref_audio_path=str(self.ref_audio), ref_text="ref")
        self.assertIn("503", str(ctx.exception))

    def test_healthcheck_offline(self):
        provider = GPTSoVITSProvider(base_url="http://does-not-exist:9880")
        fake_http_error = __import__("httpx").ConnectError("no route")
        with patch("providers.tts.gpt_sovits.httpx.get", side_effect=fake_http_error):
            info = provider.healthcheck()
        self.assertFalse(info["ok"])
        self.assertIn("base_url", info)
        self.assertEqual(info["base_url"], "http://does-not-exist:9880")
        self.assertIsNotNone(info["error"])

    def test_healthcheck_ok(self):
        provider = GPTSoVITSProvider(base_url="http://test:9880")
        with patch("providers.tts.gpt_sovits.httpx.get", return_value=_FakeResponse(status_code=200, content=b'{"msg":"ok"}')):
            info = provider.healthcheck()
        self.assertTrue(info["ok"])
        self.assertEqual(info["http_status"], 200)

    def test_lang_mapping(self):
        self.assertEqual(GPTSoVITSProvider._lang_to_gpt("zh-CN"), "zh")
        self.assertEqual(GPTSoVITSProvider._lang_to_gpt("en-US"), "en")
        self.assertEqual(GPTSoVITSProvider._lang_to_gpt("ja"), "ja")
        self.assertEqual(GPTSoVITSProvider._lang_to_gpt("xyz"), "zh")

    def test_default_base_url_is_local(self):
        self.assertEqual(DEFAULT_BASE_URL, "http://127.0.0.1:9880")
