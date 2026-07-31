import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from providers.base import ProviderError
from providers.stock.minimax_image import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    MAX_IMAGE_BYTES,
    MiniMaxImageError,
    MiniMaxImageProvider,
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


def _fake_ok_url_response(num_bytes=2048, n=1):
    urls = [f"https://example.com/img{i}.jpg" for i in range(n)]
    return _FakeResponse(json_payload={
        "data": {"image_urls": urls},
        "metadata": {"n": n},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    })


class _FakeStreamResponse:
    def __init__(self, content):
        self.content = content
        self.status_code = 200
    def raise_for_status(self): pass
    def json(self): return {}


class MiniMaxImageProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "out.jpg"
        os.environ["MINIMAX_API_KEY"] = "test-key-image"

    def tearDown(self):
        os.environ.pop("MINIMAX_API_KEY", None)
        self.tmp.cleanup()

    def test_missing_api_key_raises(self):
        os.environ.pop("MINIMAX_API_KEY", None)
        with self.assertRaises(ProviderError):
            MiniMaxImageProvider()

    def test_fetch_downloads_from_first_url(self):
        provider = MiniMaxImageProvider()
        gen_resp = _fake_ok_url_response(n=3)
        fake_post = MagicMock(return_value=gen_resp)
        img_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 4096
        fake_get = MagicMock(return_value=_FakeStreamResponse(img_bytes))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            with patch("providers.stock.minimax_image.httpx.get", fake_get):
                result = provider.fetch("city skyline at sunset", self.dest)
        self.assertEqual(result["provider"], "minimax_image")
        self.assertEqual(result["bytes"], len(img_bytes))
        self.assertEqual(result["source_url"], "https://example.com/img0.jpg")
        self.assertTrue(self.dest.exists())
        self.assertEqual(self.dest.stat().st_size, len(img_bytes))
        # 验证 payload
        body = fake_post.call_args.kwargs["json"]
        self.assertEqual(body["model"], DEFAULT_MODEL)
        self.assertEqual(body["prompt"], "city skyline at sunset")
        self.assertEqual(body["aspect_ratio"], "16:9")
        self.assertEqual(body["n"], 1)  # 限定在 1-4
        self.assertTrue(body["prompt_optimizer"])
        # 验证 URL
        url = fake_post.call_args.args[0]
        self.assertTrue(url.endswith("/v1/image_generation"))

    def test_fetch_with_aspect_ratio(self):
        provider = MiniMaxImageProvider()
        fake_post = MagicMock(return_value=_fake_ok_url_response())
        fake_get = MagicMock(return_value=_FakeStreamResponse(b"\x42" * 100))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            with patch("providers.stock.minimax_image.httpx.get", fake_get):
                provider.fetch("portrait", self.dest, aspect_ratio="9:16")
        body = fake_post.call_args.kwargs["json"]
        self.assertEqual(body["aspect_ratio"], "9:16")

    def test_fetch_n_clamped(self):
        provider = MiniMaxImageProvider()
        fake_post = MagicMock(return_value=_fake_ok_url_response())
        fake_get = MagicMock(return_value=_FakeStreamResponse(b"\x42" * 100))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            with patch("providers.stock.minimax_image.httpx.get", fake_get):
                provider.fetch("x", self.dest, n=10)  # 超过 4 应 clamp
        body = fake_post.call_args.kwargs["json"]
        self.assertEqual(body["n"], 4)

    def test_fetch_base64_response(self):
        provider = MiniMaxImageProvider()
        import base64
        raw = b"\xff\xd8\xff" + b"\x00" * 200
        fake_post = MagicMock(return_value=_FakeResponse(json_payload={
            "data": {"image_base64": [base64.b64encode(raw).decode()]},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            result = provider.fetch("anything", self.dest)
        self.assertEqual(result["bytes"], len(raw))
        self.assertIsNone(result["source_url"])
        self.assertTrue(self.dest.exists())

    def test_fetch_empty_prompt_raises(self):
        provider = MiniMaxImageProvider()
        with self.assertRaises(ProviderError):
            provider.fetch("   ", self.dest)

    def test_fetch_401_raises(self):
        provider = MiniMaxImageProvider()
        fake_post = MagicMock(return_value=_FakeResponse(status_code=401, text="invalid"))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            with self.assertRaises(MiniMaxImageError) as ctx:
                provider.fetch("x", self.dest)
        self.assertIn("auth failed", str(ctx.exception).lower())

    def test_fetch_network_error_raises(self):
        import httpx as _hx
        provider = MiniMaxImageProvider()
        fake_post = MagicMock(side_effect=_hx.ConnectError("boom"))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            with self.assertRaises(MiniMaxImageError):
                provider.fetch("x", self.dest)

    def test_fetch_url_download_error_raises(self):
        import httpx as _hx
        provider = MiniMaxImageProvider()
        fake_post = MagicMock(return_value=_fake_ok_url_response())
        fake_get = MagicMock(side_effect=_hx.ConnectError("download fail"))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            with patch("providers.stock.minimax_image.httpx.get", fake_get):
                with self.assertRaises(MiniMaxImageError) as ctx:
                    provider.fetch("x", self.dest)
        self.assertIn("URL fetch failed", str(ctx.exception))

    def test_fetch_no_image_in_response_raises(self):
        provider = MiniMaxImageProvider()
        fake_post = MagicMock(return_value=_FakeResponse(json_payload={
            "data": {},  # 没有 image_urls / image_base64
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            with self.assertRaises(MiniMaxImageError) as ctx:
                provider.fetch("x", self.dest)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_fetch_base_resp_nonzero_raises(self):
        provider = MiniMaxImageProvider()
        fake_post = MagicMock(return_value=_FakeResponse(json_payload={
            "data": {"image_urls": ["https://x"]},
            "base_resp": {"status_code": 1004, "status_msg": "quota exceeded"},
        }))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            with self.assertRaises(MiniMaxImageError) as ctx:
                provider.fetch("x", self.dest)
        self.assertIn("quota exceeded", str(ctx.exception))

    def test_healthcheck_ok(self):
        provider = MiniMaxImageProvider()
        fake_post = MagicMock(return_value=_fake_ok_url_response())
        fake_get = MagicMock(return_value=_FakeStreamResponse(b"\x42" * 100))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            with patch("providers.stock.minimax_image.httpx.get", fake_get):
                r = provider.healthcheck()
        self.assertTrue(r["ok"])
        self.assertEqual(r["http_status"], 200)
        self.assertEqual(r["model"], DEFAULT_MODEL)

    def test_healthcheck_401(self):
        provider = MiniMaxImageProvider()
        fake_post = MagicMock(return_value=_FakeResponse(status_code=401))
        with patch("providers.stock.minimax_image.httpx.post", fake_post):
            r = provider.healthcheck()
        self.assertFalse(r["ok"])
        self.assertEqual(r["http_status"], 401)
