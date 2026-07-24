#!/usr/bin/env python3
# 更新 HANDOFF.md: P5D 余项 + 116/116 真实基线
from pathlib import Path
H = Path("D:/workspace/Fliki视频制作还原/HANDOFF.md")
src = H.read_text(encoding="utf-8")

# 1. §3 已验证事实: 84/84 -> 116/116
old = "- Python 单元测试：\u006084/84\u0060 通过（原 73 + P5D-5 avatar 字段 round-trip / 默认 null 2 个 + P5D-6 avatar 节点 + props 入口 3 个 + P5D-7 avatar_layout 顶层 / 缺字段 / 非 dict / 坏 JSON 4 个 + P5D-7b avatar_layout 嵌套在 extra / 缺 extra 2 个）。"
new = "- Python 单元测试：\u0060116/116\u0060 通过（2026-07-25 全量回归, 18 个文件; 原 73 + P5D-5 avatar round-trip / 默认 null 2 个 + P5D-6 avatar 节点 + props 入口 3 个 + P5D-7 avatar_layout 顶层 / 缺字段 / 非 dict / 坏 JSON 4 个 + P5D-7b avatar_layout 嵌套在 extra / 缺 extra 2 个 + P5D-7c scene-level 合并 / patch / 校验 13 个 + P5D-8 preview kwarg / 4.919s 4 个 + P5D-8 async 后台化 4 个 + P5D 余项 _validate_image_magic 假 PNG 防御 10 个）。"
assert old in src, "old 84/84 line not found"
src = src.replace(old, new)
print("[OK] HANDOFF \u00a73: 84/84 -> 116/116")

# 2. §10 下一步: 加 P5D 余项说明 (在 A 段后)
old_a_end = "- 受影响文件：\u0060backend/db/schema.sql\u0060、\u0060backend/main.py\u0060、\u0060backend/workflow_drafts.py\u0060、\u0060backend/workflow_pipeline.py\u0060、\u0060backend/avatar_clone_router.py\u0060、\u0060backend/tests/test_workflow_drafts.py\u0060、\u0060app/src/types/draft.ts\u0060、\u0060app/src/api/drafts.ts\u0060、\u0060app/src/App.tsx\u0060、\u0060app/vite.config.ts\u0060、\u0060app/index.html\u0060、\u0060app/avatars.html\u0060（新建）、\u0060app/env-check.html\u0060。"
new_a_end = old_a_end + chr(10) + chr(10) + "### A2：P5D 余项 (已完成 2026-07-25)" + chr(10)
new_a_end += "- \u0060Main.tsx\u0060 \u0060AvatarLayout\u0060 加 \u0060shapeBorderRadii?: { circle?, rounded?, square? }\u0060, \u0060resolveLayout\u0060 重写按 shape 选 radius (shapeBorderRadii[shape] ?? 默认); circle 自动 = max/2, rounded = borderRadiusPx, square = 0. \u0060avatarBoxStyle\u0060 移除 shape if/else 块, 统一用 resolveLayout 算好的 borderRadiusPx." + chr(10)
new_a_end += "- \u0060avatar_clone_router.py\u0060 加 \u0060_IMAGE_MAGIC\u0060 dict + \u0060_validate_image_magic(path, ext)\u0060 函数, size < 256 之后调用. PNG: 89 50 4E 47 0D 0A 1A 0A; JPEG: FF D8 FF; WebP: RIFF; BMP: BM; GIF: GIF87a/GIF89a. 假 PNG / 扩展名伪造 -> 422." + chr(10)
new_a_end += "- 新增 \u0060backend/tests/test_avatar_image_magic.py\u0060 (10 case, 0.040s 全绿)." + chr(10)
new_a_end += "- 受影响文件: \u0060backend/workers/remotion-project/src/Main.tsx\u0060, \u0060backend/avatar_clone_router.py\u0060, \u0060backend/tests/test_avatar_image_magic.py\u0060, \u0060scripts/patch_p5d7c_shape_radius.py\u0060, \u0060scripts/patch_p5d7c_shape_radius_followup.py\u0060, \u0060scripts/patch_avatar_magic_check.py\u0060, \u0060scripts/run_tests.js\u0060 (rev3)." + chr(10)
assert old_a_end in src, "A2 anchor not found"
src = src.replace(old_a_end, new_a_end)
print("[OK] HANDOFF \u00a710 A2: P5D 余项")

# 3. 顶部更新时间戳
old = "更新时间：2026-07-24"
new = "更新时间：2026-07-25"
assert old in src, "timestamp anchor not found"
src = src.replace(old, new)
print("[OK] HANDOFF timestamp updated")

H.write_text(src, encoding="utf-8")
print("[DONE] HANDOFF saved")
