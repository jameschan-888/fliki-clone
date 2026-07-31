"""P7C-B: TemplateRenderer (mock) + pipeline 集成测试.

覆盖:
- LayerPlan/RenderPlan 数据类序列化
- _resolve_text 优先级 (user_fields > layer.text > placeholder)
- TemplateRenderer.resolve_layer (step_card 特殊路径)
- build_plan / render (mock 模式不真渲染)
- ffmpeg 模式生成 drawtext 命令 list
- remotion 模式生成 React 组件源码字符串
- render_template 函数封装
- pipeline _resolve_template_plan (有/无 template_id + 有/无 row)
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from providers.template_renderer import (
    LayerPlan,
    RenderPlan,
    TemplateRenderer,
    _resolve_text,
    render_template,
)


def _intro_template():
    return {
        "id": "intro_simple",
        "name": "简洁开场",
        "category": "intro",
        "structure": {
            "aspect_ratio": "16:9",
            "duration_seconds": 5,
            "background": {"type": "gradient", "colors": ["#293669", "#0c1020"]},
            "layers": [
                {"type": "logo_text", "text_field": "logo_text", "position": "top-center",
                 "y": 80, "font_size": 28, "color": "#8ba7ff", "animation": "fade_in", "delay": 0.0},
                {"type": "title", "text_field": "title", "position": "center",
                 "y": 0, "font_size": 64, "color": "#eef2ff", "animation": "fade_up", "delay": 0.2},
                {"type": "subtitle", "text_field": "subtitle", "position": "center",
                 "y": 100, "font_size": 26, "color": "#aab3cf", "animation": "fade_up", "delay": 0.5},
            ],
        },
    }


def _step_template():
    return {
        "id": "list_steps",
        "name": "三步教程",
        "structure": {
            "duration_seconds": 6,
            "background": {"type": "solid", "color": "#0c1020"},
            "layers": [
                {"type": "step_card", "index": 1, "title_field": "step1_title", "desc_field": "step1_desc"},
                {"type": "step_card", "index": 2, "title_field": "step2_title", "desc_field": "step2_desc"},
                {"type": "step_card", "index": 3, "title_field": "step3_title", "desc_field": "step3_desc"},
            ],
        },
    }


class LayerPlanTest(unittest.TestCase):
    def test_to_dict_skips_none(self):
        plan = LayerPlan(type="text")
        self.assertEqual(plan.to_dict(), {"type": "text"})

    def test_to_dict_includes_extras(self):
        plan = LayerPlan(type="step_card", text="step", y=0, extras={"index": 1})
        out = plan.to_dict()
        self.assertEqual(out["type"], "step_card")
        self.assertEqual(out["y"], 0)
        self.assertEqual(out["index"], 1)


class RenderPlanTest(unittest.TestCase):
    def test_to_dict_has_all_keys(self):
        rp = RenderPlan(
            template_id="intro_simple",
            background={"type": "solid", "color": "#000"},
            layers=[LayerPlan(type="text", text="hi")],
            duration_seconds=5.0,
            aspect_ratio="16:9",
            provider="mock",
        )
        d = rp.to_dict()
        self.assertEqual(d["template_id"], "intro_simple")
        self.assertEqual(d["layer_count"], 1)
        self.assertEqual(d["provider"], "mock")
        self.assertIsNone(d["placeholder_path"])


class ResolveTextTest(unittest.TestCase):
    def test_user_field_wins(self):
        self.assertEqual(
            _resolve_text({"text_field": "title"}, {"title": "Hello"}),
            "Hello",
        )

    def test_layer_text_fallback(self):
        self.assertEqual(
            _resolve_text({"text_field": "title", "text": "DEFAULT"}, {}),
            "DEFAULT",
        )

    def test_placeholder_when_missing(self):
        self.assertEqual(
            _resolve_text({"text_field": "title"}, {}),
            "{title}",
        )

    def test_none_when_no_text_field(self):
        self.assertIsNone(_resolve_text({}, {}))


class TemplateRendererResolveLayerTest(unittest.TestCase):
    def test_resolves_intro_layers(self):
        t = _intro_template()
        r = TemplateRenderer(t, {"logo_text": "BRAND", "title": "Hi", "subtitle": "Welcome"})
        layers = [r.resolve_layer(layer) for layer in t["structure"]["layers"]]
        self.assertEqual([layer.text for layer in layers], ["BRAND", "Hi", "Welcome"])

    def test_step_card_special_path(self):
        t = _step_template()
        r = TemplateRenderer(t, {
            "step1_title": "Open", "step1_desc": "Open the app",
            "step2_title": "Edit", "step2_desc": "",
            "step3_title": "Save",
        })
        layers = [r.resolve_layer(layer) for layer in t["structure"]["layers"]]
        self.assertEqual(layers[0].text, "Step 1: Open - Open the app")
        self.assertEqual(layers[1].text, "Step 2: Edit")
        self.assertEqual(layers[2].text, "Step 3: Save")

    def test_step_card_missing_title_uses_placeholder(self):
        t = _step_template()
        r = TemplateRenderer(t, {})
        layers = [r.resolve_layer(layer) for layer in t["structure"]["layers"]]
        self.assertEqual(layers[0].text, "Step 1: {missing}")


class BuildPlanTest(unittest.TestCase):
    def test_plan_structure(self):
        t = _intro_template()
        r = TemplateRenderer(t, {"title": "Hi"}, scene_id="s1")
        plan = r.build_plan()
        self.assertEqual(plan.template_id, "intro_simple")
        self.assertEqual(plan.aspect_ratio, "16:9")
        self.assertEqual(plan.duration_seconds, 5.0)
        self.assertEqual(len(plan.layers), 3)
        self.assertEqual(plan.provider, "mock")
        self.assertTrue(plan.placeholder_path.endswith("mock-s1.mp4"))

    def test_duration_override(self):
        t = _intro_template()
        r = TemplateRenderer(t, {"title": "Hi"}, duration_override=8.5)
        self.assertEqual(r.build_plan().duration_seconds, 8.5)

    def test_empty_structure(self):
        t = {"id": "x", "structure": {}}
        r = TemplateRenderer(t, {})
        plan = r.build_plan()
        self.assertEqual(plan.layers, [])
        self.assertEqual(plan.background, {"type": "solid", "color": "#000000"})
        self.assertEqual(plan.duration_seconds, 5.0)


class RenderTest(unittest.TestCase):
    def test_mock_mode_no_ffmpeg(self):
        t = _intro_template()
        r = TemplateRenderer(t, {"title": "Hi"}, scene_id="s1")
        out = r.render(destination="/tmp/x.mp4")
        self.assertTrue(out["ok"])
        self.assertTrue(out["mock"])
        self.assertNotIn("ffmpeg_commands", out)
        self.assertNotIn("react_source", out)
        self.assertEqual(out["destination"], "/tmp/x.mp4")

    def test_ffmpeg_mode_includes_commands(self):
        t = _intro_template()
        r = TemplateRenderer(t, {"title": "Hi"}, mode="ffmpeg", scene_id="s1")
        out = r.render()
        self.assertFalse(out["mock"])
        cmds = out["ffmpeg_commands"]
        self.assertGreater(len(cmds), 0)
        self.assertTrue(any("gradbg" in c or "color=c=" in c for c in cmds))

    def test_remotion_mode_includes_source(self):
        t = _intro_template()
        r = TemplateRenderer(t, {"title": "Hi"}, mode="remotion")
        out = r.render()
        self.assertIn("react_source", out)
        self.assertIn("Template_intro_simple", out["react_source"])
        self.assertIn("AbsoluteFill", out["react_source"])


class RenderTemplateFunctionTest(unittest.TestCase):
    def test_function_wrapper(self):
        out = render_template(_intro_template(), {"title": "Hi"}, scene_id="s1")
        self.assertTrue(out["ok"])
        self.assertEqual(out["plan"]["template_id"], "intro_simple")


class PipelineHelperTest(unittest.TestCase):
    """测试 _resolve_template_plan 在 pipeline 中的接入点."""

    def _make_db(self):
        fd, path = tempfile.mkstemp(suffix=".sqlite")
        import os as _os
        _os.close(fd)
        schema = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.executescript(schema.read_text(encoding="utf-8"))
        # template_id / template_fields columns (init_db 也会 ALTER; 幂等探测避免 duplicate column error)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(scene_drafts)").fetchall()}
        for col in ("template_id", "template_fields"):
            if col not in existing:
                conn.execute("ALTER TABLE scene_drafts ADD COLUMN " + col + " TEXT")
        conn.commit()
        conn.close()
        return path

    def _seed_template(self, conn):
        cfg = json.dumps({"fields": [], "structure": {"background": {"type": "solid", "color": "#000"}, "layers": []}})
        conn.execute("INSERT INTO templates (id, name, category, description, enabled, builtin, config_json, created_at) VALUES ('intro_simple', 'Intro', 'intro', '', 1, 1, ?, 0)", (cfg,))
        conn.commit()

    def test_no_template_id_returns_skipped(self):
        from workflow_pipeline import _resolve_template_plan
        path = self._make_db()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        result = _resolve_template_plan({"id": "scene1", "template_id": None}, conn)
        conn.close()
        # helper 现在返回 (provider, dict)
        provider, body = result
        self.assertFalse(body["ok"])
        self.assertTrue(body["skipped"])

    def test_unknown_template_returns_skipped(self):
        from workflow_pipeline import _resolve_template_plan
        path = self._make_db()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        result = _resolve_template_plan({"id": "scene1", "template_id": "nonexistent"}, conn)
        conn.close()
        provider, body = result
        self.assertFalse(body["ok"])

    def test_known_template_returns_plan(self):
        from workflow_pipeline import _resolve_template_plan
        path = self._make_db()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        self._seed_template(conn)
        result = _resolve_template_plan(
            {"id": "scene1", "template_id": "intro_simple", "template_fields": {}}, conn,
        )
        conn.close()
        provider, body = result
        self.assertEqual(provider, "template_mock")
        self.assertTrue(body["ok"])
        self.assertEqual(body["plan"]["template_id"], "intro_simple")
        self.assertTrue(body["mock"])

    def test_string_fields_json_decoded(self):
        from workflow_pipeline import _resolve_template_plan
        path = self._make_db()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        self._seed_template(conn)
        result = _resolve_template_plan(
            {"id": "scene1", "template_id": "intro_simple", "template_fields": json.dumps({"title": "Hi"})}, conn,
        )
        conn.close()
        provider, body = result
        self.assertTrue(body["ok"])


def test_pipeline_returns_provider_tuple(self):
        from workflow_pipeline import _resolve_template_plan
        path = self._make_db()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        self._seed_template(conn)
        result = _resolve_template_plan(
            {"id": "scene1", "template_id": "intro_simple", "template_fields": {}}, conn,
        )
        conn.close()
        # run_node 期望 (provider, dict)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "template_mock")
        self.assertTrue(result[1]["ok"])


if __name__ == "__main__":
    unittest.main()
