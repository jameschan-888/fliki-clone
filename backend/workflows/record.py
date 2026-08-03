"""Record to video workflow (fliki 缺失工作流 #3)

- POST /workflow-record {transcript?, source?, language?, title?} -> workflow_draft
- MVP: 接收浏览器录屏后的 ASR 转写文本
- 后续 P1: WebRTC 录屏 + 后端 ASR 闭环
"""
import re
from workflows import build_workflow_router


def _record_to_scenes(body, language):
    text = (body.get("transcript") or body.get("source") or body.get("source_script") or "").strip()
    if not text:
        return ([], "")
    cleaned = re.sub(r"s+", " ", text)
    from workflow_drafts import split_script
    return (split_script(cleaned), text)


def create_router(get_db):
    return build_workflow_router(
        prefix="/workflow-record",
        tag="workflow-record",
        source_to_scenes=_record_to_scenes,
        get_db=get_db,
        max_source_length=80000,
        source_label="transcript",
    )
