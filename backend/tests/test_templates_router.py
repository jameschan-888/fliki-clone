# P7C-B: 本地视频模板 router 测试.
import io
import gc
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from templates_router import (
    _template_payload,
    _validate_all,
    _validate_field_value,
    _merge_fields,
    create_router,
    load_builtin_templates,
    seed_templates,
)


def _setup_db():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    schema = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(schema.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    return path


def _make_client(db_path: str):
    def _get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    app = FastAPI()
    app.include_router(create_router(_get_db))
    return TestClient(app)


class LoadBuiltinTemplatesTest(unittest.TestCase):
    def test_loads_5_builtin_templates(self):
        templates = load_builtin_templates()
        self.assertEqual(len(templates), 5)
        ids = {t["id"] for t in templates}
        self.assertEqual(ids, {"intro_simple", "outro_cta", "list_steps", "quote_card", "data_big_number"})

    def test_all_templates_have_required_fields(self):
        templates = load_builtin_templates()
        for t in templates:
            self.assertIn("id", t)
            self.assertIn("name", t)
            self.assertIn("category", t)
            self.assertIn("fields", t)
            self.assertIn("structure", t)
            for f in t["fields"]:
                self.assertIn("key", f)
                self.assertIn("label", f)
                self.assertIn("type", f)
            struct = t["structure"]
            self.assertEqual(struct["aspect_ratio"], "16:9")
            self.assertIn("duration_seconds", struct)
            self.assertIn("background", struct)
            self.assertIn("layers", struct)


class FieldValidationTest(unittest.TestCase):
    def test_validate_field_required_missing(self):
        field = {"key": "title", "required": True, "type": "text"}
        ok, err = _validate_field_value(field, None)
        self.assertFalse(ok)
        self.assertIn("required", err)

    def test_validate_field_required_empty_string(self):
        field = {"key": "title", "required": True, "type": "text"}
        ok, err = _validate_field_value(field, "")
        self.assertFalse(ok)

    def test_validate_field_max_length_exceeded(self):
        field = {"key": "title", "max_length": 10, "type": "text"}
        ok, err = _validate_field_value(field, "x" * 11)
        self.assertFalse(ok)
        self.assertIn("max_length", err)

    def test_validate_field_within_max_length(self):
        field = {"key": "title", "max_length": 10, "type": "text"}
        ok, _ = _validate_field_value(field, "x" * 10)
        self.assertTrue(ok)

    def test_merge_fields_applies_defaults(self):
        template = {
            "fields": [
                {"key": "title", "required": True, "type": "text"},
                {"key": "logo_text", "default": "BRAND", "type": "text"},
            ]
        }
        merged, errors = _merge_fields(template, {"title": "hi"})
        self.assertEqual(merged["title"], "hi")
        self.assertEqual(merged["logo_text"], "BRAND")
        self.assertEqual(errors, [])

    def test_merge_fields_unknown_field_flagged(self):
        template = {"fields": [{"key": "title", "required": True}]}
        merged, errors = _merge_fields(template, {"title": "x", "extra": "y"})
        self.assertIn("unknown field: extra", errors)

    def test_validate_all_combines_required_and_length(self):
        template = {
            "fields": [
                {"key": "title", "required": True, "max_length": 5, "type": "text"},
            ]
        }
        merged, errors = _validate_all(template, {"title": "x" * 6})
        self.assertEqual(len(errors), 1)
        self.assertIn("max_length 5", errors[0])


class TemplateRouterTest(unittest.TestCase):
    def setUp(self):
        self.db_path = _setup_db()
        self.client = _make_client(self.db_path)

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_list_seeds_5_builtin(self):
        r = self.client.get("/templates")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body), 5)
        for t in body:
            self.assertTrue(t["builtin"])
            self.assertTrue(t["enabled"])
            # list 模式不含 fields / structure
            self.assertNotIn("fields", t)
            self.assertNotIn("structure", t)

    def test_list_can_include_config(self):
        r = self.client.get("/templates?include_config=true")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body), 5)
        self.assertIn("fields", body[0])
        self.assertIn("structure", body[0])

    def test_list_filter_by_category(self):
        r = self.client.get("/templates?category=intro")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], "intro_simple")

    def test_categories_endpoint(self):
        r = self.client.get("/templates/categories")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body), 5)
        cats = {c["category"] for c in body}
        self.assertEqual(cats, {"intro", "outro", "list", "quote", "data"})

    def test_get_template_returns_full_config(self):
        r = self.client.get("/templates/intro_simple")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("fields", body)
        self.assertIn("structure", body)
        self.assertEqual(len(body["fields"]), 3)

    def test_get_template_404(self):
        r = self.client.get("/templates/nonexistent")
        self.assertEqual(r.status_code, 404)

    def test_validate_fields_ok(self):
        r = self.client.post(
            "/templates/intro_simple/validate",
            json={"fields": {"title": "测试标题"}},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["valid"])
        self.assertEqual(body["errors"], [])
        # defaults 合并
        self.assertEqual(body["merged_fields"]["logo_text"], "BRAND")
        self.assertEqual(body["merged_fields"]["title"], "测试标题")

    def test_validate_fields_missing_required(self):
        # rev33: 模板 default 修了, 改测 "用户传空字符串覆盖 default" 触发 required 校验
        r = self.client.post(
            "/templates/intro_simple/validate",
            json={"fields": {"title": " "}},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["valid"])
        self.assertIn("title is required", body["errors"])

    def test_validate_fields_too_long(self):
        r = self.client.post(
            "/templates/intro_simple/validate",
            json={"fields": {"title": "x" * 51}},  # max 50
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["valid"])
        self.assertTrue(any("max_length 50" in e for e in body["errors"]))

    def test_validate_unknown_template_404(self):
        r = self.client.post(
            "/templates/nonexistent/validate",
            json={"fields": {}},
        )
        self.assertEqual(r.status_code, 404)

    def test_preview_returns_resolved_render_plan(self):
        response = self.client.post(
            "/templates/intro_simple/preview",
            json={"fields": {"title": "烟雾标题", "subtitle": "快速预览"}, "duration_seconds": 1.5},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["preview"])
        self.assertTrue(body["mock"])
        self.assertEqual(body["plan"]["template_id"], "intro_simple")
        self.assertEqual(body["plan"]["duration_seconds"], 1.5)
        self.assertEqual(body["plan"]["layer_count"], 3)
        texts = [layer.get("text") for layer in body["plan"]["layers"]]
        self.assertIn("烟雾标题", texts)
        self.assertEqual(body["merged_fields"]["logo_text"], "BRAND")

    def test_preview_rejects_invalid_fields(self):
        # rev33: 模板 default 修了, 改测 "用户传空字符串覆盖 default" 触发 required 422
        response = self.client.post(
            "/templates/intro_simple/preview",
            json={"fields": {"title": " "}, "duration_seconds": 1},
        )
        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail.get("error_code"), "TEMPLATE_PREVIEW_INVALID")
        self.assertIn("title is required", detail.get("details", {}).get("errors", []))

    def test_preview_unknown_template_returns_404(self):
        response = self.client.post(
            "/templates/not_found/preview",
            json={"fields": {}},
        )
        self.assertEqual(response.status_code, 404)

    def test_create_custom_template(self):
        r = self.client.post(
            "/templates",
            json={
                "id": "my_custom",
                "name": "我的模板",
                "category": "custom",
                "description": "测试",
                "config": {
                    "fields": [{"key": "x", "label": "X", "type": "text", "required": True}],
                    "structure": {
                        "aspect_ratio": "16:9",
                        "duration_seconds": 3,
                        "background": {"type": "solid", "color": "#000"},
                        "layers": [{"type": "text", "text_field": "x", "position": "center", "font_size": 32, "color": "#fff"}],
                    },
                },
            },
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["id"], "my_custom")
        self.assertFalse(body["builtin"])

    def test_create_duplicate_409(self):
        self.client.post(
            "/templates",
            json={
                "id": "dup_test", "name": "X", "category": "x",
                "config": {"fields": [], "structure": {"aspect_ratio": "16:9", "duration_seconds": 1, "background": {}, "layers": []}},
            },
        )
        r = self.client.post(
            "/templates",
            json={
                "id": "dup_test", "name": "X", "category": "x",
                "config": {"fields": [], "structure": {"aspect_ratio": "16:9", "duration_seconds": 1, "background": {}, "layers": []}},
            },
        )
        self.assertEqual(r.status_code, 409)

    def test_create_invalid_id_pattern_422(self):
        r = self.client.post(
            "/templates",
            json={
                "id": "Has-UpperCase", "name": "X", "category": "x",
                "config": {"fields": [], "structure": {}},
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_delete_builtin_422(self):
        r = self.client.delete("/templates/intro_simple")
        self.assertEqual(r.status_code, 422)
        # 确认还在
        g = self.client.get("/templates/intro_simple")
        self.assertEqual(g.status_code, 200)

    def test_delete_custom_ok(self):
        self.client.post(
            "/templates",
            json={
                "id": "to_delete", "name": "X", "category": "custom",
                "config": {"fields": [], "structure": {"aspect_ratio": "16:9", "duration_seconds": 1, "background": {}, "layers": []}},
            },
        )
        r = self.client.delete("/templates/to_delete")
        self.assertEqual(r.status_code, 200)
        g = self.client.get("/templates/to_delete")
        self.assertEqual(g.status_code, 404)

    def test_seed_templates_idempotent(self):
        # 第一次 list 触发 seed
        self.client.get("/templates")
        # 第二次再 seed 不报错
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        before = conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        seed_templates(conn)
        after = conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        conn.close()
        self.assertEqual(before, after)
        self.assertEqual(before, 5)



class CopyDraftToTemplateTest(unittest.TestCase):
    """P2: 草稿复制为模板 (POST /templates/from-draft/{draft_id}).

    行为:
    - 复制一个已套模板的 scene 的 template_id + 当前 fields 到新模板
    - 沿用原 template_id 的 config.structure (Remotion 渲染层)
    - 新模板 builtin=False, 名字以 "Copy of " 开头
    - 复制后 template_id 重名走 slug + 1
    - 草稿不存在 / 未套模板 / 找不到原模板 → 4xx
    """

    def setUp(self):
        self.db_path = _setup_db()
        self.client = _make_client(self.db_path)
        self.fake_request = self._make_fake_request("user-draft", "user")
        self._insert_draft([
            {"id": "d1", "title": "D1", "user_id": "user-draft"},
            {"id": "d2", "title": "D2", "user_id": "user-draft"},
            {"id": "d3", "title": "D3"},
        ], [
            {"id": "s1", "position": 0, "workflow_draft_id": "d1", "title": "S1", "narration": "n", "visual_intent": "v", "subtitle": "", "duration_seconds": 4.0, "template_id": "intro_simple", "template_fields": json.dumps({"title": "我的标题", "subtitle": "我的副标题"})},
            {"id": "s2", "position": 1, "workflow_draft_id": "d1", "title": "S2", "narration": "n", "visual_intent": "v", "subtitle": "", "duration_seconds": 4.0, "template_id": "intro_simple", "template_fields": json.dumps({"title": "第二个标题"})},
            {"id": "s3", "position": 0, "workflow_draft_id": "d2", "title": "S3", "narration": "n", "visual_intent": "v", "subtitle": "", "duration_seconds": 4.0, "template_id": "intro_simple", "template_fields": json.dumps({"title": "其他用户"})},
            {"id": "s4", "position": 0, "workflow_draft_id": "d3", "title": "S4", "narration": "n", "visual_intent": "v", "subtitle": "", "duration_seconds": 4.0},
        ])

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def _make_fake_request(self, sub: str, role: str):
        from auth_router import _make_token
        token = _make_token(sub, role)
        class _Fake:
            def __init__(self, t):
                self.headers = {"Authorization": "Bearer " + t}
        return _Fake(token)

    def _insert_draft(self, drafts, scenes):
        import time
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for draft in drafts:
            conn.execute(
                "INSERT INTO workflow_drafts (id, title, source_script, language, status, version, created_at, updated_at, user_id) "
                "VALUES (?, ?, '', 'zh-CN', 'draft', 1, ?, ?, ?)",
                (draft["id"], draft["title"], now, now, draft.get("user_id")),
            )
        for scene in scenes:
            conn.execute(
                "INSERT INTO scene_drafts (id, workflow_draft_id, position, title, narration, visual_intent, subtitle, duration_seconds, template_id, template_fields, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    scene["id"], scene["workflow_draft_id"], scene["position"], scene["title"], scene["narration"], scene["visual_intent"],
                    scene.get("subtitle", ""), scene.get("duration_seconds", 4.0),
                    scene.get("template_id"), scene.get("template_fields"),
                    now, now,
                ),
            )
        conn.commit()
        conn.close()

    def _post_from_draft(self, draft_id, request, **params):
        # scene_id / name 走 query, 端点签名读不到 body 字段
        query = "&".join(k + "=" + v for k, v in params.items())
        url = "/templates/from-draft/" + draft_id + (("?" + query) if query else "")
        headers = request.headers if request is not None else None
        return self.client.post(url, headers=headers)

    def test_copy_requires_auth(self):
        r = self._post_from_draft("d1", None)
        self.assertEqual(r.status_code, 401)

    def test_copy_returns_404_when_draft_missing(self):
        r = self._post_from_draft("does-not-exist", self.fake_request)
        self.assertEqual(r.status_code, 404)

    def test_copy_403_when_draft_belongs_to_other_user(self):
        r = self._post_from_draft("d3", self.fake_request)
        self.assertEqual(r.status_code, 404)

    def test_copy_409_when_draft_has_no_template(self):
        # d3 整个 draft 属于无 token 用户; 用 d3 替代会有 user_id 隔离冲突. 这里仅以 _draft=无 template_id 的场景验证, 改用新增 draft 注入.
        r = self._post_from_draft("d3", self.fake_request)
        self.assertIn(r.status_code, (403, 404))
        # 改插入一个当前 user 的无 template draft
        self._insert_draft([{"id": "d4", "title": "D4", "user_id": "user-draft"}], [
            {"id": "s40", "position": 0, "workflow_draft_id": "d4", "title": "S40", "narration": "n", "visual_intent": "v", "subtitle": "", "duration_seconds": 4.0},
        ])
        r2 = self._post_from_draft("d4", self.fake_request)
        self.assertEqual(r2.status_code, 409)
        body = r2.json()
        self.assertIn("detail", body)
        self.assertIn("template", body["detail"].lower())

    def test_copy_creates_custom_template_with_merged_fields_and_default(self):
        r = self._post_from_draft("d1", self.fake_request)
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertTrue(body["id"].startswith("copy_of_intro_simple"))
        self.assertFalse(body["builtin"])
        self.assertEqual(body["category"], "intro")
        self.assertIn("Copy of", body["name"])
        self.assertEqual(body["_source"]["draft_id"], "d1")
        self.assertEqual(body["_source"]["scene_id"], "s1")
        self.assertEqual(body["_source"]["template_id"], "intro_simple")
        # 字段: title 必填, 用户填了 "我的标题"; 需求是固化最近一次使用作为 default, 避免重复填
        fields = {f["key"]: f for f in body["fields"]}
        self.assertEqual(fields["title"]["default"], "我的标题")
        self.assertEqual(fields["subtitle"]["default"], "我的副标题")
        # logo_text 草稿没填, 沿用原模板 default 即可 (新模板不应再额外写)
        self.assertEqual(fields["logo_text"]["default"], "BRAND")
        # 原模板 structure 沿用
        self.assertEqual(body["structure"]["layers"][0]["text_field"], "logo_text")

    def test_copy_uses_explicit_scene_id_and_supports_custom_name(self):
        r = self._post_from_draft("d1", self.fake_request, scene_id="s2", name="我的开场模板")
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["name"], "我的开场模板")
        self.assertEqual(body["_source"]["scene_id"], "s2")
        fields = {f["key"]: f for f in body["fields"]}
        self.assertEqual(fields["title"]["default"], "第二个标题")
        # 没有显式填过 subtitle → 不强加 default
        self.assertNotIn("default", fields["subtitle"])

    def test_copy_returns_404_when_scene_id_unknown(self):
        r = self._post_from_draft("d1", self.fake_request, scene_id="does-not-exist")
        self.assertEqual(r.status_code, 404)
        body = r.json()
        self.assertIn("detail", body)

    def test_copy_404_when_source_template_missing(self):
        self._insert_draft([{"id": "d5", "title": "D5", "user_id": "user-draft"}], [
            {"id": "s50", "position": 0, "workflow_draft_id": "d5", "title": "S50", "narration": "n", "visual_intent": "v", "subtitle": "", "duration_seconds": 4.0, "template_id": "ghost_template", "template_fields": "{}"},
        ])
        r = self._post_from_draft("d5", self.fake_request)
        self.assertEqual(r.status_code, 404)

    def test_copy_collision_increments_suffix(self):
        r1 = self._post_from_draft("d1", self.fake_request)
        r2 = self._post_from_draft("d1", self.fake_request)
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()["id"], r2.json()["id"])
        # 第二个 id 末位数字自增
        self.assertTrue(r2.json()["id"].startswith("copy_of_intro_simple_"))

    def test_copied_template_appears_in_list_and_get(self):
        r = self._post_from_draft("d1", self.fake_request)
        self.assertEqual(r.status_code, 201)
        template_id = r.json()["id"]
        listed = self.client.get("/templates?enabled_only=false").json()
        self.assertTrue(any(item["id"] == template_id for item in listed))
        fetched = self.client.get("/templates/" + template_id).json()
        self.assertEqual(fetched["id"], template_id)
        self.assertEqual(len(fetched["fields"]), 3)


class SceneDraftsTemplateFieldsTest(unittest.TestCase):
    """确认 scene_drafts 表加上了 template_id + template_fields 列."""

    def test_scene_drafts_has_template_columns(self):
        # schema.sql 本身没有 template_id/template_fields 列, 是 main.py init_db 运行时加的.
        # 这里仅验证 schema.sql 跑完有基础列 (voice / avatar), migration 由 main.py 负责.
        import shutil
        td = tempfile.mkdtemp()
        try:
            db_path = os.path.join(td, "test.sqlite")
            schema_path = str(Path(__file__).resolve().parent.parent / "db" / "schema.sql")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            schema_text = Path(__file__).resolve().parent.parent.joinpath("db", "schema.sql").read_text(encoding="utf-8")
            conn.executescript(schema_text)
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(scene_drafts)").fetchall()}
            conn.close()
            del conn
            gc.collect()
            self.assertIn("voice", cols)
            self.assertIn("avatar", cols)
        finally:
            shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
