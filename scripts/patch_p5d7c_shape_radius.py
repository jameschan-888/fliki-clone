#!/usr/bin/env python3
# P5D-7c 余项: per-shape borderRadius + 假 PNG magic 校验
# 生成时间: 2026-07-25
import re, sys
from pathlib import Path

ROOT = Path("D:/workspace/Fliki视频制作还原")
MAIN = ROOT / "backend/workers/remotion-project/src/Main.tsx"
ROUTER = ROOT / "backend/avatar_clone_router.py"

# ---- Part 1: Main.tsx 加 shapeBorderRadii + resolveLayout 重写 ----
src = MAIN.read_text(encoding="utf-8")

# 1.1 AvatarLayout 接口
old = (
    "export interface AvatarLayout {\n"
    "  position?: AvatarPosition;\n"
    "  widthPx?: number;\n"
    "  heightPx?: number;\n"
    "  marginPx?: number;\n"
    "  borderColor?: string;\n"
    "  borderPx?: number;\n"
    "  borderRadiusPx?: number;\n"
    "  shape?: AvatarShape;\n"
    "  showLabel?: boolean;\n"
    "}"
)
new = (
    "export interface AvatarLayout {\n"
    "  position?: AvatarPosition;\n"
    "  widthPx?: number;\n"
    "  heightPx?: number;\n"
    "  marginPx?: number;\n"
    "  borderColor?: string;\n"
    "  borderPx?: number;\n"
    "  borderRadiusPx?: number;\n"
    "  shapeBorderRadii?: {\n"
    "    circle?: number;\n"
    "    rounded?: number;\n"
    "    square?: number;\n"
    "  };\n"
    "  shape?: AvatarShape;\n"
    "  showLabel?: boolean;\n"
    "}"
)
assert old in src, "AvatarLayout block not found"
src = src.replace(old, new)
print("[OK] AvatarLayout + shapeBorderRadii")

# 1.2 resolveLayout
old = (
    "function resolveLayout(sceneLayout: AvatarLayout | undefined, globalLayout: AvatarLayout | undefined): Required<AvatarLayout> {\n"
    "  const merged: AvatarLayout = { ...(globalLayout ?? {}), ...(sceneLayout ?? {}) };\n"
    "  return {\n"
    "    position: merged.position ?? DEFAULT_AVATAR_LAYOUT.position,\n"
    "    widthPx: merged.widthPx ?? DEFAULT_AVATAR_LAYOUT.widthPx,\n"
    "    heightPx: merged.heightPx ?? DEFAULT_AVATAR_LAYOUT.heightPx,\n"
    "    marginPx: merged.marginPx ?? DEFAULT_AVATAR_LAYOUT.marginPx,\n"
    "    borderColor: merged.borderColor ?? DEFAULT_AVATAR_LAYOUT.borderColor,\n"
    "    borderPx: merged.borderPx ?? DEFAULT_AVATAR_LAYOUT.borderPx,\n"
    "    borderRadiusPx: merged.borderRadiusPx ?? DEFAULT_AVATAR_LAYOUT.borderRadiusPx,\n"
    "    shape: merged.shape ?? DEFAULT_AVATAR_LAYOUT.shape,\n"
    "    showLabel: merged.showLabel ?? DEFAULT_AVATAR_LAYOUT.showLabel,\n"
    "  };\n"
    "}"
)
new = (
    "function _shapeRadius(merged: AvatarLayout, base: Required<AvatarLayout>): number {\n"
    "  const shapeRadii = merged.shapeBorderRadii ?? {};\n"
    "  const shape = merged.shape ?? DEFAULT_AVATAR_LAYOUT.shape;\n"
    "  if (typeof shapeRadii[shape] === 'number') return shapeRadii[shape];\n"
    "  if (shape === 'circle') return Math.max(base.widthPx, base.heightPx) / 2;\n"
    "  if (shape === 'square') return 0;\n"
    "  return base.borderRadiusPx;\n"
    "}\n\n"
    "function resolveLayout(sceneLayout: AvatarLayout | undefined, globalLayout: AvatarLayout | undefined): Required<AvatarLayout> {\n"
    "  const merged: AvatarLayout = { ...(globalLayout ?? {}), ...(sceneLayout ?? {}) };\n"
    "  const base: Required<AvatarLayout> = {\n"
    "    position: merged.position ?? DEFAULT_AVATAR_LAYOUT.position,\n"
    "    widthPx: merged.widthPx ?? DEFAULT_AVATAR_LAYOUT.widthPx,\n"
    "    heightPx: merged.heightPx ?? DEFAULT_AVATAR_LAYOUT.heightPx,\n"
    "    marginPx: merged.marginPx ?? DEFAULT_AVATAR_LAYOUT.marginPx,\n"
    "    borderColor: merged.borderColor ?? DEFAULT_AVATAR_LAYOUT.borderColor,\n"
    "    borderPx: merged.borderPx ?? DEFAULT_AVATAR_LAYOUT.borderPx,\n"
    "    borderRadiusPx: merged.borderRadiusPx ?? DEFAULT_AVATAR_LAYOUT.borderRadiusPx,\n"
    "    shape: merged.shape ?? DEFAULT_AVATAR_LAYOUT.shape,\n"
    "    showLabel: merged.showLabel ?? DEFAULT_AVATAR_LAYOUT.showLabel,\n"
    "  };\n"
    "  base.borderRadiusPx = _shapeRadius(merged, base);\n"
    "  return base;\n"
    "}"
)
assert old in src, "resolveLayout block not found"
src = src.replace(old, new)
print("[OK] resolveLayout + _shapeRadius")

# 1.3 avatarBoxStyle 移除 shape destructure (resolveLayout 已塞正确值)
old = (
    "function avatarBoxStyle(\n"
    "  layout: Required<AvatarLayout>,\n"
    "  canvas: { width: number; height: number },\n"
    "): React.CSSProperties {\n"
    "  const { widthPx, heightPx, marginPx, position, borderColor, borderPx, borderRadiusPx, shape } = layout;"
)
new = (
    "function avatarBoxStyle(\n"
    "  layout: Required<AvatarLayout>,\n"
    "  canvas: { width: number; height: number },\n"
    "): React.CSSProperties {\n"
    "  // borderRadiusPx 已在 resolveLayout 中按 shapeBorderRadii / shape 默认值算好, 直接用.\n"
    "  const { widthPx, heightPx, marginPx, position, borderColor, borderPx, borderRadiusPx } = layout;"
)
assert old in src, "avatarBoxStyle header not found"
src = src.replace(old, new)
print("[OK] avatarBoxStyle destructure")

# 1.4 isCircle 引用 layout.shape
old = "  const isCircle = shape === 'circle';"
new = "  const isCircle = layout.shape === 'circle';"
if old in src:
    src = src.replace(old, new)
    print("[OK] isCircle reference")
else:
    print("[WARN] isCircle reference not found (layout refactor needed manually)")

MAIN.write_text(src, encoding="utf-8")
print("[DONE] Main.tsx saved")