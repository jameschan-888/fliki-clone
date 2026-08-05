'''R28c-B: chat.py _llm_parse_instruction + _parse_instruction LLM-first + regex fallback.
LLM 默认关闭 (env CHAT_LLM_ENABLED=true 开启), 失败 fallback 到原 6 regex op. schema 校验 limit/aspect/seconds/voice/keyword.
'''

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-ds-key-stub")
os.environ.pop("CHAT_LLM_ENABLED", None)

import sys
sys.path.insert(0, "backend")
from chat import _parse_instruction, _llm_parse_instruction, SUPPORTED_OPS, SUPPORTED_ASPECTS

SOURCE_PATH = "providers.text.deepseek_text.DeepSeekTextProvider"


def _fake_ds(content):
    return {"content": content, "model": "deepseek-chat", "usage": {}}


def _patch_provider(generate_return):
    fake = MagicMock()
    fake.generate = MagicMock(return_value=generate_return)
    return patch(SOURCE_PATH, MagicMock(return_value=fake))


class LlmDisabledTest(unittest.TestCase):
    def test_default_disabled_falls_back_to_regex(self):
        os.environ.pop("CHAT_LLM_ENABLED", None)
        self.assertEqual(_parse_instruction("shorten subtitles to 30"), ("shorten_subtitles", {"limit": 30}))
        self.assertEqual(_parse_instruction("make all 9:16"), ("set_aspect", {"aspect": "9:16"}))
        self.assertEqual(_parse_instruction("voice to zh-CN-XiaoxiaoNeural"), ("set_voice", {"voice": "zh-CN-XiaoxiaoNeural"}))
        self.assertEqual(_parse_instruction("darken everything"), ("adjust_visual", {"keyword": "dark moody"}))
        self.assertEqual(_parse_instruction("xyz gibberish"), (None, None))

    def test_disabled_with_explicit_false_env(self):
        with patch.dict(os.environ, {"CHAT_LLM_ENABLED": "false"}):
            self.assertEqual(_parse_instruction("xyz"), (None, None))
            self.assertEqual(_parse_instruction("shorten scenes by 2s"), ("shorten_duration", {"seconds": 2.0}))


class LlmEnabledHappyPathTest(unittest.TestCase):
    def setUp(self):
        os.environ["CHAT_LLM_ENABLED"] = "true"

    def tearDown(self):
        os.environ.pop("CHAT_LLM_ENABLED", None)

    def test_shorten_subtitles(self):
        c = '{"op": "shorten_subtitles", "params": {"limit": 50}, "confidence": 0.95}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("把字幕压到 50 字以内"), ("shorten_subtitles", {"limit": 50}))

    def test_set_aspect(self):
        c = '{"op": "set_aspect", "params": {"aspect": "9:16"}, "confidence": 0.9}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("改成竖屏"), ("set_aspect", {"aspect": "9:16"}))

    def test_shorten_duration(self):
        c = '{"op": "shorten_duration", "params": {"seconds": 1.5}, "confidence": 0.85}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("每段缩短 1.5 秒"), ("shorten_duration", {"seconds": 1.5}))

    def test_set_voice(self):
        c = '{"op": "set_voice", "params": {"voice": "zh-CN-YunxiNeural"}, "confidence": 0.92}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("声音换成云希"), ("set_voice", {"voice": "zh-CN-YunxiNeural"}))

    def test_adjust_visual(self):
        c = '{"op": "adjust_visual", "params": {"keyword": "cinematic warm tones"}, "confidence": 0.88}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("画面加电影感暖色调"), ("adjust_visual", {"keyword": "cinematic warm tones"}))

    def test_json_with_surrounding_text(self):
        c = '解析如下: {\n  "op": "set_aspect", "params": {"aspect": "1:1"}, "confidence": 0.8\n} 以上'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("变成方形"), ("set_aspect", {"aspect": "1:1"}))


class LlmFallbackTest(unittest.TestCase):
    def setUp(self):
        os.environ["CHAT_LLM_ENABLED"] = "true"

    def tearDown(self):
        os.environ.pop("CHAT_LLM_ENABLED", None)

    def test_provider_init_fails(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            self.assertEqual(_parse_instruction("shorten subtitles to 25"), ("shorten_subtitles", {"limit": 25}))

    def test_generate_raises(self):
        fake = MagicMock()
        fake.generate = MagicMock(side_effect=RuntimeError("api down"))
        with patch(SOURCE_PATH, MagicMock(return_value=fake)):
            self.assertEqual(_parse_instruction("shorten subtitles to 25"), ("shorten_subtitles", {"limit": 25}))

    def test_invalid_json(self):
        with _patch_provider(_fake_ds("not a json at all")):
            self.assertEqual(_parse_instruction("shorten subtitles to 25"), ("shorten_subtitles", {"limit": 25}))

    def test_low_confidence(self):
        c = '{"op": "set_aspect", "params": {"aspect": "16:9"}, "confidence": 0.3}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("something random"), (None, None))

    def test_unsupported_op(self):
        c = '{"op": "delete_everything", "params": {}, "confidence": 0.99}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("something random"), (None, None))

    def test_no_braces_in_response(self):
        with _patch_provider(_fake_ds("我无法解析这个指令")):
            self.assertEqual(_parse_instruction("shorten subtitles to 25"), ("shorten_subtitles", {"limit": 25}))


class LlmSchemaValidationTest(unittest.TestCase):
    def setUp(self):
        os.environ["CHAT_LLM_ENABLED"] = "true"

    def tearDown(self):
        os.environ.pop("CHAT_LLM_ENABLED", None)

    def test_limit_out_of_range_high(self):
        c = '{"op": "limit", "params": {"limit": "999"}, "confidence": 0.9}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("xyz"), (None, None))

    def test_limit_zero(self):
        c = '{"op": "limit", "params": {"limit": "0"}, "confidence": 0.9}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("xyz"), (None, None))

    def test_invalid_aspect(self):
        c = '{"op": "invalid", "params": {"aspect": "21:9"}, "confidence": 0.9}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("xyz"), (None, None))

    def test_seconds_negative(self):
        c = '{"op": "seconds", "params": {"seconds": "-1"}, "confidence": 0.9}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("xyz"), (None, None))

    def test_voice_empty(self):
        c = '{"op": "voice", "params": {"voice": ""}, "confidence": 0.9}'
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("xyz"), (None, None))

    def test_keyword_too_long(self):
        long_kw_str = "x" * 100
        c = "{\"op\": \"adjust_visual\", \"params\": {\"keyword\": \"\" + long_kw_str + \"\"}, \"confidence\": 0.9}"
        with _patch_provider(_fake_ds(c)):
            self.assertEqual(_parse_instruction("xyz"), (None, None))

    def test_supported_ops_constant_complete(self):
        self.assertEqual(len(SUPPORTED_OPS), 5)
        self.assertEqual(SUPPORTED_ASPECTS, ("16:9", "9:16", "1:1"))

    def test_empty_instruction(self):
        self.assertEqual(_parse_instruction(""), (None, None))
        self.assertEqual(_parse_instruction(None), (None, None))
