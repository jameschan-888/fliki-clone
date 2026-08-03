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
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    from workflow_drafts import split_script
    return (split_script(cleaned), text)



import urllib.request
import urllib.error

def _fetch_url(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (FlikiBot/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(200000).decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return ""
    # 极简 HTML -> 文本: 去 script/style, 抽 <p> / <h1-h3>
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    paras = re.findall(r"<(?:p|h[1-6]|li|article)[^>]*>(.+?)</(?:p|h[1-6]|li|article)>", text, flags=re.IGNORECASE | re.DOTALL)
    if not paras:
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()[:20000]
    joined = " ".join(re.sub(r"<[^>]+>", " ", p) for p in paras)
    joined = re.sub(r"\s+", " ", joined).strip()
    return joined[:20000]

def _blog_to_scenes_extended(body, language):
    url = (body.get("url") or "").strip()
    if url and not body.get("source"):
        fetched = _fetch_url(url)
        if fetched:
            body = dict(body)
            body["source"] = fetched
    scenes, src = _blog_to_scenes(body, language)
    return (scenes, src)
def create_router(get_db):
    return build_workflow_router(
        prefix="/workflow-blog",
        tag="workflow-blog",
        source_to_scenes=_blog_to_scenes_extended,
        get_db=get_db,
        max_source_length=100000,
        source_label="article",
    )
