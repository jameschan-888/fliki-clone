"""Translate video workflow (fliki 缺失工作流 #4)

- POST /workflow-translate {source?, source_lang?, target_lang?, language?, title?} -> workflow_draft
- MVP: 接收已转写好的源文本, 生成 scenes
- 后续 P1: ASR+MT+TTS+lip-sync 闭环
"""
import re
from workflows import build_workflow_router


def _translate_to_scenes(body, language):
    text = (body.get("source") or body.get("source_script") or "").strip()
    if not text:
        return ([], "")
    cleaned = re.sub(r"s+", " ", text)
    from workflow_drafts import split_script
    src = ("[" + str(body.get("source_lang") or "?") + "->" + str(body.get("target_lang") or language) + "] ") + text[:200]
    return (split_script(cleaned), src)


def create_router(get_db):
    return build_workflow_router(
        prefix="/workflow-translate",
        tag="workflow-translate",
        source_to_scenes=_translate_to_scenes,
        get_db=get_db,
        max_source_length=50000,
        source_label="source",
    )
