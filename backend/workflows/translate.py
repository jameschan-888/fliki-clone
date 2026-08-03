"""Translate video workflow (fliki 缺失工作流 #4)

- POST /workflow-translate {source?, source_lang?, target_lang?, language?, title?} -> workflow_draft
- MVP: 接收已转写好的源文本, 生成 scenes
- 后续 P1: ASR+MT+TTS+lip-sync 闭环
"""
import json
import os
import pathlib
import re
import urllib.request
import uuid
from workflows import build_workflow_router


def _translate_to_scenes(body, language):
    text = (body.get("source") or body.get("source_script") or "").strip()
    if not text:
        return ([], "")
    cleaned = re.sub(r"\s+", " ", text)
    from workflow_drafts import split_script
    src = ("[" + str(body.get("source_lang") or "?") + "->" + str(body.get("target_lang") or language) + "] ") + text[:200]
    return (split_script(cleaned), src)



def _translate_text(text, source_lang, target_lang):
    endpoint = os.environ.get("FLIKI_TRANSLATION_URL", "").strip()
    if not endpoint or source_lang == target_lang:
        return text
    payload = json.dumps({"text": text, "source_lang": source_lang, "target_lang": target_lang}).encode("utf-8")
    try:
        request = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
        return str(result.get("text") or result.get("translation") or text)
    except (OSError, ValueError, json.JSONDecodeError):
        return text

def _translate_to_scenes_extended(body, language):
    body = dict(body)
    if not body.get("source") and body.get("media_path"):
        try:
            from autoedit import transcribe_audio
            body["source"] = transcribe_audio(body["media_path"], language=str(body.get("source_lang") or language).split("-")[0]) or ""
        except (ImportError, OSError, RuntimeError, ValueError):
            body["source"] = ""
    source_lang = str(body.get("source_lang") or "")
    target_lang = str(body.get("target_lang") or language)
    if body.get("source"):
        body["source"] = _translate_text(str(body["source"]), source_lang, target_lang)
    return _translate_to_scenes(body, language)

def create_router(get_db):
    router = build_workflow_router(prefix="/workflow-translate", tag="workflow-translate", source_to_scenes=_translate_to_scenes_extended, get_db=get_db, max_source_length=50000, source_label="source")
    from fastapi import HTTPException, Request
    from auth_router import get_user_id_from_request

    @router.post("/upload")
    async def upload_translate_media(request: Request):
        user_id = get_user_id_from_request(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        form = await request.form()
        media = form.get("media")
        if media is None or not hasattr(media, "read"):
            raise HTTPException(status_code=422, detail="media 文件不能为空")
        target_dir = pathlib.Path("data/uploads/translate")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / (str(user_id) + "_" + uuid.uuid4().hex + ".media")
        target.write_bytes(await media.read())
        return {"media_path": str(target), "filename": target.name}

    return router
