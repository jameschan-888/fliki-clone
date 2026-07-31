# Pixelle Prompts: 脚本生成模板 (P1-9, 不调用 API).
#
# 来源: docs/DOWNLOAD_AUDIT.md 中 Pixelle 审计 (asset_script_generation / topic_narration / title_generation / image_generation).
# 本模块是文档级 prompt 橇合, 可以直接啲给 LLM, 不依赖 ComfyUI / MoviePy / Streamlit.
# 测试: tests/test_pixelle_prompts.py
from __future__ import annotations

from typing import Any

# 4 套模板名称 (统一与 Pixelle 原项目命名一致, 便于跨项目参考)
SCRIPT_BREAKDOWN = "script_breakdown"
SCENE_NARRATION = "scene_narration"
TITLE_GENERATION = "title_generation"
VISUAL_INTENT = "visual_intent"

TEMPLATE_NAMES = (SCRIPT_BREAKDOWN, SCENE_NARRATION, TITLE_GENERATION, VISUAL_INTENT)


SCRIPT_BREAKDOWN_TEMPLATE = """你是一位专业视频剪辑, 负责把以下脚本拆分为 {min_scenes}-{max_scenes} 个可编辑场景.
语言: {language}.

输出格式: 每场景一行, 格式为 "【场景 N】标题 | 旁白｜画面意图".

要求:
1. 标题 8-15 字, 描述场景主题
2. 旁白 30-80 字, 与原脚本逻辑一致, 不增删事实
3. 画面意图 5-15 字, 关键词用、分隔
4. 不超过 {max_scenes} 场景, 不少于 {min_scenes} 场景

原脚本如下:
---
{script}
---
"""

SCENE_NARRATION_TEMPLATE = """你是一位视频剪辑, 给一个场景写 {min_chars}-{max_chars} 字的口语化旁白.
语言: {language}.

场景信息:
- 标题: {title}
- 画面意图: {visual_intent}
- 上下文: {context}

要求:
1. 口语化, 不要台词或书面语
2. {min_chars}-{max_chars} 字, 避免以、。、。【】等特殊字符结束
3. 保留原意, 不增删事实
4. 适合 TTS 读出, 避免过长句子或难发音字
"""

TITLE_GENERATION_TEMPLATE = """你是视频频道运营, 给以下视频脚本取 3 个 {max_chars}字以内的标题.
语言: {language}.

要求:
1. 标题简洁, 能诱召点击
2. 反映脚本主题, 不骗人点击
3. 避免过度包装 (如 "爆殃！！！​" "必看")
4. 不超过 {max_chars} 字

脚本如下:
---
{script}
---

返回 JSON: {{"titles": ["...", "...", "..."]}}
"""

VISUAL_INTENT_TEMPLATE = """你是视频剪辑, 给一段旁白提炼 5-10 个可用于搜索库的关键词.
语言: {language}.

要求:
1. 关键词中英文优先 (Pexels / Pixabay 索引宜英文)
2. 5-10 个词, 、分隔
3. 避免人名 / 品牌 / 言论
4. 描述画面中的主体、场景、动作

旁白:
---
{narration}
---

返回仅一行, 如 "ocean, sunset, boat, waves".
"""

_TEMPLATES = {
    SCRIPT_BREAKDOWN: SCRIPT_BREAKDOWN_TEMPLATE,
    SCENE_NARRATION: SCENE_NARRATION_TEMPLATE,
    TITLE_GENERATION: TITLE_GENERATION_TEMPLATE,
    VISUAL_INTENT: VISUAL_INTENT_TEMPLATE,
}


def list_templates() -> list[str]:
    """返回所有可用模板名称."""
    return list(TEMPLATE_NAMES)


def get_template(name: str) -> str:
    """获取原始模板文本. 不存在则抛 KeyError."""
    if name not in _TEMPLATES:
        raise KeyError(f"Unknown template {name!r}; available: {list_templates()}")
    return _TEMPLATES[name]


def render_prompt(name: str, **kwargs: Any) -> str:
    """根据参数渲染模板, 返回可以直接啲 LLM 的 prompt.

    参数:
        name: 模板名称 (SCRIPT_BREAKDOWN / SCENE_NARRATION / TITLE_GENERATION / VISUAL_INTENT)
        **kwargs: 模板中的占位变量

    返回:
        渲染后的完整提示词串

    示例:
        >>> render_prompt(SCRIPT_BREAKDOWN, script="hi", language="zh-CN", min_scenes=3, max_scenes=5)
    """
    template = get_template(name)
    try:
        return template.format(**kwargs)
    except KeyError as exc:
        raise KeyError(f"Missing template parameter {exc.args[0]!r} for {name!r}") from exc

