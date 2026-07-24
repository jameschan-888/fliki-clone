#!/usr/bin/env python3
# 补 patch: avatarBoxStyle 删除 if shape 分支, 统一用 resolveLayout 已算好的 borderRadiusPx
from pathlib import Path
MAIN = Path("D:/workspace/Fliki视频制作还原/backend/workers/remotion-project/src/Main.tsx")
src = MAIN.read_text(encoding="utf-8")

old = (
    "  if (shape === 'circle') {\n"
    "    style.borderRadius = Math.max(widthPx, heightPx) / 2;\n"
    "  } else if (shape === 'rounded') {\n"
    "    style.borderRadius = borderRadiusPx;\n"
    "  } else {\n"
    "    style.borderRadius = 0;\n"
    "  }\n"
)
new = (
    "  // borderRadiusPx 已在 resolveLayout 中按 shapeBorderRadii / shape 默认值算好, 直接用.\n"
    "  style.borderRadius = borderRadiusPx;\n"
)
assert old in src, "shape if block not found"
src = src.replace(old, new)
MAIN.write_text(src, encoding="utf-8")
print("[OK] avatarBoxStyle shape if/else removed")