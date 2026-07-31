# P5G Generic uploads router (mp4/mp3/jpg/png/webp) -> data/uploads/{user_id}/.
# rev24 阶段 D P0: 加 user_id 隔离 (token 必带 + 按 user_id 子目录 + DELETE 跨用户 404).
# 兼容性: 文件 URL 改为 /uploads/{user_id}/{file_id}.{ext}, mount 仍 serve.
from __future__ import annotations

import uuid as uuidlib
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File


ALLOWED_EXT = {".mp4", ".mov", ".webm", ".mkv",
               ".mp3", ".wav", ".m4a", ".flac", ".ogg",
               ".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_BYTES = 200 * 1024 * 1024


def _get_user_id(request: Request | None) -> str | None:
    """rev24 阶段 D P0: uploads 强制 user_id, 防匿名上传 + DELETE 跨用户删除."""
    if request is None:
        return None
    try:
        from auth_router import get_user_id_from_request
        return get_user_id_from_request(request)
    except Exception:
        return None


def create_router(upload_dir=None):
    router = APIRouter(prefix="/api/uploads", tags=["uploads"])
    upload_root = Path(upload_dir or Path(__file__).parent / "data" / "uploads")
    upload_root.mkdir(parents=True, exist_ok=True)

    @router.post("")
    async def upload_file(file: UploadFile = File(...), request: Request = None):
        # P0: 必须有有效 token
        user_id = _get_user_id(request)
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail={"error_code": "MISSING_TOKEN", "message": "missing/invalid token",
                        "hint": "/auth/login 或 /auth/register"},
            )
        if not file.filename:
            raise HTTPException(status_code=422, detail="filename is required")
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported extension {ext!r}; allowed: {sorted(ALLOWED_EXT)}",
            )
        new_id = uuidlib.uuid4().hex
        # P0: 按 user_id 子目录隔离, 防跨用户 DELETE 删除别人文件
        user_dir = upload_root / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        dest = user_dir / f"{new_id}{ext}"
        size = 0
        try:
            with dest.open("wb") as out:
                while True:
                    chunk = await file.read(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_BYTES:
                        out.close()
                        dest.unlink(missing_ok=True)
                        raise HTTPException(status_code=413, detail=f"Upload exceeds cap {MAX_BYTES} bytes")
                    out.write(chunk)
            if size < 64:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=422, detail="File too small (<64B)")
        except HTTPException:
            raise
        except Exception as exc:
            dest.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

        # URL 含 user_id, mount 仍能 serve (/uploads/{user_id}/{file_id}.ext)
        url = f"/uploads/{user_id}/{new_id}{ext}"
        return {
            "id": new_id,
            "url": url,
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": size,
            "extension": ext,
            "user_id": user_id,
        }

    @router.delete("/{file_id}")
    def delete_file(file_id: str, request: Request = None):
        # P0: 必须有有效 token, 仅搜自己 user_id 子目录
        user_id = _get_user_id(request)
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail={"error_code": "MISSING_TOKEN", "message": "missing/invalid token"},
            )
        # 跨用户拒绝: 只搜自己子目录, 别人的 file_id 找不到 → 404 (防枚举)
        user_dir = upload_root / user_id
        candidates = list(user_dir.glob(f"{file_id}.*"))
        if not candidates:
            raise HTTPException(status_code=404, detail="Upload not found")
        for c in candidates:
            try:
                c.unlink()
            except OSError:
                pass
        return {"deleted": True, "id": file_id}

    return router
