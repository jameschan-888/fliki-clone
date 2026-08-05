"""R28c-A: ai_split_script (DeepSeek 智能分镜) 测试.
覆盖: init 失败 fallback, JSON 解析 (含前后缀文字), JSON 无效 fallback, generate 异常 fallback,
maximum_scenes 截断, 空 narration 跳过, 缺字段 fallback, DraftCreateBody use_ai 字段.
"""
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-ds-key-stub")

from workflow_drafts import ai_split_script, split_script, DraftCreateBody

# 注意 mock 路径: workflow_drafts.ai_split_script 内部 lazy import
# `from providers.text.deepseek_text import DeepSeekTextProvider`
# patch 必须在类源位置 (providers.text.deepseek_text.DeepSeekTextProvider)
# 才能让函数体内 import 拿到 mock 类.
SOURCE_PATH = "providers.text.deepseek_text.DeepSeekTextProvider"

SAMPLE_SCRIPT = "第一段介绍产品。第二段说明场景草稿。第三段强调确认后才渲染。第四段展望发布效果。" * 5


def _fake_ds_response(content):
    return {"content": content, "model": "deepseek-chat", "usage": {"total_tokens": 100}}


class AiSplitScriptFallbackTest(unittest.TestCase):
    def test_uses_split_script_when_provider_init_fails(self):
        # DEEPSEEK_API_KEY 缺 -> ProviderError -> fallback
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            scenes = ai_split_script(SAMPLE_SCRIPT)
        self.assertGreater(len(scenes), 0)
        self.assertIn("id", scenes[0])
        self.assertIn("narration", scenes[0])
        # fallback 来自 split_script, title 是 "场景 N"
        self.assertTrue(scenes[0]["title"].startswith("场景"))

    def test_uses_split_script_when_generate_raises(self):
        fake_provider = MagicMock()
        fake_provider.generate = MagicMock(side_effect=RuntimeError("api down"))
        with patch(SOURCE_PATH, MagicMock(return_value=fake_provider)):
            scenes = ai_split_script(SAMPLE_SCRIPT)
        self.assertGreater(len(scenes), 0)
        self.assertTrue(scenes[0]["title"].startswith("场景"))

    def test_uses_split_script_when_json_invalid(self):
        fake_provider = MagicMock()
        fake_provider.generate = MagicMock(return_value=_fake_ds_response("not a json at all"))
        with patch(SOURCE_PATH, MagicMock(return_value=fake_provider)):
            scenes = ai_split_script(SAMPLE_SCRIPT)
        self.assertGreater(len(scenes), 0)
        self.assertTrue(scenes[0]["title"].startswith("场景"))

    def test_uses_split_script_when_no_brackets(self):
        fake_provider = MagicMock()
        fake_provider.generate = MagicMock(return_value=_fake_ds_response("口语分镜: 6 场, 请确认"))
        with patch(SOURCE_PATH, MagicMock(return_value=fake_provider)):
            scenes = ai_split_script(SAMPLE_SCRIPT)
        self.assertGreater(len(scenes), 0)
        self.assertTrue(scenes[0]["title"].startswith("场景"))


class AiSplitScriptJsonParseTest(unittest.TestCase):
    def test_parses_pure_json_array(self):
        fake_content = '[{"title":"第一段","narration":"第一段介绍产品。第二段说明场景草稿。","visual_intent":"产品, 介绍, 场景"},{"title":"第二段","narration":"第三段强调确认后才渲染。","visual_intent":"场景, 草稿"}]'
        fake_provider = MagicMock()
        fake_provider.generate = MagicMock(return_value=_fake_ds_response(fake_content))
        with patch(SOURCE_PATH, MagicMock(return_value=fake_provider)):
            scenes = ai_split_script(SAMPLE_SCRIPT)
        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["title"], "第一段")
        self.assertEqual(scenes[0]["visual_intent"], "产品, 介绍, 场景")
        self.assertIn("第一段介绍产品", scenes[0]["narration"])

    def test_handles_json_with_surrounding_text(self):
        fake_content = "好的, 下面是分镜: [\n{\"title\":\"A\",\"narration\":\"片段一\",\"visual_intent\":\"关键词\"}\n]希望对您有帮助"
        fake_provider = MagicMock()
        fake_provider.generate = MagicMock(return_value=_fake_ds_response(fake_content))
        with patch(SOURCE_PATH, MagicMock(return_value=fake_provider)):
            scenes = ai_split_script(SAMPLE_SCRIPT)
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["title"], "A")
        self.assertEqual(scenes[0]["narration"], "片段一")

    def test_fills_missing_title_and_visual_intent(self):
        fake_content = '[{"narration":"一段叙述"}]'
        fake_provider = MagicMock()
        fake_provider.generate = MagicMock(return_value=_fake_ds_response(fake_content))
        with patch(SOURCE_PATH, MagicMock(return_value=fake_provider)):
            scenes = ai_split_script(SAMPLE_SCRIPT)
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["title"], "场景 1")
        self.assertEqual(scenes[0]["visual_intent"], "一段叙述")

    def test_skips_scene_with_empty_narration(self):
        fake_content = '[{"title":"a","narration":"有效片段","visual_intent":"k"},{"title":"b","narration":"","visual_intent":""},{"title":"c","narration":"又一段","visual_intent":"k2"}]'
        fake_provider = MagicMock()
        fake_provider.generate = MagicMock(return_value=_fake_ds_response(fake_content))
        with patch(SOURCE_PATH, MagicMock(return_value=fake_provider)):
            scenes = ai_split_script(SAMPLE_SCRIPT)
        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["title"], "a")
        self.assertEqual(scenes[1]["title"], "c")

    def test_respects_maximum_scenes_limit(self):
        items = []
        for i in range(20):
            items.append("{\"title\":\"seg" + str(i) + "\",\"narration\":\"片段" + str(i) + "\",\"visual_intent\":\"k" + str(i) + "\"}")
        fake_content = "[" + ",".join(items) + "]"
        fake_provider = MagicMock()
        fake_provider.generate = MagicMock(return_value=_fake_ds_response(fake_content))
        with patch(SOURCE_PATH, MagicMock(return_value=fake_provider)):
            scenes = ai_split_script(SAMPLE_SCRIPT, minimum_scenes=3, maximum_scenes=5)
        self.assertEqual(len(scenes), 5)
        self.assertEqual(scenes[0]["title"], "seg0")
        self.assertEqual(scenes[4]["title"], "seg4")


class DraftCreateBodyAiFlagTest(unittest.TestCase):
    def test_use_ai_defaults_to_false(self):
        b = DraftCreateBody(source_script="hi")
        self.assertFalse(b.use_ai)
        self.assertEqual(b.ai_model, "deepseek-chat")

    def test_use_ai_true_with_custom_model(self):
        b = DraftCreateBody(source_script="hi", use_ai=True, ai_model="deepseek-reasoner")
        self.assertTrue(b.use_ai)
        self.assertEqual(b.ai_model, "deepseek-reasoner")