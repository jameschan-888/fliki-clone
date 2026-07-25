import json
import math
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from providers.tts import DEFAULT_VOICE


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
    out = {name: row[name] for name in ("id", "position", "title", "narration", "visual_intent", "subtitle", "duration_seconds", "voice", "avatar")}
    layout = row["avatar_layout"]
    if layout:
        try: out["avatar_layout"] = json.loads(layout)
        except Exception: out["avatar_layout"] = None
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
    router = APIRouter(prefix="/workflow-drafts", tags=["workflow-drafts"])

    @router.post("")
    def create_draft(body: DraftCreateBody):
        connection = get_db()
        draft_id, now = uuid.uuid4().hex, utc_now()
        scenes = split_script(body.source_script)
        try:
            connection.execute("INSERT INTO workflow_drafts (id, title, source_script, language, status, version, created_at, updated_at) VALUES (?, ?, ?, ?, 'draft', 1, ?, ?)", (draft_id, body.title or "未命名视频", body.source_script.strip(), body.language, now, now))
            for scene in scenes:
                connection.execute("INSERT INTO scene_drafts (id, workflow_draft_id, position, title, narration, visual_intent, subtitle, duration_seconds, voice, avatar, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (scene["id"], draft_id, scene["position"], scene["title"], scene["narration"], scene["visual_intent"], scene["subtitle"], scene["duration_seconds"], scene.get("voice") or DEFAULT_VOICE, scene.get("avatar"), now, now))
            connection.commit()
            return draft_payload(connection, draft_id)
        finally:
            connection.close()

    @router.get("/{draft_id}")
    def get_draft(draft_id: str):
        connection = get_db()
        try:
            return draft_payload(connection, draft_id)
        finally:
            connection.close()

    @router.patch("/{draft_id}/scenes/{scene_id}")
    def update_scene(draft_id: str, scene_id: str, body: ScenePatchBody):
        connection = get_db()
        try:
            require_editable(connection, draft_id)
            if connection.execute("SELECT id FROM scene_drafts WHERE id=? AND workflow_draft_id=?", (scene_id, draft_id)).fetchone() is None:
                raise HTTPException(status_code=404, detail="Scene draft not found")
            values = body.model_dump(exclude_unset=True)
            if "avatar_layout" in values and values["avatar_layout"] is not None:
                values["avatar_layout"] = json.dumps(values["avatar_layout"], ensure_ascii=False)
            assignments = ", ".join(f"{name}=?" for name in values)
            connection.execute(f"UPDATE scene_drafts SET {assignments}, updated_at=? WHERE id=?", (*values.values(), utc_now(), scene_id))
            record_revision(connection, draft_id)
            connection.commit()
            return draft_payload(connection, draft_id)
        finally:
            connection.close()

    @router.post("/{draft_id}/scenes")
    def add_scene(draft_id: str, body: SceneCreateBody):
        connection = get_db()
        try:
            require_editable(connection, draft_id)
            count = connection.execute("SELECT COUNT(*) FROM scene_drafts WHERE workflow_draft_id=?", (draft_id,)).fetchone()[0]
            position = min(body.position if body.position is not None else count, count)
            connection.execute("UPDATE scene_drafts SET position=position+1 WHERE workflow_draft_id=? AND position>=?", (draft_id, position))
            now, narration = utc_now(), body.narration.strip()
            connection.execute("INSERT INTO scene_drafts (id, workflow_draft_id, position, title, narration, visual_intent, subtitle, duration_seconds, voice, avatar, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (uuid.uuid4().hex, draft_id, position, body.title, narration, body.visual_intent, body.subtitle or narration, body.duration_seconds or max(2.0, round(len(narration) / 4.2, 1)), body.voice or DEFAULT_VOICE, body.avatar, now, now))
            record_revision(connection, draft_id)
            connection.commit()
            return draft_payload(connection, draft_id)
        finally:
            connection.close()

    @router.delete("/{draft_id}/scenes/{scene_id}")
    def delete_scene(draft_id: str, scene_id: str):
        connection = get_db()
        try:
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
        finally:
            connection.close()

    @router.post("/{draft_id}/reorder")
    def reorder_scenes(draft_id: str, body: ReorderBody):
        connection = get_db()
        try:
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
        finally:
            connection.close()

    @router.post("/{draft_id}/confirm")
    def confirm_draft(draft_id: str):
        connection = get_db()
        try:
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
        finally:
            connection.close()

    return router
