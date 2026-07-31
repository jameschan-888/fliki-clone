# File Security: 路径清洗 + Windows 保留名拒绝 + Path Traversal 防护.
# 统一文件操作入口, 替代散落在各处的 Path() / basename / suffix 处理.
# 测试: tests/test_file_security.py (P1-8).
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Iterable


# Windows 保留名 (大小写不敏感). 这些文件名不能用作文件名, 即便带扩展名也不行 (CON.txt 也不行).
_WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})

# Windows 完整路径不允许的字符: < > : " / \\ | ? *
_WINDOWS_FORBIDDEN_CHARS = re.compile(r'[<>:"/\\\\|?*\x01-\x1f]')

# 路径分隔符 (用于检测用户输入是否包含分隔符)
_PATH_SEPARATORS = ("/", "\\")


def _strip_dangerous_chars(name: str) -> str:
    """去除 Windows 禁止字符 + 控制字符, 折叠连续分隔符."""
    cleaned = _WINDOWS_FORBIDDEN_CHARS.sub("_", name)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("._-")


def _strip_diacritics(text: str) -> str:
    """去除重音符号, 避免 macOS HFS+ / Windows NTFS 大小写折叠时的边角案例."""
    return "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def safe_filename(name: str, max_length: int = 120, *, fallback: str = "file") -> str:
    """清洗文件名: 去除路径分隔符 + Windows 禁止字符 + 保留名拒绝 + 长度截断.

    参数:
        name: 原始文件名 (可能来自用户上传或外部 API)
        max_length: 最大长度 (默认 120, 避免部分文件系统 255 边界)
        fallback: 当清洗后为空时使用的占位名

    返回:
        安全可用的文件名 (不含路径分隔符)

    示例:
        >>> safe_filename("../etc/passwd")
        'etc_passwd'
        >>> safe_filename("CON.txt")
        '_CON.txt'
        >>> safe_filename("")
        'file'

    """
    if not isinstance(name, str) or not name.strip():
        return fallback

    # 取 basename
    basename = name
    for sep in _PATH_SEPARATORS:
        if sep in basename:
            basename = basename.rsplit(sep, 1)[-1]

    # 去重音
    basename = _strip_diacritics(basename)

    # 去危险字符
    basename = _strip_dangerous_chars(basename)

    if not basename:
        return fallback

    # Windows 保留名检测 (按 . 拆分第一段, 与扩展名无关)
    stem = basename.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        basename = f"_{basename}"

    # 长度截断
    if len(basename) > max_length:
        if "." in basename:
            stem_part, ext_part = basename.rsplit(".", 1)
            keep = max_length - len(ext_part) - 1
            basename = stem_part[:keep] + "." + ext_part
        else:
            basename = basename[:max_length]

    return basename or fallback


def validate_not_reserved(filename: str) -> None:
    """检查文件名不是 Windows 保留名, 否则抛 ValueError."""
    stem = filename.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        raise ValueError(f"Filename {filename!r} is a Windows reserved name")


def safe_join(base_dir, *parts) -> Path:
    """安全 join 路径: 防止 path traversal (../ 逃出 base_dir)."""
    base = Path(base_dir).resolve()
    joined = base.joinpath(*parts).resolve()
    try:
        joined.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Path {joined!s} escapes base {base!s}") from exc
    return joined


def safe_extension(filename: str, allowed) -> str:
    """从文件名提取扩展名并验证在白名单内."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed:
        raise ValueError(f"Extension {ext!r} not in allowed set {sorted(allowed)}")
    return ext


def is_within_directory(path, directory) -> bool:
    """判断 path 是否在 directory 内."""
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
        return True
    except ValueError:
        return False

