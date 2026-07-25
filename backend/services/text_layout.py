"""CJK 文本断行器。

借鉴灵剪 engines/ffmpeg_card/text_layout.py：按 token 拆分（中文按字、英文/数字按词），
再按 max_chars 与 max_lines 装配。返回 (lines, warnings)；warnings 含 TEXT_TRUNCATED。
"""
from __future__ import annotations

import re

LATIN_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*")


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    for match in LATIN_WORD.finditer(text):
        if match.start() > index:
            tokens.extend(list(text[index: match.start()]))
        tokens.append(match.group(0))
        index = match.end()
    if index < len(text):
        tokens.extend(list(text[index:]))
    return [token for token in tokens if token.strip()]


def break_text(text: str, max_chars: int = 18, max_lines: int = 2) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    current = ""
    warnings: list[str] = []

    for token in _tokens(text):
        next_line = current + token
        limit = max(max_chars, len(token))
        if current and len(next_line) > limit:
            lines.append(current)
            current = token
            if len(lines) == max_lines:
                warnings.append("TEXT_TRUNCATED")
                return lines, warnings
        else:
            current = next_line

    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        warnings.append("TEXT_TRUNCATED")
        lines = lines[:max_lines]
    if text and "".join(lines) != "".join(_tokens(text)):
        warnings.append("TEXT_TRUNCATED")
    return lines, warnings


def estimate_max_chars(text_length: int, max_lines: int = 2) -> int:
    if text_length <= 0:
        return 1
    return max(1, (text_length + max_lines - 1) // max_lines)
