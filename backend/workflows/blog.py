"""Blog to video workflow (fliki 缺失工作流 #1)

- POST /workflow-blog {url?, source?, language?, title?, use_ai?, generate_images?} -> workflow_draft
- R26: URL fetch + DeepSeek 总结文章为 5-10 段精炼分镜 (env BLOG_AI_ENABLED=true 默认开启, 失败 fallback 到 split_script)
- R26: 可选 MiniMax 出图 (env BLOG_IMAGE_ENABLED=true 默认关, 需人手开启避免频购额度)
"""
import json
import os
import re
import urllib.request
import urllib.error

from workflows import build_workflow_router

SUPPORTED_LANGUAGES = ("zh-CN", "en-US", "ja-JP", "es-ES", "fr-FR", "de-DE", "ko-KR")

def _fetch_url(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (FlikiBot/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(200000).decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, UnicodeDecodeError):
        return ""
    # 极简 HTML -> 文本: 去 script/style, 抽 <p> / <h1-h6> / <li> / <article>
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    paras = re.findall(r"<(?:p|h[1-6]|li|article)[^>]*>(.+?)</(?:p|h[1-6]|li|article)>", text, flags=re.IGNORECASE | re.DOTALL)
    if not paras:
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()[:20000]
    joined = " ".join(re.sub(r"<[^>]+>", " ", p) for p in paras)
    joined = re.sub(r"\s+", " ", joined).strip()
    return joined[:20000]

def _ai_summarize_article(text, language="zh-CN", model="deepseek-chat"):
    """R26: DeepSeek summarize article to 5-10 scenes. Returns list of dict {title, narration, visual_intent}.
    Returns [] on any failure (caller falls back to split_script).
    """
    if not text or not str(text).strip():
        return []
    if (os.getenv("BLOG_AI_ENABLED") or "true").strip().lower() in ("0", "false", "no", "off"):
        return []
    try:
        from providers.text.deepseek_text import DeepSeekTextProvider
        provider = DeepSeekTextProvider(model=model)
    except Exception:
        return []
    lang_label = {"zh-CN": "Chinese (Simplified)", "en-US": "English", "ja-JP": "Japanese", "es-ES": "Spanish", "fr-FR": "French", "de-DE": "German", "ko-KR": "Korean"}.get(language, "Chinese")
    system = (
        "You are a blog-to-video script writer. Given article text, summarize to 5-10 short video scenes."
        " Output STRICT JSON array (no markdown, no surrounding text), each item has keys:"
        " {title (12 chars max in " + lang_label + "), narration (this scene's narration 30-80 chars in " + lang_label + "), visual_intent (visual keywords in " + lang_label + ", comma-separated, 6 max)}."
        " Each scene must stand alone as a self-contained video clip."
        " Return 5-10 scenes based on article length. JSON only."
    )
    try:
        result = provider.generate(text[:8000], system=system, max_tokens=2500, temperature=0.6)
    except Exception:
        return []
    raw = (result.get("content") or "").strip()
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(raw[start:end])
    except Exception:
        return []
    if not isinstance(data, list) or not data:
        return []
    out = []
    for item in data[:10]:
        if not isinstance(item, dict):
            continue
        narration = (item.get("narration") or "").strip()
        if not narration:
            continue
        out.append({
            "title": (item.get("title") or " ").strip()[:80],
            "narration": narration[:400],
            "visual_intent": (item.get("visual_intent") or " ").strip()[:200],
        })
        if len(out) >= 10:
            break
    return out

def _enrich_scenes_with_images(scenes, aspect_ratio="16:9", output_dir=" "):
    """R26: optional MiniMax image generation per scene. Adds image_url to each scene dict.
    Returns updated scenes list (mutates + returns same list). On any provider failure, returns scenes unchanged.
    """
    if not scenes:
        return scenes
    if (os.getenv("BLOG_IMAGE_ENABLED") or "false").strip().lower() not in ("1", "true", "yes", "on"):
        return scenes
    try:
        from providers.stock.minimax_image import MiniMaxImageProvider
        provider = MiniMaxImageProvider()
    except Exception:
        return scenes
    import uuid
    from pathlib import Path
    base = Path(output_dir) if output_dir else Path("data/blog_images")
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        return scenes
    for scene in scenes:
        prompt = (scene.get("visual_intent") or scene.get("narration") or " ").strip()
        if not prompt:
            continue
        dest = base / (uuid.uuid4().hex + ".jpg")
        try:
            resp = provider.fetch(query=prompt, destination=dest, aspect_ratio=aspect_ratio, n=1, prompt_optimizer=True)
            if isinstance(resp, dict):
                url = resp.get("url") or resp.get("image_url")
                if url:
                    scene["image_url"] = url
                path = resp.get("path") or resp.get("local_path")
                if path:
                    scene["image_path"] = str(path)
        except Exception:
            continue
    return scenes

def _blog_to_scenes(body, language):
    text = (body.get("source") or body.get("source_script") or "").strip()
    if not text:
        return ([], "")
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"```.*?```", " ", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    from workflow_drafts import split_script
    return (split_script(cleaned), text)

def _blog_to_scenes_extended(body, language):
    body = dict(body or {})
    url = (body.get("url") or "").strip()
    if url and not body.get("source"):
        fetched = _fetch_url(url)
        if fetched:
            body["source"] = fetched
    text = (body.get("source") or body.get("source_script") or "").strip()
    if not text:
        return ([], "")
    use_ai = body.get("use_ai", True)
    ai_scenes = []
    if use_ai:
        ai_model = (body.get("ai_model") or "deepseek-chat").strip()
        ai_scenes = _ai_summarize_article(text, language=language, model=ai_model)
    if ai_scenes:
        scenes = ai_scenes
    else:
        scenes, _ = _blog_to_scenes(body, language)
    if body.get("generate_images"):
        aspect = (body.get("video_aspect") or "16:9").strip()
        output_dir = (body.get("image_output_dir") or "").strip()
        scenes = _enrich_scenes_with_images(scenes, aspect_ratio=aspect, output_dir=output_dir)
    return (scenes, text)


def create_router(get_db):
    return build_workflow_router(
        prefix="/workflow-blog",
        tag="workflow-blog",
        source_to_scenes=_blog_to_scenes_extended,
        get_db=get_db,
        max_source_length=100000,
        source_label="article",
    )
