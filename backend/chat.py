"""Chat editor backend (P0-8 MVP).
- POST /chat/apply {draft_id, instruction} -> {applied: [changes]}
- Natural language -> batch scene patches
- MVP: keyword parsing for 6 commands (LLM upgrade in P1)
"""
import json
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Body
from workflow_drafts import draft_payload
from auth_router import get_user_id_from_request as _uid


def _ensure_owner(connection, draft_id, request):
    user_id = _uid(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    row = connection.execute("SELECT user_id FROM workflow_drafts WHERE id=?", (draft_id,)).fetchone()
    if row is None or row["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Workflow draft not found")
    return user_id


SUPPORTED_OPS = (
    "shorten_subtitles",
    "set_aspect",
    "shorten_duration",
    "set_voice",
    "adjust_visual",
)
SUPPORTED_ASPECTS = ("16:9", "9:16", "1:1")

def _llm_parse_instruction(instruction):
    """R28c-B: DeepSeek natural language intent parser.

    Returns (op, params) on confidence, else (None, None).
    Env CHAT_LLM_ENABLED=true required to enable (default off -> fallback to regex).
    """
    if not instruction or not str(instruction).strip():
        return (None, None)
    flag = (os.getenv("CHAT_LLM_ENABLED") or "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return (None, None)
    try:
        from providers.text.deepseek_text import DeepSeekTextProvider
        provider = DeepSeekTextProvider(model=os.getenv("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat"))
    except Exception:
        return (None, None)
    system = (
        "You are a Chinese video-edit instruction parser. Given user natural-language instruction, output STRICT JSON: {op, params, confidence}. ops: shorten_subtitles(limit int), set_aspect(aspect 16:9/9:16/1:1), shorten_duration(seconds float), set_voice(voice str), adjust_visual(keyword str). Unknown op=null+confidence<0.5. JSON only, no markdown, no explanation."
    )
    try:
        result = provider.generate(instruction, system=system, max_tokens=200, temperature=0.1)
    except Exception:
        return (None, None)
    raw = (result.get("content") or "").strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start < 0 or end <= start:
        return (None, None)
    try:
        data = json.loads(raw[start:end])
    except Exception:
        return (None, None)
    if not isinstance(data, dict):
        return (None, None)
    op = data.get("op")
    try:
        confidence = float(data.get("confidence") or 0)
    except Exception:
        confidence = 0.0
    if not op or op not in SUPPORTED_OPS or confidence < 0.5:
        return (None, None)
    params = data.get("params")
    if not isinstance(params, dict):
        return (None, None)
    if op == "shorten_subtitles":
        try:
            limit = int(params.get("limit"))
        except Exception:
            return (None, None)
        if limit <= 0 or limit > 500:
            return (None, None)
        return (op, {"limit": limit})
    if op == "set_aspect":
        aspect = params.get("aspect")
        if aspect not in SUPPORTED_ASPECTS:
            return (None, None)
        return (op, {"aspect": aspect})
    if op == "shorten_duration":
        try:
            seconds = float(params.get("seconds"))
        except Exception:
            return (None, None)
        if seconds <= 0 or seconds > 60:
            return (None, None)
        return (op, {"seconds": round(seconds, 2)})
    if op == "set_voice":
        voice = (params.get("voice") or "").strip()
        if not voice or len(voice) > 64:
            return (None, None)
        return (op, {"voice": voice})
    if op == "adjust_visual":
        keyword = (params.get("keyword") or "").strip()
        if not keyword or len(keyword) > 64:
            return (None, None)
        return (op, {"keyword": keyword})
    return (None, None)
def _parse_instruction(instruction):
    # R28c-B: LLM-first intent parsing with regex fallback.
    op, params = _llm_parse_instruction(instruction)
    if op is not None:
        return (op, params)
    text = (instruction or "").strip()
    if not text:
        return (None, None)
    text_lower = text.lower()
    m = re.search(r"(?:shorten|truncate)\s+subtitles?(?:\s+to)?\s+(\d+)\s*(?:chars?|chars|字)?", text_lower)
    if m:
        return ("shorten_subtitles", {"limit": int(m.group(1))})
    m = re.search(r"(?:make|set)\s+all\s+(?:scenes?\s+)?(?:to\s+)?(16:9|9:16|1:1)", text_lower)
    if m:
        return ("set_aspect", {"aspect": m.group(1)})
    m = re.search(r"shorten\s+(?:all\s+)?scenes?\s+by\s+(\d+(?:\.\d+)?)\s*s(?:econds?)?", text_lower)
    if m:
        return ("shorten_duration", {"seconds": float(m.group(1))})
    m = re.search(r"(?:change|set)\s+(?:all\s+)?voices?\s+to\s+([\w\-\.]+)", text, re.IGNORECASE)
    if m:
        return ("set_voice", {"voice": m.group(1)})
    m = re.search(r"voice\s+(?:to\s+)?([a-z]{2}-[A-Za-z\-]+(?:Neural)?)", text, re.IGNORECASE)
    if m:
        return ("set_voice", {"voice": m.group(1)})
    if re.search(r"darken|\bdark\b", text_lower):
        return ("adjust_visual", {"keyword": "dark moody"})
    if re.search(r"brighten|\bbright\b", text_lower):
        return ("adjust_visual", {"keyword": "bright vibrant"})
    m = re.search(r"add\s+(.+?)\s+to\s+(?:all\s+)?(?:visuals?|visual|scenes?)", text_lower)
    if m:
        return ("adjust_visual", {"keyword": m.group(1)})
    return (None, None)


def create_router(get_db):
    router = APIRouter(prefix="/chat", tags=["chat"])

    @router.post("/apply")
    def apply_instruction(body: dict = Body(...), request: Request = None):
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="body must be JSON object")
        draft_id = (body.get("draft_id") or "").strip()
        instruction = (body.get("instruction") or "").strip()
        if not draft_id or not instruction:
            raise HTTPException(status_code=422, detail="draft_id and instruction required")
        op, params = _parse_instruction(instruction)
        if op is None:
            supported = "shorten subtitles to N / set aspect 16:9 / shorten by Ns / voice to NAME / darken / brighten / add X to visual"
            raise HTTPException(status_code=422, detail="unrecognized instruction. Supported: " + supported)
        applied = []
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as connection:
            _ensure_owner(connection, draft_id, request)
            scenes = connection.execute("SELECT * FROM scene_drafts WHERE workflow_draft_id=? ORDER BY position", (draft_id,)).fetchall()
            for scene in scenes:
                if op == "shorten_subtitles":
                    limit = int(params["limit"])
                    cur = scene["subtitle_display"] or scene["subtitle"] or scene["narration"] or ""
                    new_val = cur[:limit]
                    if new_val != cur:
                        connection.execute("UPDATE scene_drafts SET subtitle_display=?, subtitle=COALESCE(NULLIF(?, ''), subtitle), updated_at=? WHERE id=?", (new_val, new_val, now, scene["id"]))
                        applied.append({"scene_id": scene["id"], "field": "subtitle_display", "before": cur, "after": new_val})
                elif op == "set_aspect":
                    aspect = params["aspect"]
                    if scene["video_aspect"] != aspect:
                        connection.execute("UPDATE scene_drafts SET video_aspect=?, updated_at=? WHERE id=?", (aspect, now, scene["id"]))
                        applied.append({"scene_id": scene["id"], "field": "video_aspect", "before": scene["video_aspect"], "after": aspect})
                elif op == "shorten_duration":
                    seconds = float(params["seconds"])
                    old = scene["duration_seconds"] or 2.0
                    new_dur = max(0.5, round(old - seconds, 1))
                    if new_dur != old:
                        connection.execute("UPDATE scene_drafts SET duration_seconds=?, updated_at=? WHERE id=?", (new_dur, now, scene["id"]))
                        applied.append({"scene_id": scene["id"], "field": "duration_seconds", "before": old, "after": new_dur})
                elif op == "set_voice":
                    voice = params["voice"]
                    if (scene["voice"] or "") != voice:
                        connection.execute("UPDATE scene_drafts SET voice=?, updated_at=? WHERE id=?", (voice, now, scene["id"]))
                        applied.append({"scene_id": scene["id"], "field": "voice", "before": scene["voice"], "after": voice})
                elif op == "adjust_visual":
                    keyword = params["keyword"]
                    cur_vi = scene["visual_intent"] or ""
                    if keyword not in cur_vi:
                        new_vi = (cur_vi + " | " + keyword).strip(" |")
                        connection.execute("UPDATE scene_drafts SET visual_intent=?, updated_at=? WHERE id=?", (new_vi, now, scene["id"]))
                        applied.append({"scene_id": scene["id"], "field": "visual_intent", "before": cur_vi, "after": new_vi})
            connection.commit()
            payload = draft_payload(connection, draft_id)
        return {
            "ok": True,
            "operation": op,
            "params": params,
            "applied_count": len(applied),
            "applied": applied,
            "draft": payload,
        }

    return router
