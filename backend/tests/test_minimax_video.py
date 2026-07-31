import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from providers.base import ProviderError
from providers.stock.minimax_video import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    MAX_VIDEO_BYTES,
    MiniMaxVideoError,
    MiniMaxVideoProvider,
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


class _FakeStreamResponse:
    def __init__(self, content):
        self.content = content
        self.status_code = 200
    def raise_for_status(self): pass
    def json(self): return {}


class MiniMaxVideoProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "out.mp4"
        os.environ["MINIMAX_API_KEY"] = "test-key-video"

    def tearDown(self):
        os.environ.pop("MINIMAX_API_KEY", None)
        self.tmp.cleanup()

    def test_missing_api_key_raises(self):
        os.environ.pop("MINIMAX_API_KEY", None)
        with self.assertRaises(ProviderError):
            MiniMaxVideoProvider()

    def test_fetch_empty_prompt_raises(self):
        provider = MiniMaxVideoProvider(max_polls=2)
        with self.assertRaises(ProviderError):
            provider.fetch("   ", self.dest)

    def test_submit_401_raises(self):
        provider = MiniMaxVideoProvider(max_polls=2)
        fake_post = MagicMock(return_value=_FakeResponse(status_code=401, text="invalid"))
        with patch("providers.stock.minimax_video.httpx.post", fake_post):
            with self.assertRaises(MiniMaxVideoError) as ctx:
                provider.fetch("x", self.dest)
        self.assertIn("auth failed", str(ctx.exception).lower())

    def test_submit_network_error_raises(self):
        import httpx as _hx
        provider = MiniMaxVideoProvider(max_polls=2)
        fake_post = MagicMock(side_effect=_hx.ConnectError("boom"))
        with patch("providers.stock.minimax_video.httpx.post", fake_post):
            with self.assertRaises(MiniMaxVideoError):
                provider.fetch("x", self.dest)

    def test_submit_base_resp_nonzero_raises(self):
        provider = MiniMaxVideoProvider(max_polls=2)
        fake_post = MagicMock(return_value=_FakeResponse(json_payload={
            "base_resp": {"status_code": 1004, "status_msg": "no quota"}
        }))
        with patch("providers.stock.minimax_video.httpx.post", fake_post):
            with self.assertRaises(MiniMaxVideoError) as ctx:
                provider.fetch("x", self.dest)
        self.assertIn("no quota", str(ctx.exception))

    def test_submit_missing_task_id_raises(self):
        provider = MiniMaxVideoProvider(max_polls=2)
        fake_post = MagicMock(return_value=_FakeResponse(json_payload={
            "base_resp": {"status_code": 0, "status_msg": "success"}
            # 没有 task_id
        }))
        with patch("providers.stock.minimax_video.httpx.post", fake_post):
            with self.assertRaises(MiniMaxVideoError) as ctx:
                provider.fetch("x", self.dest)
        self.assertIn("task_id", str(ctx.exception).lower())

    def test_full_flow_success_via_url(self):
        provider = MiniMaxVideoProvider(max_polls=5, poll_interval=0)
        submit_resp = _FakeResponse(json_payload={
            "task_id": "task-abc-123",
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        # 第 1 次轮询: processing; 第 2 次: success with video_url
        poll1 = _FakeResponse(json_payload={
            "status": "Processing",
            "base_resp": {"status_code": 0, "status_msg": "in progress"},
        })
        poll2 = _FakeResponse(json_payload={
            "status": "Success",
            "data": {"video_url": "https://example.com/video.mp4"},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        video_bytes = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4096
        dl_resp = _FakeStreamResponse(video_bytes)

        fake_post = MagicMock(side_effect=[submit_resp, poll1, poll2])
        fake_get = MagicMock(return_value=dl_resp)

        with patch("providers.stock.minimax_video.httpx.post", fake_post):
            with patch("providers.stock.minimax_video.httpx.get", fake_get):
                result = provider.fetch("a man picks up a book", self.dest)
        self.assertEqual(result["provider"], "minimax_video")
        self.assertEqual(result["task_id"], "task-abc-123")
        self.assertEqual(result["bytes"], len(video_bytes))
        self.assertEqual(result["poll_attempts"], 2)
        self.assertTrue(self.dest.exists())
        self.assertEqual(self.dest.stat().st_size, len(video_bytes))

        # 验证 submit payload
        submit_body = fake_post.call_args_list[0].kwargs["json"]
        self.assertEqual(submit_body["model"], DEFAULT_MODEL)
        self.assertEqual(submit_body["prompt"], "a man picks up a book")
        self.assertEqual(submit_body["duration"], 6)
        self.assertEqual(submit_body["resolution"], "1080P")

    def test_poll_timeout_raises(self):
        provider = MiniMaxVideoProvider(max_polls=3, poll_interval=0)
        submit_resp = _FakeResponse(json_payload={
            "task_id": "task-pending",
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        poll = _FakeResponse(json_payload={
            "status": "Processing",
            "base_resp": {"status_code": 0, "status_msg": "still going"},
        })
        fake_post = MagicMock(side_effect=[submit_resp, poll, poll, poll])
        with patch("providers.stock.minimax_video.httpx.post", fake_post):
            with self.assertRaises(MiniMaxVideoError) as ctx:
                provider.fetch("x", self.dest)
        self.assertIn("timeout", str(ctx.exception).lower())

    def test_poll_failed_raises(self):
        provider = MiniMaxVideoProvider(max_polls=3, poll_interval=0)
        submit_resp = _FakeResponse(json_payload={
            "task_id": "task-fail",
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        poll = _FakeResponse(json_payload={
            "status": "Failed",
            "base_resp": {"status_code": 1011, "status_msg": "NSFW detected"},
        })
        fake_post = MagicMock(side_effect=[submit_resp, poll])
        with patch("providers.stock.minimax_video.httpx.post", fake_post):
            with self.assertRaises(MiniMaxVideoError) as ctx:
                provider.fetch("x", self.dest)
        self.assertIn("NSFW detected", str(ctx.exception))

    def test_fetch_with_hex_response(self):
        provider = MiniMaxVideoProvider(max_polls=3, poll_interval=0)
        submit_resp = _FakeResponse(json_payload={
            "task_id": "task-hex",
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        video_bytes = b"\x00\x00\x00\x18ftypmp42" + b"\x42" * 500
        poll = _FakeResponse(json_payload={
            "status": "Success",
            "data": {"video": video_bytes.hex()},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        fake_post = MagicMock(side_effect=[submit_resp, poll])
        with patch("providers.stock.minimax_video.httpx.post", fake_post):
            result = provider.fetch("x", self.dest)
        self.assertEqual(result["bytes"], len(video_bytes))
        self.assertIsNone(result["source_url"])

    def test_healthcheck_ok(self):
        provider = MiniMaxVideoProvider(max_polls=2)
        fake_post = MagicMock(return_value=_FakeResponse(json_payload={
            "task_id": "h-1",
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }))
        with patch("providers.stock.minimax_video.httpx.post", fake_post):
            r = provider.healthcheck()
        self.assertTrue(r["ok"])
        self.assertEqual(r["http_status"], 200)
        self.assertEqual(r["model"], DEFAULT_MODEL)

    def test_healthcheck_401(self):
        provider = MiniMaxVideoProvider(max_polls=2)
        fake_post = MagicMock(return_value=_FakeResponse(status_code=401))
        with patch("providers.stock.minimax_video.httpx.post", fake_post):
            r = provider.healthcheck()
        self.assertFalse(r["ok"])
        self.assertEqual(r["http_status"], 401)
