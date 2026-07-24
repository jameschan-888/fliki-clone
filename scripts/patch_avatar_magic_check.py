#!/usr/bin/env python3
# P5D 余项: 假 PNG / 假 JPEG 等 magic 校验, 防 ffmpeg 卡死
from pathlib import Path
R = Path("D:/workspace/Fliki视频制作还原/backend/avatar_clone_router.py")
src = R.read_text(encoding="utf-8")

old1 = "MAX_OUTPUT_BYTES = 200 * 1024 * 1024  # 200MB hard cap"
new1 = "MAX_OUTPUT_BYTES = 200 * 1024 * 1024  # 200MB hard cap" + chr(10) + chr(10)
new1 += "_IMAGE_MAGIC = {" + chr(10)
new1 += "    '.jpg':  [b'\\xff\\xd8\\xff']," + chr(10)
new1 += "    '.jpeg': [b'\\xff\\xd8\\xff']," + chr(10)
new1 += "    '.png':  [b'\\x89\\x50\\x4e\\x47\\x0d\\x0a\\x1a\\x0a']," + chr(10)
new1 += "    '.webp': [b'RIFF']," + chr(10)
new1 += "    '.bmp':  [b'BM']," + chr(10)
new1 += "    '.gif':  [b'GIF87a', b'GIF89a']," + chr(10)
new1 += "}" + chr(10) + chr(10)
new1 += "_MAGIC_SNIFF_BYTES = 12" + chr(10) + chr(10)
new1 += "def _validate_image_magic(path, ext):" + chr(10)
new1 += "    expected = _IMAGE_MAGIC.get(ext.lower())" + chr(10)
new1 += "    if not expected:" + chr(10)
new1 += "        return b''" + chr(10)
new1 += "    try:" + chr(10)
new1 += "        with open(path, 'rb') as f:" + chr(10)
new1 += "            head = f.read(_MAGIC_SNIFF_BYTES)" + chr(10)
new1 += "    except OSError:" + chr(10)
new1 += "        return b''" + chr(10)
new1 += "    for sig in expected:" + chr(10)
new1 += "        if head.startswith(sig):" + chr(10)
new1 += "            return head" + chr(10)
new1 += "    raise HTTPException(" + chr(10)
new1 += "        status_code=422," + chr(10)
new1 += "        detail=(" + chr(10)
new1 += "            'Face image magic bytes do not match extension ' + repr(ext) + '; '" + chr(10)
new1 += "            'got ' + repr(head[:8]) + ', expected one of ' + repr([s[:8] for s in expected])" + chr(10)
new1 += "        )," + chr(10)
new1 += "    )" + chr(10)
assert old1 in src, "MAX_OUTPUT_BYTES line not found"
src = src.replace(old1, new1)
print("[OK] IMAGE_MAGIC dict + _validate_image_magic helper added")

old2 = (
    "        if size < 256:" + chr(10)
    + "            face_dest.unlink(missing_ok=True)" + chr(10)
    + "            raise HTTPException(status_code=422, detail=\"Face image too small (<256B)\")" + chr(10)
)
new2 = (
    "        if size < 256:" + chr(10)
    + "            face_dest.unlink(missing_ok=True)" + chr(10)
    + "            raise HTTPException(status_code=422, detail=\"Face image too small (<256B)\")" + chr(10)
    + "        _validate_image_magic(face_dest, face_ext)" + chr(10)
)
assert old2 in src, "size < 256 block not found"
src = src.replace(old2, new2)
print("[OK] _validate_image_magic() called after size check")

R.write_text(src, encoding="utf-8")
print("[DONE] avatar_clone_router.py saved")
