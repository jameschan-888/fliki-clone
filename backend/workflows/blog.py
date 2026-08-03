"""Blog to video workflow (fliki 缺失工作流 #1)

- POST /workflow-blog {url?, source?, language?, title?} -> workflow_draft
- MVP: 直接复用 workflow_drafts.split_script 拆分已提取的文章文本
- 后续 P1: URL fetch + RSS parse + AI summarize
"""
import re

from workflows import build_workflow_router


def _blog_to_scenes(body, language):
    text = (body.get("source") or body.get("source_script") or "").strip()
    if not text:
        return ([], "")
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"```.*?```", " ", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"s+", " ", cleaned).strip()
    from workflow_drafts import split_script
    return (split_script(cleaned), text)


def create_router(get_db):
    return build_workflow_router(
        prefix="/workflow-blog",
        tag="workflow-blog",
        source_to_scenes=_blog_to_scenes,
        get_db=get_db,
        max_source_length=100000,
        source_label="article",
    )
