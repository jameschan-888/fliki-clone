"""Record to video workflow (fliki 缺失工作流 #3)

- POST /workflow-record {transcript?, source?, language?, title?} -> workflow_draft
- MVP: 接收浏览器录屏后的 ASR 转写文本
- 后续 P1: WebRTC 录屏 + 后端 ASR 闭环
"""
import re
import uuid
import pathlib
from workflows import build_workflow_router


def _record_to_scenes(body, language):
    text = (body.get("transcript") or body.get("source") or body.get("source_script") or "").strip()
    if not text:
        return ([], "")
    cleaned = re.sub(r"\s+", " ", text)
    from workflow_drafts import split_script
    return (split_script(cleaned), text)



def _transcribe_audio(path, language):
    # MVP: 直接返回客户端提供的 transcript, 不做 server-side ASR
    # P1 接 faster-whisper / Edge ASR
    return ""

def _record_to_scenes_extended(body, language):
    transcript = body.get("transcript") or ""
    if not transcript and body.get("audio_path"):
        transcript = _transcribe_audio(body["audio_path"], language)
    if transcript:
        body = dict(body)
        body["transcript"] = transcript
    return _record_to_scenes(body, language)
def create_router(get_db):
    router = build_workflow_router(
        prefix="/workflow-record",
        tag="workflow-record",
        source_to_scenes=_record_to_scenes_extended,
        get_db=get_db,
        max_source_length=80000,
        source_label="transcript",
    )

    from fastapi import HTTPException, Request
    from auth_router import get_user_id_from_request

    @router.post("/upload")
    async def upload_recording(request: Request):
        user_id = get_user_id_from_request(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        form = await request.form()
        recording = form.get("recording")
        if recording is None or not hasattr(recording, "read"):
            raise HTTPException(status_code=422, detail="recording 文件不能为空")
        target_dir = pathlib.Path("data/uploads/recordings")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / (str(user_id) + "_" + uuid.uuid4().hex + ".webm")
        target.write_bytes(await recording.read())
        return {"audio_path": str(target), "filename": target.name}

    return router