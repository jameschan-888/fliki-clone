import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-ds-key-stub")

from providers.base import ProviderError
from providers.text.deepseek_text import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DeepSeekError,
    DeepSeekTextProvider,
)


class _FakeResponse:
    def __init__(self, status_code=200, json_payload=None, text=""):
        self.status_code = status_code
        self.text = text
        self._json = json_payload

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


class DeepSeekTextProviderTest(unittest.TestCase):
    def test_init_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEEPSEEK_API_KEY", None)
            with self.assertRaises(ProviderError):
                DeepSeekTextProvider(api_key="")

    def test_init_with_explicit_key(self):
        p = DeepSeekTextProvider(api_key="explicit-key", model="deepseek-reasoner")
        self.assertEqual(p.api_key, "explicit-key")
        self.assertEqual(p.model, "deepseek-reasoner")
        self.assertEqual(p.name, "deepseek")
        self.assertTrue(p.base_url.startswith("https://"))

    def test_generate_rejects_empty_prompt(self):
        p = DeepSeekTextProvider(api_key="k")
        with self.assertRaises(ProviderError):
            p.generate("")
        with self.assertRaises(ProviderError):
            p.generate("   ")

    def test_generate_posts_to_chat_completions_with_bearer(self):
        p = DeepSeekTextProvider(api_key="abc123")
        fake_resp = _FakeResponse(json_payload={"choices": [{"message": {"content": "你好"}}], "model": "deepseek-chat", "usage": {"total_tokens": 5}})
        fake_post = MagicMock(return_value=fake_resp)
        with patch("providers.text.deepseek_text.httpx.post", fake_post):
            result = p.generate("hello")
        args, kwargs = fake_post.call_args
        self.assertIn("/v1/chat/completions", args[0])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer abc123")
        self.assertEqual(kwargs["json"]["model"], "deepseek-chat")
        self.assertEqual(kwargs["json"]["messages"][-1]["role"], "user")
        self.assertEqual(kwargs["json"]["messages"][-1]["content"], "hello")
        self.assertFalse(kwargs["json"]["stream"])
        self.assertEqual(result["content"], "你好")
        self.assertEqual(result["model"], "deepseek-chat")
        self.assertEqual(result["usage"]["total_tokens"], 5)

    def test_generate_includes_system_message_when_given(self):
        p = DeepSeekTextProvider(api_key="k")
        fake_resp = _FakeResponse(json_payload={"choices": [{"message": {"content": "ok"}}]})
        fake_post = MagicMock(return_value=fake_resp)
        with patch("providers.text.deepseek_text.httpx.post", fake_post):
            p.generate("q", system="You are helpful")
        messages = fake_post.call_args.kwargs["json"]["messages"]
        self.assertEqual(messages[0], {"role": "system", "content": "You are helpful"})
        self.assertEqual(messages[-1]["content"], "q")

    def test_generate_raises_on_http_error(self):
        p = DeepSeekTextProvider(api_key="k")
        fake_resp = _FakeResponse(status_code=401, text="invalid api key")
        with patch("providers.text.deepseek_text.httpx.post", MagicMock(return_value=fake_resp)):
            with self.assertRaises(DeepSeekError) as cm:
                p.generate("hi")
        self.assertIn("401", str(cm.exception))

    def test_generate_raises_on_empty_choices(self):
        p = DeepSeekTextProvider(api_key="k")
        fake_resp = _FakeResponse(json_payload={"choices": []})
        with patch("providers.text.deepseek_text.httpx.post", MagicMock(return_value=fake_resp)):
            with self.assertRaises(DeepSeekError):
                p.generate("hi")

    def test_generate_raises_on_non_json(self):
        p = DeepSeekTextProvider(api_key="k")
        fake_resp = _FakeResponse(status_code=200, json_payload=None, text="<html>oops</html>")
        with patch("providers.text.deepseek_text.httpx.post", MagicMock(return_value=fake_resp)):
            with self.assertRaises(DeepSeekError):
                p.generate("hi")

    def test_max_tokens_clamped_to_8192(self):
        p = DeepSeekTextProvider(api_key="k")
        fake_resp = _FakeResponse(json_payload={"choices": [{"message": {"content": "ok"}}]})
        fake_post = MagicMock(return_value=fake_resp)
        with patch("providers.text.deepseek_text.httpx.post", fake_post):
            p.generate("hi", max_tokens=99999)
        self.assertEqual(fake_post.call_args.kwargs["json"]["max_tokens"], 8192)
