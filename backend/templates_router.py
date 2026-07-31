# P7C-B: 本地视频模板 CRUD + 字段验证.
# 5-10 套内置模板, 支持用户自定义; scene_drafts 通过 template_id 引用.
# 渲染由 Remotion 负责 (后续 step), 本 router 只做字段校验 + 结构输出.
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from providers.template_renderer import render_template

DATA_DIR = Path(__file__).parent / "data"
TEMPLATES_FILE = DATA_DIR / "templates.json"


def now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def load_builtin_templates() -> list[dict]:
    if not TEMPLATES_FILE.exists():
        return []
    with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _template_payload(row, *, include_config: bool = True) -> dict:
    base = dict(row)
    payload = {
        "id": base["id"],
        "name": base["name"],
        "category": base["category"],
        "description": base["description"],
        "builtin": bool(base["builtin"]),
        "enabled": bool(base["enabled"]),
        "created_at": base["created_at"],
    }
    if include_config:
        config = json.loads(base["config_json"] or "{}")
        payload["fields"] = config.get("fields", [])
        payload["structure"] = config.get("structure", {})
    return payload


def _validate_field_value(field_def: dict, value) -> tuple[bool, str | None]:
    """校验单个字段值; 返回 (ok, error_message)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        if field_def.get("required"):
            return False, f"{field_def['key']} is required"
        return True, None
    ftype = field_def.get("type", "text")
    if ftype == "text":
        s = str(value)
        max_len = field_def.get("max_length")
        if max_len and len(s) > max_len:
            return False, f"{field_def['key']} exceeds max_length {max_len} (got {len(s)})"
    return True, None


def _merge_fields(template: dict, user_fields: dict) -> tuple[dict, list[str]]:
    """合并用户填的字段 + 默认值, 返回 (merged, errors)."""
    merged = {}
    errors = []
    field_defs = {f["key"]: f for f in template.get("fields", [])}
    for key, fdef in field_defs.items():
        if key in user_fields and user_fields[key] not in (None, ""):
            merged[key] = user_fields[key]
        elif "default" in fdef:
            merged[key] = fdef["default"]
        elif fdef.get("required"):
            errors.append(f"{key} is required")
    for key in user_fields:
        if key not in field_defs:
            errors.append(f"unknown field: {key}")
    return merged, errors


def _validate_all(template: dict, user_fields: dict) -> tuple[dict, list[str]]:
    """完整校验: 必填 + 长度 + 类型. 返回 (merged, errors)."""
    merged, errors = _merge_fields(template, user_fields)
    field_defs = {f["key"]: f for f in template.get("fields", [])}
    for key, value in merged.items():
        if key in field_defs:
            ok, err = _validate_field_value(field_defs[key], value)
            if not ok:
                errors.append(err)
    return merged, errors


def seed_templates(connection) -> int:
    """启动时把 data/templates.json 5 套导入 templates 表. 已有则跳过. 返回新插入数."""
    builtin = load_builtin_templates()
    if not builtin:
        return 0
    now = now_epoch()
    inserted = 0
    for t in builtin:
        cur = connection.execute("SELECT id FROM templates WHERE id=?", (t["id"],))
        if cur.fetchone() is not None:
            continue
        config = {"fields": t.get("fields", []), "structure": t.get("structure", {})}
        connection.execute(
            "INSERT INTO templates (id, name, category, description, enabled, builtin, config_json, created_at) "
            "VALUES (?, ?, ?, ?, 1, 1, ?, ?)",
            (t["id"], t["name"], t["category"], t.get("description", ""), json.dumps(config, ensure_ascii=False), now),
        )
        inserted += 1
    if inserted:
        connection.commit()
    return inserted


class TemplateCreateBody(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=32)
    description: str = Field(default="", max_length=500)
    config: dict


class TemplatePreviewBody(BaseModel):
    fields: dict = Field(default_factory=dict)
    duration_seconds: float = Field(default=3.0, ge=0.5, le=30.0)


def create_router(get_db):
    router = APIRouter(prefix="/templates", tags=["templates"])

    @router.get("")
    def list_templates(category: str | None = None, enabled_only: bool = True, include_config: bool = False):
        connection = get_db()
        try:
            seed_templates(connection)
            clauses = []
            params = []
            if category:
                clauses.append("category=?")
                params.append(category)
            if enabled_only:
                clauses.append("enabled=1")
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = connection.execute(
                f"SELECT * FROM templates{where} ORDER BY category, name", params
            ).fetchall()
            return [_template_payload(row, include_config=include_config) for row in rows]
        finally:
            connection.close()

    @router.get("/categories")
    def list_categories():
        connection = get_db()
        try:
            seed_templates(connection)
            rows = connection.execute(
                "SELECT category, COUNT(*) AS count FROM templates WHERE enabled=1 GROUP BY category ORDER BY category"
            ).fetchall()
            return [{"category": r["category"], "count": r["count"]} for r in rows]
        finally:
            connection.close()

    @router.get("/{template_id}")
    def get_template(template_id: str):
        connection = get_db()
        try:
            seed_templates(connection)
            row = connection.execute(
                "SELECT * FROM templates WHERE id=?", (template_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Template not found")
            return _template_payload(row, include_config=True)
        finally:
            connection.close()

    @router.post("/{template_id}/preview")
    def preview_template(template_id: str, body: TemplatePreviewBody):
        """Build the resolved template plan used by Remotion without starting a render job."""
        connection = get_db()
        try:
            seed_templates(connection)
            row = connection.execute(
                "SELECT * FROM templates WHERE id=? AND enabled=1", (template_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Template not found")
            template = _template_payload(row, include_config=True)
            merged_fields, errors = _validate_all(template, body.fields)
            if errors:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error_code": "TEMPLATE_PREVIEW_INVALID",
                        "message": "Template preview validation failed",
                        "hint": "Fill every required template field before previewing.",
                        "details": {"errors": errors},
                    },
                )
            result = render_template(
                template,
                merged_fields,
                mode="mock",
                duration_override=body.duration_seconds,
            )
            return {
                **result,
                "preview": True,
                "merged_fields": merged_fields,
            }
        finally:
            connection.close()

    @router.post("/{template_id}/validate")
    def validate_fields(template_id: str, payload: dict):
        """校验用户填的字段, 返回合并后的完整字段 + 错误列表. 不写库."""
        connection = get_db()
        try:
            seed_templates(connection)
            row = connection.execute(
                "SELECT * FROM templates WHERE id=?", (template_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Template not found")
            template = _template_payload(row, include_config=True)
            user_fields = payload.get("fields", {}) if isinstance(payload, dict) else {}
            merged, errors = _validate_all(template, user_fields)
            return {
                "template_id": template_id,
                "valid": len(errors) == 0,
                "errors": errors,
                "merged_fields": merged,
            }
        finally:
            connection.close()

    @router.post("")
    def create_template(body: TemplateCreateBody):
        connection = get_db()
        try:
            cur = connection.execute("SELECT id FROM templates WHERE id=?", (body.id,))
            if cur.fetchone() is not None:
                raise HTTPException(status_code=409, detail="Template id already exists")
            config = body.config or {}
            if "fields" not in config or "structure" not in config:
                raise HTTPException(status_code=422, detail="config must have 'fields' and 'structure'")
            connection.execute(
                "INSERT INTO templates (id, name, category, description, enabled, builtin, config_json, created_at) "
                "VALUES (?, ?, ?, ?, 1, 0, ?, ?)",
                (body.id, body.name, body.category, body.description, json.dumps(config, ensure_ascii=False), now_epoch()),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM templates WHERE id=?", (body.id,)).fetchone()
            return _template_payload(row, include_config=True)
        finally:
            connection.close()

    @router.post("/from-draft/{draft_id}", status_code=201)
    def copy_draft_to_template(
        draft_id: str,
        request: Request,
        scene_id: str | None = None,
        name: str | None = None,
    ):
        # P2 端点: scene_id/name 走 query 字符串, FastAPI 不会自动从 body 读 prm; 之所以保留 body 仅方便未来扩展. 现实调用走 query.
        """P2: 把草稿中已套模板的 scene 复制为新模板.

        来源: workflow_drafts -> scene_drafts.template_id + template_fields.
        行为:
        - 必登录 (401 当无 Bearer); 草稿不属于当前 user 返 404 (静默);
        - 选 scene 规则: 显式 ?scene_id > 否则取草稿首个 template_id 非空的 scene;
        - source 模板 (template_id) 缺失返 404; scene 无 template_id 返 409;
        - 新模板 id = "copy_of_<src>" + 可选 "_2" "_3" .. 自动避重; builtin=False; enabled=1.
        - 字段定义: 沿用 source 模板; 草稿中显式填过的非空字段写入 default, 跳过原模板已有的 default.
        - 返回: include_config=True 的 template payload, 多加 _source 元数据.
        """
        from auth_router import get_user_id_from_request as _uid
        user_id = _uid(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        connection = get_db()
        try:
            seed_templates(connection)
            draft = connection.execute(
                "SELECT id, user_id FROM workflow_drafts WHERE id=?",
                (draft_id,),
            ).fetchone()
            if draft is None or draft["user_id"] != user_id:
                raise HTTPException(status_code=404, detail="Workflow draft not found")
            if scene_id:
                scene = connection.execute(
                    "SELECT id, template_id, template_fields FROM scene_drafts WHERE id=? AND workflow_draft_id=?",
                    (scene_id, draft_id),
                ).fetchone()
                if scene is None:
                    raise HTTPException(status_code=404, detail="Scene draft not found")
            else:
                scene = connection.execute(
                    "SELECT id, template_id, template_fields FROM scene_drafts WHERE workflow_draft_id=? AND template_id IS NOT NULL ORDER BY position LIMIT 1",
                    (draft_id,),
                ).fetchone()
            if scene is None or not scene["template_id"]:
                raise HTTPException(
                    status_code=409,
                    detail="Draft has no scene with a template id; please select a template for one of its scenes before copying.",
                )
            source_id = scene["template_id"]
            source_row = connection.execute(
                "SELECT * FROM templates WHERE id=?", (source_id,)
            ).fetchone()
            if source_row is None:
                raise HTTPException(status_code=404, detail=f"Source template {source_id!r} not found")
            source_payload = _template_payload(source_row, include_config=True)
            raw_fields = scene["template_fields"]
            user_values = {}
            if raw_fields:
                try:
                    user_values = json.loads(raw_fields) or {}
                except Exception:
                    user_values = {}
            new_fields = []
            for fdef in source_payload.get("fields", []):
                entry = dict(fdef)
                key = entry["key"]
                user_val = user_values.get(key)
                has_user_value = user_val not in (None, "")
                source_default = entry.get("default")
                # 仅在草稿中显式填过且原模板没有 / 与原 default 不同时, 才把用户值固化为 default
                if has_user_value and (source_default is None or str(source_default) != str(user_val)):
                    entry["default"] = user_val
                # 原模板 default 是空字符串时, 视为"未设置", 移除避免把空 default 暴露给新模板
                if "default" in entry and (entry["default"] is None or str(entry["default"]) == ""):
                    entry.pop("default")
                new_fields.append(entry)
            new_config = {
                "fields": new_fields,
                "structure": source_payload.get("structure", {}),
            }
            base_id = "copy_of_" + source_id
            new_id = base_id
            suffix = 1
            while connection.execute("SELECT id FROM templates WHERE id=?", (new_id,)).fetchone() is not None:
                suffix += 1
                new_id = base_id + "_" + str(suffix)
            new_name = name or ("Copy of " + source_payload["name"])
            connection.execute(
                "INSERT INTO templates (id, name, category, description, enabled, builtin, config_json, created_at) "
                "VALUES (?, ?, ?, ?, 1, 0, ?, ?)",
                (
                    new_id,
                    new_name,
                    source_payload["category"],
                    source_payload.get("description", ""),
                    json.dumps(new_config, ensure_ascii=False),
                    now_epoch(),
                ),
            )
            connection.commit()
            new_row = connection.execute("SELECT * FROM templates WHERE id=?", (new_id,)).fetchone()
            payload = _template_payload(new_row, include_config=True)
            payload["_source"] = {
                "draft_id": draft_id,
                "scene_id": scene["id"],
                "template_id": source_id,
            }
            return payload
        finally:
            connection.close()

    @router.delete("/{template_id}")
    def delete_template(template_id: str):
        connection = get_db()
        try:
            seed_templates(connection)
            row = connection.execute("SELECT builtin FROM templates WHERE id=?", (template_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Template not found")
            if bool(row["builtin"]):
                raise HTTPException(status_code=422, detail="Built-in templates cannot be deleted")
            connection.execute("DELETE FROM templates WHERE id=?", (template_id,))
            connection.commit()
            return {"deleted": True, "id": template_id}
        finally:
            connection.close()

    return router
