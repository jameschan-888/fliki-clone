"""4 大缺失工作流 (Blog/PPT/Record/Translate) 公共辅助.

- 复用 workflow_drafts.create_router 的 scene_drafts 表 + render 管线
- 4 个工作流提供不同的 source_to_scenes 函数
- MVP: 接收 body, 生成同 workflow_drafts 形态的 scenes
"""
import re, uuid


def _slug_scenes(scenes):
    """保证每个 scene 有 uuid + position + 默认字段."""
    out = []
    for scene in scenes:
        narration = (scene.get("narration") or "").strip()
        if not narration:
            continue
        vi = scene.get("visual_intent")
        if not vi:
            tokens = re.sub(r"[,!?;:、。 ]+", " ", narration).split()
            vi = "|".join(tokens[:6]) or narration[:30]
        out.append({
            "id": uuid.uuid4().hex,
            "position": len(out),
            "title": scene.get("title") or ("场景 " + str(len(out) + 1)),
            "narration": narration,
            "visual_intent": vi,
            "subtitle": scene.get("subtitle") or narration,
            "subtitle_display": scene.get("subtitle_display") or scene.get("subtitle") or narration,
            "subtitle_spoken": scene.get("subtitle_spoken") or narration,
            "media_width": scene.get("media_width") or 1280,
            "media_height": scene.get("media_height") or 720,
            "video_aspect": scene.get("video_aspect") or "16:9",
            "video_transition_mode": scene.get("video_transition_mode") or "fade",
            "duration_seconds": scene.get("duration_seconds") or max(2.0, round(len(narration) / 4.2, 1)),
        })
    return out


def insert_draft(connection, user_id, title, source_script, language, scenes):
    """插入 workflow_drafts + scene_drafts 两张表."""
    from datetime import datetime, timezone
    draft_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    connection.execute(
        "INSERT INTO workflow_drafts (id, title, source_script, language, status, version, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)",
        (draft_id, title or "未命名视频", (source_script or "").strip(), language, "draft", now, now, user_id),
    )
    for scene in scenes:
        connection.execute(
            "INSERT INTO scene_drafts (id, workflow_draft_id, position, title, narration, visual_intent, subtitle, duration_seconds, voice, avatar, video_aspect, video_transition_mode, media_width, media_height, subtitle_display, subtitle_spoken, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (scene["id"], draft_id, scene["position"], scene["title"], scene["narration"], scene["visual_intent"], scene["subtitle"], scene["duration_seconds"], scene.get("voice") or "zh-CN-XiaoxiaoNeural", scene.get("avatar"), scene.get("video_aspect") or "16:9", scene.get("video_transition_mode") or "fade", scene.get("media_width") or 1280, scene.get("media_height") or 720, scene.get("subtitle_display") or scene.get("subtitle") or scene["narration"], scene.get("subtitle_spoken") or scene["narration"], now, now),
        )
    connection.commit()
    return draft_id


def build_workflow_router(prefix, tag, source_to_scenes, get_db, max_source_length=50000, source_label="source"):
    """构造 4 大工作流的 router.
    - source_to_scenes: (body, language) -> ([scenes], source_script_str)
    """
    from fastapi import APIRouter, HTTPException, Request
    from workflow_drafts import draft_payload
    from auth_router import get_user_id_from_request as _uid

    router = APIRouter(prefix=prefix, tags=[tag])

    @router.post("")
    def create_from_source(body: dict, request: Request = None):
        user_id = _uid(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        title = (body.get("title") or "未命名视频")[:200]
        language = (body.get("language") or "zh-CN")[:32]
        try:
            result = source_to_scenes(body, language)
            if isinstance(result, tuple) and len(result) == 2:
                raw_scenes, source_script = result
            else:
                raw_scenes = result
                source_script = ""
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=422, detail="source_to_scenes 错误: " + str(exc)[:200])
        scenes = _slug_scenes(raw_scenes or [])
        if not scenes:
            raise HTTPException(status_code=422, detail=source_label + " 无法生成任何 scene")
        with get_db() as connection:
            draft_id = insert_draft(connection, user_id, title, source_script or "", language, scenes)
            return draft_payload(connection, draft_id)

    return router
