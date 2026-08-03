"""PPT to video workflow (fliki 缺失工作流 #2)

- POST /workflow-ppt {slides: [{title, content}], language?, title?} -> workflow_draft
- MVP: 接收前端解析后的 slides JSON, 每页一个 scene
- 后续 P1: 直接接 .pptx 上传
"""
from workflows import build_workflow_router


def _ppt_to_scenes(body, language):
    slides = body.get("slides") or []
    if not isinstance(slides, list) or not slides:
        return ([], "")
    scenes = []
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        content = (slide.get("content") or slide.get("text") or "").strip()
        if not content:
            continue
        scenes.append({
            "title": (slide.get("title") or ("幻灯片 " + str(len(scenes) + 1)))[:200],
            "narration": content[:5000],
            "subtitle": content[:200],
        })
    src = ("PPT 共 " + str(len(scenes)) + " 页") if scenes else ""
    return (scenes, src)


def create_router(get_db):
    return build_workflow_router(
        prefix="/workflow-ppt",
        tag="workflow-ppt",
        source_to_scenes=_ppt_to_scenes,
        get_db=get_db,
        max_source_length=50000,
        source_label="slides",
    )
