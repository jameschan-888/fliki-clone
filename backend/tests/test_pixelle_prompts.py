import unittest

from pixelle_prompts import (
    SCENE_NARRATION,
    SCRIPT_BREAKDOWN,
    TITLE_GENERATION,
    VISUAL_INTENT,
    get_template,
    list_templates,
    render_prompt,
)


class ListTemplatesTest(unittest.TestCase):
    def test_returns_all_four(self):
        names = list_templates()
        self.assertEqual(len(names), 4)
        for n in (SCRIPT_BREAKDOWN, SCENE_NARRATION, TITLE_GENERATION, VISUAL_INTENT):
            self.assertIn(n, names)


class GetTemplateTest(unittest.TestCase):
    def test_valid_template(self):
        tpl = get_template(SCRIPT_BREAKDOWN)
        self.assertIsInstance(tpl, str)
        self.assertGreater(len(tpl), 100)

    def test_unknown_raises(self):
        with self.assertRaises(KeyError):
            get_template("not_a_template")


class RenderPromptTest(unittest.TestCase):
    def test_script_breakdown_renders(self):
        out = render_prompt(
            SCRIPT_BREAKDOWN,
            script="hello world",
            language="zh-CN",
            min_scenes=3,
            max_scenes=8,
        )
        self.assertIn("hello world", out)
        self.assertIn("zh-CN", out)
        self.assertIn("3-8", out)  # min-max scenes
        self.assertIn("场景", out)  # Chinese phrase for scene

    def test_scene_narration_renders(self):
        out = render_prompt(
            SCENE_NARRATION,
            title="场景 1",
            visual_intent="海洋",
            context="温馨的日出",
            min_chars=30,
            max_chars=80,
            language="zh-CN",
        )
        self.assertIn("场景 1", out)
        self.assertIn("海洋", out)
        self.assertIn("30-80", out)

    def test_title_generation_renders(self):
        out = render_prompt(
            TITLE_GENERATION,
            script="一个故事",
            max_chars=20,
            language="zh-CN",
        )
        self.assertIn("一个故事", out)
        self.assertIn("20", out)
        self.assertIn("JSON", out)

    def test_visual_intent_renders(self):
        out = render_prompt(VISUAL_INTENT, narration="太阳升起", language="zh-CN")
        self.assertIn("太阳升起", out)
        self.assertIn("关键词", out)  # keywords in Chinese

    def test_missing_param_raises(self):
        with self.assertRaises(KeyError):
            render_prompt(SCRIPT_BREAKDOWN, script="hi")  # missing language/min/max

    def test_unknown_template_raises(self):
        with self.assertRaises(KeyError):
            render_prompt("fake", script="hi")


class TemplateContentTest(unittest.TestCase):
    """检查模板包含关键指令 (防止脱字或被篡改)."""

    def test_breakdown_has_3_to_n_scenes(self):
        tpl = get_template(SCRIPT_BREAKDOWN)
        self.assertIn("min_scenes", tpl)
        self.assertIn("max_scenes", tpl)
        self.assertIn("language", tpl)
        self.assertIn("script", tpl)

    def test_narration_has_constraints(self):
        tpl = get_template(SCENE_NARRATION)
        self.assertIn("min_chars", tpl)
        self.assertIn("max_chars", tpl)

    def test_title_has_max_chars(self):
        tpl = get_template(TITLE_GENERATION)
        self.assertIn("max_chars", tpl)

    def test_visual_intent_has_narration(self):
        tpl = get_template(VISUAL_INTENT)
        self.assertIn("narration", tpl)


if __name__ == "__main__":
    unittest.main()

