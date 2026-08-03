"""4 大缺失工作流 (Blog/PPT/Record/Translate) 单元测试.
- source_to_scenes 转换正确性
- 空输入返回空列表
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockWorkflowsTest(unittest.TestCase):
    """测试 4 大 workflow 的 source_to_scenes 逻辑 (无需 DB / 网络)."""

    def test_blog_to_scenes_strips_html(self):
        from workflows.blog import _blog_to_scenes
        body = {"source": "<p>第一段。</p><p>第二段！</p><p>第三段？</p><p>第四段；</p><p>第五段。</p>" }
        scenes, src = _blog_to_scenes(body, "zh-CN")
        self.assertGreater(len(scenes), 0, "blog 应该至少 1 个 scene")
        self.assertEqual(src, body["source"])
        for s in scenes:
            self.assertIn("narration", s)
            self.assertNotIn("<", s.get("narration", ""), "html 标签应被剥离")

    def test_ppt_to_scenes_one_per_slide(self):
        from workflows.ppt import _ppt_to_scenes
        body = {
            "slides": [
                {"title": "封面", "content": "公司简介。"},
                {"title": "正文", "content": "产品特点。"},
                {"title": "", "content": "联系方式。"},
            ]
        }
        scenes, src = _ppt_to_scenes(body, "zh-CN")
        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["title"], "封面")
        self.assertEqual(scenes[1]["title"], "正文")
        self.assertEqual(scenes[2]["title"], "幻灯片 3")
        self.assertIn("PPT 共", src)

    def test_ppt_empty_returns_empty(self):
        from workflows.ppt import _ppt_to_scenes
        scenes, src = _ppt_to_scenes({"slides": []}, "zh-CN")
        self.assertEqual(scenes, [])
        self.assertEqual(src, "")

    def test_record_to_scenes_from_transcript(self):
        from workflows.record import _record_to_scenes
        body = {"transcript": "欢迎！今天讲 AI 视频生成。第一步写脚本。第二步选素材。第三步渲染。"}
        scenes, src = _record_to_scenes(body, "zh-CN")
        self.assertGreater(len(scenes), 0)
        self.assertEqual(src, body["transcript"])

    def test_translate_to_scenes_with_lang(self):
        from workflows.translate import _translate_to_scenes
        body = {"source": "Welcome to my channel. First step. Second step.", "source_lang": "zh-CN", "target_lang": "en-US"}
        scenes, src = _translate_to_scenes(body, "en-US")
        self.assertGreater(len(scenes), 0)
        self.assertIn("zh-CN", src)
        self.assertIn("en-US", src)

    def test_all_empty_returns_empty(self):
        from workflows.blog import _blog_to_scenes
        from workflows.ppt import _ppt_to_scenes
        from workflows.record import _record_to_scenes
        from workflows.translate import _translate_to_scenes
        self.assertEqual(_blog_to_scenes({}, "zh-CN")[0], [])
        self.assertEqual(_ppt_to_scenes({}, "zh-CN")[0], [])
        self.assertEqual(_record_to_scenes({}, "zh-CN")[0], [])
        self.assertEqual(_translate_to_scenes({}, "zh-CN")[0], [])

    def test_blog_short_text(self):
        """短文本 (1 句) 也能生成至少 1 个 scene."""
        from workflows.blog import _blog_to_scenes
        scenes, _ = _blog_to_scenes({"source": "一句话测试。"}, "zh-CN")
        self.assertGreaterEqual(len(scenes), 1)

    def test_blog_extended_fetches_url_when_source_missing(self):
        import workflows.blog as blog
        original = blog._fetch_url
        try:
            blog._fetch_url = lambda url: "远程文章第一段。远程文章第二段。"
            scenes, source = blog._blog_to_scenes_extended({"url": "https://example.com/post"}, "zh-CN")
        finally:
            blog._fetch_url = original
        self.assertGreaterEqual(len(scenes), 1)
        self.assertIn("远程文章", source)

    def test_ppt_extended_uses_parsed_pptx_when_slides_missing(self):
        import workflows.ppt as ppt
        original = ppt._parse_pptx
        try:
            ppt._parse_pptx = lambda path: [{"title": "导入页", "content": "导入内容。"}]
            scenes, source = ppt._ppt_to_scenes_extended({"pptx_path": "demo.pptx"}, "zh-CN")
        finally:
            ppt._parse_pptx = original
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["title"], "导入页")
        self.assertIn("PPT 共 1 页", source)

    def test_record_extended_preserves_client_transcript(self):
        from workflows.record import _record_to_scenes_extended
        scenes, source = _record_to_scenes_extended({"transcript": "客户端转写内容。"}, "zh-CN")
        self.assertGreaterEqual(len(scenes), 1)
        self.assertEqual(source, "客户端转写内容。")

    def test_translate_extended_preserves_language_metadata(self):
        from workflows.translate import _translate_to_scenes_extended
        scenes, source = _translate_to_scenes_extended({"source": "Hello world.", "source_lang": "en-US", "target_lang": "zh-CN"}, "zh-CN")
        self.assertGreaterEqual(len(scenes), 1)
        self.assertIn("en-US", source)
        self.assertIn("zh-CN", source)
    def test_record_extended_uses_local_asr(self):
        import workflows.record as record
        import autoedit
        original = autoedit.transcribe_audio
        try:
            autoedit.transcribe_audio = lambda path, language: "ASR 生成的文字。"
            scenes, source = record._record_to_scenes_extended({"audio_path": "demo.webm"}, "zh-CN")
        finally:
            autoedit.transcribe_audio = original
        self.assertGreaterEqual(len(scenes), 1)
        self.assertEqual(source, "ASR 生成的文字。")

    def test_translate_extended_uses_configured_mt(self):
        import workflows.translate as translate
        original = translate._translate_text
        try:
            translate._translate_text = lambda text, source, target: "已翻译内容。"
            scenes, source = translate._translate_to_scenes_extended({"source": "Original.", "source_lang": "en-US", "target_lang": "zh-CN"}, "zh-CN")
        finally:
            translate._translate_text = original
        self.assertGreaterEqual(len(scenes), 1)
        self.assertIn("已翻译内容", source)

if __name__ == "__main__":
    unittest.main()
