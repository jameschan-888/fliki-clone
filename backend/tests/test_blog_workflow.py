'''R26: blog.py URL fetch + DeepSeek summarize + MiniMax image enrichment.
'''
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-ds-key-stub")

import sys
sys.path.insert(0, "backend")
from workflows.blog import (
    _fetch_url, _ai_summarize_article, _enrich_scenes_with_images,
    _blog_to_scenes_extended, _blog_to_scenes, SUPPORTED_LANGUAGES,
)

DS_PATH = "providers.text.deepseek_text.DeepSeekTextProvider"
IMG_PATH = "providers.stock.minimax_image.MiniMaxImageProvider"

SAMPLE_HTML = "<html><body><h1>标题</h1><p>第一段内容。</p><p>第二段内容。</p><script>alert(1)</script><style>body{}</style><li>列表项</li></body></html>"
SAMPLE_TEXT = "Python 是一门应用广泛的编程语言。它具有高效的数据结构和简清的语法。适合各种项目开发。" * 8

def _fake_urlopen(html_bytes):
    mock_resp = MagicMock()
    mock_resp.read = MagicMock(return_value=html_bytes)
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return patch("urllib.request.urlopen", MagicMock(return_value=mock_resp))

class FetchUrlTest(unittest.TestCase):
    def test_invalid_url_returns_empty(self):
        self.assertEqual(_fetch_url("http://invalid.local.test"), "")
    def test_empty_url_returns_empty(self):
        self.assertEqual(_fetch_url(""), "")
    def test_extracts_p_h_li(self):
        with _fake_urlopen(SAMPLE_HTML.encode("utf-8")):
            text = _fetch_url("http://example.com")
        self.assertIn("标题", text)
        self.assertIn("第一段", text)
        self.assertIn("第二段", text)
        self.assertIn("列表项", text)
        self.assertNotIn("alert", text)
        self.assertNotIn("body{}", text)


class AiSummarizeTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("BLOG_AI_ENABLED", None)

    def tearDown(self):
        os.environ.pop("BLOG_AI_ENABLED", None)

    def _patch_ds(self, content):
        fake = MagicMock()
        fake.generate = MagicMock(return_value={"content": content, "model": "deepseek-chat", "usage": {}})
        return patch(DS_PATH, MagicMock(return_value=fake))

    def test_empty_text_returns_empty(self):
        self.assertEqual(_ai_summarize_article(""), [])
        self.assertEqual(_ai_summarize_article(None), [])

    def test_provider_init_fails_returns_empty(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            self.assertEqual(_ai_summarize_article(SAMPLE_TEXT), [])

    def test_generate_raises_returns_empty(self):
        fake = MagicMock()
        fake.generate = MagicMock(side_effect=RuntimeError("api down"))
        with patch(DS_PATH, MagicMock(return_value=fake)):
            self.assertEqual(_ai_summarize_article(SAMPLE_TEXT), [])

    def test_invalid_json_returns_empty(self):
        with self._patch_ds("not json"):
            self.assertEqual(_ai_summarize_article(SAMPLE_TEXT), [])

    def test_parses_pure_json_array(self):
        c = '[{"title":"a","narration":"一句","visual_intent":"kw"},{"title":"b","narration":"另一句","visual_intent":"kw2"}]'
        with self._patch_ds(c):
            out = _ai_summarize_article(SAMPLE_TEXT)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["title"], "a")
        self.assertEqual(out[0]["narration"], "一句")

    def test_handles_surrounding_text(self):
        c = '总结: [{"title":"x","narration":"内容","visual_intent":"k"}] 完'
        with self._patch_ds(c):
            out = _ai_summarize_article(SAMPLE_TEXT)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "x")

    def test_skips_empty_narration(self):
        c = '[{"title":"a","narration":"ok","visual_intent":"k"},{"title":"b","narration":"","visual_intent":""}]'
        with self._patch_ds(c):
            out = _ai_summarize_article(SAMPLE_TEXT)
        self.assertEqual(len(out), 1)

    def test_limits_to_10_scenes(self):
        items = []
        for i in range(20):
            tpl = chr(123) + chr(34) + chr(116) + chr(105) + chr(116) + chr(108) + chr(101) + chr(34) + chr(58) + chr(34) + chr(88) + chr(34) + chr(44) + chr(34) + chr(110) + chr(97) + chr(114) + chr(114) + chr(97) + chr(116) + chr(105) + chr(111) + chr(110) + chr(34) + chr(58) + chr(34) + chr(115) + chr(101) + chr(103) + chr(32) + chr(88) + chr(34) + chr(44) + chr(34) + chr(118) + chr(105) + chr(115) + chr(117) + chr(97) + chr(108) + chr(95) + chr(105) + chr(110) + chr(116) + chr(101) + chr(110) + chr(116) + chr(34) + chr(58) + chr(34) + chr(107) + chr(88) + chr(34) + chr(125)
            items.append(tpl.replace(chr(34) + chr(88) + chr(34), chr(34) + str(i) + chr(34)))
        c = chr(91) + chr(44).join(items) + chr(93)
        with self._patch_ds(c):
            out = _ai_summarize_article(SAMPLE_TEXT)
        self.assertEqual(len(out), 10)

    def test_disabled_by_env(self):
        with patch.dict(os.environ, {"BLOG_AI_ENABLED": "false"}):
            with self._patch_ds("should not be called"):
                out = _ai_summarize_article(SAMPLE_TEXT)
        self.assertEqual(out, [])


class EnrichImagesTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("BLOG_IMAGE_ENABLED", None)

    def tearDown(self):
        os.environ.pop("BLOG_IMAGE_ENABLED", None)

    def test_disabled_by_default(self):
        scenes = [{"title": "a", "narration": "n", "visual_intent": "k"}]
        with patch(IMG_PATH) as mock_cls:
            out = _enrich_scenes_with_images(scenes)
        self.assertEqual(out, scenes)
        mock_cls.assert_not_called()

    def test_enabled_no_provider_returns_unchanged(self):
        with patch.dict(os.environ, {"BLOG_IMAGE_ENABLED": "true"}):
            with patch(IMG_PATH, MagicMock(side_effect=RuntimeError("no key"))):
                scenes = [{"title": "a", "narration": "n", "visual_intent": "k"}]
                out = _enrich_scenes_with_images(scenes)
        self.assertNotIn("image_url", out[0])

    def test_enabled_adds_image_url_on_success(self):
        with patch.dict(os.environ, {"BLOG_IMAGE_ENABLED": "true"}, clear=False):
            fake_provider = MagicMock()
            fake_provider.fetch = MagicMock(return_value={"url": "https://cdn/x.jpg", "path": "data/blog_images/abc.jpg"})
            with patch(IMG_PATH, MagicMock(return_value=fake_provider)):
                import tempfile
                with tempfile.TemporaryDirectory() as tmp:
                    scenes = [{"title": "a", "narration": "n", "visual_intent": "keyword"}]
                    out = _enrich_scenes_with_images(scenes, output_dir=tmp)
            self.assertEqual(out[0]["image_url"], "https://cdn/x.jpg")
            self.assertIn("image_path", out[0])

    def test_provider_raises_continues(self):
        with patch.dict(os.environ, {"BLOG_IMAGE_ENABLED": "true"}, clear=False):
            fake_provider = MagicMock()
            fake_provider.fetch = MagicMock(side_effect=RuntimeError("rate limit"))
            with patch(IMG_PATH, MagicMock(return_value=fake_provider)):
                import tempfile
                with tempfile.TemporaryDirectory() as tmp:
                    scenes = [{"visual_intent": "k1"}, {"visual_intent": "k2"}]
                    out = _enrich_scenes_with_images(scenes, output_dir=tmp)
            self.assertEqual(len(out), 2)
            for s in out:
                self.assertNotIn("image_url", s)


class BlogExtendedTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("BLOG_AI_ENABLED", None)

    def tearDown(self):
        os.environ.pop("BLOG_AI_ENABLED", None)

    def test_empty_source_returns_empty(self):
        scenes, src = _blog_to_scenes_extended({"": ""}, "zh-CN")
        self.assertEqual(scenes, [])
        self.assertEqual(src, "")

    def test_source_only_uses_split_script(self):
        with patch("workflows.blog._ai_summarize_article", MagicMock(return_value=[])):
            scenes, src = _blog_to_scenes_extended({"source": SAMPLE_TEXT}, "zh-CN")
        self.assertGreater(len(scenes), 0)
        self.assertEqual(src, SAMPLE_TEXT)

    def test_use_ai_true_uses_deepseek(self):
        fake_ai = MagicMock(return_value=[{"title": "x", "narration": "y", "visual_intent": "z"}])
        with patch("workflows.blog._ai_summarize_article", fake_ai):
            scenes, src = _blog_to_scenes_extended({"source": SAMPLE_TEXT}, "zh-CN")
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["title"], "x")
        fake_ai.assert_called_once()

    def test_use_ai_false_skips_deepseek(self):
        fake_ai = MagicMock(return_value=[])
        with patch("workflows.blog._ai_summarize_article", fake_ai):
            scenes, src = _blog_to_scenes_extended({"source": SAMPLE_TEXT, "use_ai": False}, "zh-CN")
        self.assertGreater(len(scenes), 0)
        fake_ai.assert_not_called()

    def test_url_fetches_when_no_source(self):
        fake_fetch = MagicMock(return_value=SAMPLE_TEXT)
        with patch("workflows.blog._fetch_url", fake_fetch), patch("workflows.blog._ai_summarize_article", MagicMock(return_value=[])):
            scenes, src = _blog_to_scenes_extended({"url": "http://blog.example/post"}, "zh-CN")
        fake_fetch.assert_called_once()
        self.assertEqual(src, SAMPLE_TEXT)

    def test_generate_images_called_when_requested(self):
        fake_enrich = MagicMock(side_effect=lambda s, **kw: s)
        with patch("workflows.blog._enrich_scenes_with_images", fake_enrich):
            _blog_to_scenes_extended({"source": SAMPLE_TEXT, "generate_images": True}, "zh-CN")
        fake_enrich.assert_called_once()


class SupportedLanguagesTest(unittest.TestCase):
    def test_contains_zh_and_en(self):
        self.assertIn("zh-CN", SUPPORTED_LANGUAGES)
        self.assertIn("en-US", SUPPORTED_LANGUAGES)
