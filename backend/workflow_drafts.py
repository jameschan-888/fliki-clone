import json
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from providers.tts import DEFAULT_VOICE
from templates_router import _template_payload, _validate_all, seed_templates

CameraMotion = Literal["none", "zoom-in", "zoom-out", "pan-left", "pan-right", "pan-up", "pan-down"]
VideoAspect = Literal["16:9", "9:16", "1:1"]
VideoTransitionMode = Literal["none", "fade", "cut", "slide-left", "slide-right", "slide-up", "slide-down"]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def split_script(source_script: str, minimum_scenes: int = 3, maximum_scenes: int = 10):
    normalized = re.sub(r"\s+", " ", source_script.strip())
    sentences = [part.strip() for part in re.split(r"(?<=[。！？!?；;])", normalized) if part.strip()]
    if not sentences:
        sentences = [normalized]
    target_count = min(maximum_scenes, max(minimum_scenes, math.ceil(len(normalized) / 150)))
    target_count = min(target_count, max(1, len(sentences)))
    groups = [[] for _ in range(target_count)]
    for index, sentence in enumerate(sentences):
        groups[min(target_count - 1, index * target_count // len(sentences))].append(sentence)
    scenes = []
    for group in groups:
        narration = "".join(group).strip()
        if not narration:
            continue
        visual_keywords = re.sub(r"[，。！？!?；;：:]", " ", narration).split()
        scenes.append({
            "id": uuid.uuid4().hex,
            "position": len(scenes),
            "title": f"场景 {len(scenes) + 1}",
            "narration": narration,
            "visual_intent": "、".join(visual_keywords[:6]) or narration[:30],
            "subtitle": narration,
            # P0-4: subtitle_display (屏幕显示) + subtitle_spoken (TTS) 默认都跟 narration
            "subtitle_display": narration,
            "subtitle_spoken": narration,
            # P0-5: 默认 16:9 (1280x720)
            "media_width": 1280,
            "media_height": 720,
            # P1-7: VideoAspect / VideoTransitionMode (Pixelle 审计)
            "video_aspect": "16:9",
            "video_transition_mode": "fade",
            "duration_seconds": max(2.0, round(len(narration) / 4.2, 1)),
        })
    return scenes


class DraftCreateBody(BaseModel):
    source_script: str = Field(min_length=1, max_length=20000)
    title: str | None = Field(default=None, max_length=200)
    language: str = Field(default="zh-CN", min_length=2, max_length=32)


class ScenePatchBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    narration: str | None = Field(default=None, min_length=1, max_length=5000)
    visual_intent: str | None = Field(default=None, min_length=1, max_length=2000)
    subtitle: str | None = Field(default=None, min_length=1, max_length=5000)
    duration_seconds: float | None = Field(default=None, ge=0.5, le=3600)
    voice: str | None = Field(default=None, min_length=1, max_length=120)
    avatar: str | None = Field(default=None, max_length=120)
    avatar_layout: dict | None = None
    template_id: str | None = Field(default=None, max_length=64)
    template_fields: dict | None = None
    stock_url: str | None = Field(default=None, max_length=500)
    camera_motion: CameraMotion | None = None
    # P0-5: media 宽高 (默认 None = 沿用 1280x720)
    media_width: int | None = Field(default=None, ge=320, le=3840)
    media_height: int | None = Field(default=None, ge=240, le=2160)
    # P0-4: subtitle 双轨 (display=屏幕, spoken=TTS)
    subtitle_display: str | None = Field(default=None, max_length=5000)
    subtitle_spoken: str | None = Field(default=None, max_length=5000)
    # P1-7: VideoAspect / VideoTransitionMode (Pixelle 审计)
    video_aspect: VideoAspect | None = None
    video_transition_mode: VideoTransitionMode | None = None

    @model_validator(mode="after")
    def require_change(self):
        # avatar_layout: dict | None = None 默认 None 不进 model_fields_set；用 model_dump(exclude_unset=True) 更稳
        if not self.model_dump(exclude_unset=True):
            raise ValueError("At least one scene field is required")
        return self


class SceneCreateBody(BaseModel):
    title: str = Field(default="新场景", min_length=1, max_length=200)
    narration: str = Field(min_length=1, max_length=5000)
    visual_intent: str = Field(min_length=1, max_length=2000)
    subtitle: str | None = Field(default=None, max_length=5000)
    duration_seconds: float | None = Field(default=None, ge=0.5, le=3600)
    voice: str | None = Field(default=None, min_length=1, max_length=120)
    avatar: str | None = Field(default=None, max_length=120)
    position: int | None = Field(default=None, ge=0)
    template_id: str | None = Field(default=None, max_length=64)
    template_fields: dict | None = None
    stock_url: str | None = Field(default=None, max_length=500)
    camera_motion: CameraMotion = "zoom-in"
    # P0-5: media 宽高 (默认 1280x720)
    media_width: int | None = Field(default=None, ge=320, le=3840)
    media_height: int | None = Field(default=None, ge=240, le=2160)
    # P0-4: subtitle 双轨 (display 默认 = subtitle; spoken 默认 = narration)
    subtitle_display: str | None = Field(default=None, max_length=5000)
    subtitle_spoken: str | None = Field(default=None, max_length=5000)
    # P1-7: VideoAspect / VideoTransitionMode (Pixelle 审计)
    video_aspect: VideoAspect = "16:9"
    video_transition_mode: VideoTransitionMode = "fade"


class ReorderBody(BaseModel):
    scene_ids: list[str] = Field(min_length=1, max_length=100)


def voice_matches_language(voice: str, language: str):
    match = re.match(r"^([a-z]{2,3})-([A-Za-z]{2,4})(?:-|$)", voice)
    if not match:
        return True
    selected_locale = f"{match.group(1)}-{match.group(2)}".lower()
    requested = language.strip().lower()
    if "-" not in requested:
        return selected_locale.split("-", 1)[0] == requested
    return selected_locale == requested


def scene_from_row(row):
    available = set(row.keys())
    names = ("id", "position", "title", "narration", "visual_intent", "subtitle", "duration_seconds", "voice", "avatar", "template_id", "stock_url", "media_width", "media_height", "subtitle_display", "subtitle_spoken", "video_aspect", "video_transition_mode")
    out = {name: row[name] for name in names if name in available}
    out["camera_motion"] = row["camera_motion"] if "camera_motion" in available and row["camera_motion"] else "zoom-in"
    # P0-5: media 宽高 (默认 1280x720)
    out["media_width"] = row["media_width"] if "media_width" in available and row["media_width"] else 1280
    out["media_height"] = row["media_height"] if "media_height" in available and row["media_height"] else 720
    # P0-4: subtitle 双轨 (默认回落到 subtitle)
    out["subtitle_display"] = row["subtitle_display"] if "subtitle_display" in available and row["subtitle_display"] else out.get("subtitle", "")
    out["subtitle_spoken"] = row["subtitle_spoken"] if "subtitle_spoken" in available and row["subtitle_spoken"] else out.get("narration", "")
    # P1-7: VideoAspect / VideoTransitionMode 默认值 (避免前端 undefined)
    out["video_aspect"] = row["video_aspect"] if "video_aspect" in available and row["video_aspect"] else "16:9"
    out["video_transition_mode"] = row["video_transition_mode"] if "video_transition_mode" in available and row["video_transition_mode"] else "fade"
    layout = row["avatar_layout"] if "avatar_layout" in available else None
    if layout:
        try: out["avatar_layout"] = json.loads(layout)
        except Exception: out["avatar_layout"] = None
    tf = row["template_fields"] if "template_fields" in available else None
    if tf:
        try: out["template_fields"] = json.loads(tf)
        except Exception: out["template_fields"] = None
    return out


def draft_payload(connection, draft_id: str):
    draft = connection.execute("SELECT * FROM workflow_drafts WHERE id=?", (draft_id,)).fetchone()
    if draft is None:
        raise HTTPException(status_code=404, detail="Workflow draft not found")
    scenes = connection.execute("SELECT * FROM scene_drafts WHERE workflow_draft_id=? ORDER BY position", (draft_id,)).fetchall()
    return {
        "id": draft["id"], "title": draft["title"], "source_script": draft["source_script"],
        "language": draft["language"], "status": draft["status"], "version": draft["version"],
        "duration_seconds": round(sum(scene["duration_seconds"] for scene in scenes), 1),
        "scenes": [scene_from_row(scene) for scene in scenes], "created_at": draft["created_at"],
        "updated_at": draft["updated_at"], "confirmed_at": draft["confirmed_at"],
    }


def _validate_template_fields(connection, template_id, user_fields):
    """校验 scene 引用 template_id 是否存在 + fields 是否合法. 返回 merged dict 或抛 HTTPException."""
    if not template_id:
        return None
    seed_templates(connection)
    row = connection.execute("SELECT * FROM templates WHERE id=?", (template_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail=f"Template {template_id!r} not found")
    template = _template_payload(row, include_config=True)
    merged, errors = _validate_all(template, user_fields or {})
    if errors:
        raise HTTPException(status_code=422, detail={"template_id": template_id, "errors": errors})
    return merged


def require_editable(connection, draft_id: str):
    row = connection.execute("SELECT status FROM workflow_drafts WHERE id=?", (draft_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow draft not found")
    if row["status"] != "draft":
        raise HTTPException(status_code=409, detail="Confirmed drafts are immutable")


def record_revision(connection, draft_id: str):
    payload = draft_payload(connection, draft_id)
    version = payload["version"] + 1
    now = utc_now()
    connection.execute("INSERT INTO draft_revisions (id, workflow_draft_id, version, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?)", (uuid.uuid4().hex, draft_id, version, json.dumps(payload, ensure_ascii=False), now))
    connection.execute("UPDATE workflow_drafts SET version=?, updated_at=? WHERE id=?", (version, now, draft_id))


def create_router(get_db):
    from auth_router import get_user_id_from_request as _uid_of_request
    router = APIRouter(prefix="/workflow-drafts", tags=["workflow-drafts"])

    def _require_draft_owner(connection, draft_id: str, request):
        """强制 user_id 与 draft 的 user_id 一致; 不一致返回 404 (不暴露存在性).
        - 无 token: 401 Authentication required
        - draft 不存在或不属于当前 user: 404 (跨用户静默)
        """
        user_id = _uid_of_request(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        row = connection.execute(
            "SELECT user_id FROM workflow_drafts WHERE id=?", (draft_id,)
        ).fetchone()
        if row is None or row["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Workflow draft not found")
        return user_id


    @router.post("")
    def create_draft(body: DraftCreateBody, request: Request = None):
        from auth_router import get_user_id_from_request as _uid
        user_id = _uid(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        with get_db() as connection:
            draft_id, now = uuid.uuid4().hex, utc_now()
            scenes = split_script(body.source_script)
            connection.execute("INSERT INTO workflow_drafts (id, title, source_script, language, status, version, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, 'draft', 1, ?, ?, ?)", (draft_id, body.title or "未命名视频", body.source_script.strip(), body.language, now, now, user_id))
            for scene in scenes:
                connection.execute("INSERT INTO scene_drafts (id, workflow_draft_id, position, title, narration, visual_intent, subtitle, duration_seconds, voice, avatar, video_aspect, video_transition_mode, media_width, media_height, subtitle_display, subtitle_spoken, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (scene["id"], draft_id, scene["position"], scene["title"], scene["narration"], scene["visual_intent"], scene["subtitle"], scene["duration_seconds"], scene.get("voice") or DEFAULT_VOICE, scene.get("avatar"), scene.get("video_aspect") or "16:9", scene.get("video_transition_mode") or "fade", scene.get("media_width") or 1280, scene.get("media_height") or 720, scene.get("subtitle_display") or scene.get("subtitle") or scene["subtitle"], scene.get("subtitle_spoken") or scene.get("narration") or scene["narration"], now, now))
            connection.commit()
            return draft_payload(connection, draft_id)
    # rev24 stage C #8: 按 user_id 过滤的 drafts 列表端点; 匿名 token 返回空数组
    @router.get("")
    def list_drafts(request: Request = None, page: int = 0, limit: int = 50, status: str | None = None):
        """列出当前 user 的所有 drafts (按 updated_at DESC, 默认 50, 上限 200).
        - 无 token: 返回空数组 / 空 wrapper (不暴露他人草稿)
        - 有 token: 按 user_id 严格过滤
        - 可选 status 过滤 (draft / confirmed / archived)
        - page=0 (默认) 返 list 形态 (向后兼容); page>=1 返 wrapper {items, total, page, limit, has_more}
        """
        from auth_router import get_user_id_from_request as _uid
        user_id = _uid(request)
        if not user_id:
            return [] if page <= 0 else {"items": [], "total": 0, "page": page, "limit": limit, "has_more": False}
        with get_db() as connection:
            clauses = ["user_id = ?"]
            params: list = [user_id]
            if status:
                clauses.append("status = ?")
                params.append(status)
            where = " WHERE " + " AND ".join(clauses)
            capped_limit = max(1, min(limit, 200))
            if page <= 0:
                # 旧行为: 返 list
                rows = connection.execute(
                    "SELECT id FROM workflow_drafts" + where + " ORDER BY updated_at DESC LIMIT ?",
                    params + [capped_limit],
                ).fetchall()
                return [draft_payload(connection, row["id"]) for row in rows]
            # 新行为: 分页 wrapper
            total = int(connection.execute(
                "SELECT count(*) FROM workflow_drafts" + where, params
            ).fetchone()[0] or 0)
            offset = (page - 1) * capped_limit
            rows = connection.execute(
                "SELECT id FROM workflow_drafts" + where + " ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                params + [capped_limit, offset],
            ).fetchall()
            items = [draft_payload(connection, row["id"]) for row in rows]
            return {
                "items": items,
                "total": total,
                "page": page,
                "limit": capped_limit,
                "has_more": offset + len(items) < total,
            }
    @router.get("/{draft_id}")
    def get_draft(draft_id: str, request: Request = None):
        with get_db() as connection:
            _require_draft_owner(connection, draft_id, request)
            return draft_payload(connection, draft_id)
    @router.patch("/{draft_id}/scenes/{scene_id}")
    def update_scene(draft_id: str, scene_id: str, body: ScenePatchBody, request: Request = None):
        with get_db() as connection:
            _require_draft_owner(connection, draft_id, request)
            require_editable(connection, draft_id)
            if connection.execute("SELECT id FROM scene_drafts WHERE id=? AND workflow_draft_id=?", (scene_id, draft_id)).fetchone() is None:
                raise HTTPException(status_code=404, detail="Scene draft not found")
            values = body.model_dump(exclude_unset=True)
            if "template_id" in values or "template_fields" in values:
                tid = values.get("template_id")
                tf = values.get("template_fields") or {}
                _validate_template_fields(connection, tid, tf)
            if "avatar_layout" in values and values["avatar_layout"] is not None:
                values["avatar_layout"] = json.dumps(values["avatar_layout"], ensure_ascii=False)
            if "template_fields" in values and values["template_fields"] is not None:
                values["template_fields"] = json.dumps(values["template_fields"], ensure_ascii=False)
            assignments = ", ".join(f"{name}=?" for name in values)
            connection.execute(f"UPDATE scene_drafts SET {assignments}, updated_at=? WHERE id=?", (*values.values(), utc_now(), scene_id))
            record_revision(connection, draft_id)
            connection.commit()
            return draft_payload(connection, draft_id)
    @router.post("/{draft_id}/scenes")
    def add_scene(draft_id: str, body: SceneCreateBody, request: Request = None):
        with get_db() as connection:
            _require_draft_owner(connection, draft_id, request)
            require_editable(connection, draft_id)
            if body.template_id:
                _validate_template_fields(connection, body.template_id, body.template_fields or {})
            count = connection.execute("SELECT COUNT(*) FROM scene_drafts WHERE workflow_draft_id=?", (draft_id,)).fetchone()[0]
            position = min(body.position if body.position is not None else count, count)
            connection.execute("UPDATE scene_drafts SET position=position+1 WHERE workflow_draft_id=? AND position>=?", (draft_id, position))
            now, narration = utc_now(), body.narration.strip()
            tf_json = json.dumps(body.template_fields, ensure_ascii=False) if body.template_fields else None
            connection.execute("INSERT INTO scene_drafts (id, workflow_draft_id, position, title, narration, visual_intent, subtitle, duration_seconds, voice, avatar, template_id, template_fields, stock_url, camera_motion, video_aspect, video_transition_mode, media_width, media_height, subtitle_display, subtitle_spoken, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (uuid.uuid4().hex, draft_id, position, body.title, narration, body.visual_intent, body.subtitle or narration, body.duration_seconds or max(2.0, round(len(narration) / 4.2, 1)), body.voice or DEFAULT_VOICE, body.avatar, body.template_id, tf_json, body.stock_url, body.camera_motion, body.video_aspect, body.video_transition_mode, body.media_width or 1280, body.media_height or 720, body.subtitle_display or body.subtitle or narration, body.subtitle_spoken or narration, now, now))
            record_revision(connection, draft_id)
            connection.commit()
            return draft_payload(connection, draft_id)
    @router.delete("/{draft_id}/scenes/{scene_id}")
    def delete_scene(draft_id: str, scene_id: str, request: Request = None):
        with get_db() as connection:
            _require_draft_owner(connection, draft_id, request)
            require_editable(connection, draft_id)
            if connection.execute("SELECT COUNT(*) FROM scene_drafts WHERE workflow_draft_id=?", (draft_id,)).fetchone()[0] <= 1:
                raise HTTPException(status_code=409, detail="A draft must contain at least one scene")
            scene = connection.execute("SELECT position FROM scene_drafts WHERE id=? AND workflow_draft_id=?", (scene_id, draft_id)).fetchone()
            if scene is None:
                raise HTTPException(status_code=404, detail="Scene draft not found")
            connection.execute("DELETE FROM scene_drafts WHERE id=?", (scene_id,))
            connection.execute("UPDATE scene_drafts SET position=position-1 WHERE workflow_draft_id=? AND position>?", (draft_id, scene["position"]))
            record_revision(connection, draft_id)
            connection.commit()
            return draft_payload(connection, draft_id)
    @router.post("/{draft_id}/reorder")
    def reorder_scenes(draft_id: str, body: ReorderBody, request: Request = None):
        with get_db() as connection:
            _require_draft_owner(connection, draft_id, request)
            require_editable(connection, draft_id)
            current_ids = [row["id"] for row in connection.execute("SELECT id FROM scene_drafts WHERE workflow_draft_id=? ORDER BY position", (draft_id,)).fetchall()]
            if len(body.scene_ids) != len(set(body.scene_ids)) or set(body.scene_ids) != set(current_ids):
                raise HTTPException(status_code=422, detail="scene_ids must contain every scene exactly once")
            for temporary_position, scene_id in enumerate(body.scene_ids):
                connection.execute("UPDATE scene_drafts SET position=? WHERE id=?", (-temporary_position - 1, scene_id))
            for position, scene_id in enumerate(body.scene_ids):
                connection.execute("UPDATE scene_drafts SET position=?, updated_at=? WHERE id=?", (position, utc_now(), scene_id))
            record_revision(connection, draft_id)
            connection.commit()
            return draft_payload(connection, draft_id)
    @router.delete("/{draft_id}")
    def delete_draft(draft_id: str, request: Request = None):
        """删除草稿. 存在关联 workflow_runs 时拒绝 (409), 防误删渲染产物;
        scene_drafts / draft_revisions 由 ON DELETE CASCADE 清理."""
        with get_db() as connection:
            _require_draft_owner(connection, draft_id, request)
            run_count = connection.execute(
                "SELECT COUNT(*) FROM workflow_runs WHERE workflow_draft_id=?", (draft_id,)
            ).fetchone()[0]
            if run_count:
                raise HTTPException(status_code=409, detail="Cannot delete draft with existing workflow runs")
            connection.execute("DELETE FROM workflow_drafts WHERE id=?", (draft_id,))
            connection.commit()
            return {"deleted": True, "id": draft_id}

    @router.post("/{draft_id}/confirm")
    def confirm_draft(draft_id: str, request: Request = None):
        with get_db() as connection:
            _require_draft_owner(connection, draft_id, request)
            payload = draft_payload(connection, draft_id)
            if payload["status"] == "confirmed":
                return payload
            if not payload["scenes"]:
                raise HTTPException(status_code=409, detail="Cannot confirm an empty draft")
            incompatible = [scene for scene in payload["scenes"] if not voice_matches_language(scene["voice"], payload["language"])]
            if incompatible:
                labels = ", ".join(f"场景 {scene['position'] + 1}: {scene['voice']}" for scene in incompatible)
                raise HTTPException(status_code=422, detail=f"配音语言与草稿语言 {payload['language']} 不一致：{labels}")
            # Mock provider gate: confirm 闸门检查每类 default provider 是否 is_mock。
            try:
                from errors import LingjianError, MOCK_PROVIDER_BLOCKS_RELEASE  # noqa: PLC0415
            except Exception:
                LingjianError = None  # type: ignore[assignment]
                MOCK_PROVIDER_BLOCKS_RELEASE = None  # type: ignore[assignment]
            if LingjianError is not None:
                mock_providers: list[dict] = []
                for category in ("tts", "stock", "music", "avatar"):
                    row = connection.execute(
                        "SELECT name, config_json FROM provider_configs WHERE category=? AND is_default=1 ORDER BY priority LIMIT 1",
                        (category,),
                    ).fetchone()
                    if row is None:
                        continue
                    try:
                        cfg = json.loads(row["config_json"] or "{}")
                    except (TypeError, ValueError):
                        cfg = {}
                    if cfg.get("is_mock"):
                        mock_providers.append({"category": category, "name": row["name"]})
                if mock_providers:
                    labels = ", ".join(f"{item['category']}={item['name']}" for item in mock_providers)
                    raise LingjianError(
                        MOCK_PROVIDER_BLOCKS_RELEASE,
                        "Mock provider 不能进入 release 流程。",
                        "在 /provider-configs 中关闭 mock 或把 default 切到真实 provider；如需本地预览请用 preview 渲染。",
                        {"mock_providers": mock_providers},
                        status_code=409,
                    )
            confirmed_at = utc_now()
            connection.execute("UPDATE workflow_drafts SET status='confirmed', confirmed_snapshot_json=?, confirmed_at=?, updated_at=? WHERE id=? AND status='draft'", (json.dumps(payload, ensure_ascii=False), confirmed_at, confirmed_at, draft_id))
            connection.commit()
            return draft_payload(connection, draft_id)
    return router
