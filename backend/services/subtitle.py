"""字幕分块与时长对齐。

借鉴灵剪 packages/core/rendering.py 中的 _caption_chunks 与
_voice_duration_aligned_caption_cues。
"""
from __future__ import annotations

from typing import Any

DEFAULT_MAX_CHARS = 18


def chunk_subtitle(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    cursor = 0
    while cursor < len(text):
        end = min(cursor + max_chars, len(text))
        if end < len(text):
            for separator in (" ", "，", "。", "、", "；", "：", ",", "."):
                boundary = text.rfind(separator, cursor, end)
                if boundary > cursor:
                    end = boundary
                    break
        chunk = text[cursor:end].strip()
        if chunk:
            chunks.append(chunk)
        cursor = end
    return chunks


def align_to_duration(text: str, duration: float, max_chars: int = DEFAULT_MAX_CHARS, min_dur: float = 0.4) -> list[dict[str, Any]]:
    if duration <= 0:
        return []
    chunks = chunk_subtitle(text, max_chars=max_chars)
    if not chunks:
        return []
    each = max(duration / len(chunks), min_dur)
    cues: list[dict[str, Any]] = []
    cursor = 0.0
    for chunk in chunks:
        start = round(cursor, 3)
        end = round(min(duration, cursor + each), 3)
        cues.append({"start": start, "end": end, "text": chunk})
        cursor = end
    if cues:
        cues[-1]["end"] = round(duration, 3)
    return cues
