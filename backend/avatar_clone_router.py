# P5E Avatar clone CRUD + synthesize (Wav2Lip-ONNX).
# Always safe to import; downstream ONNX inference is invoked through the
# Provider which already falls back to a static-image MP4 when ONNX deps
# or the model file are unavailable. That guarantees even an empty install
# still produces a deliverable video.
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form

from providers.base import ProviderError
from providers.avatar import build_wav2lip_provider
from provider_config import seed_runtime_providers
from file_security import safe_extension  # P1-8


ALLOWED_FACE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
MAX_FACE_BYTES = 20 * 1024 * 1024   # 20MB
MAX_AUDIO_BYTES = 20 * 1024 * 1024  # 20MB
MAX_OUTPUT_BYTES = 200 * 1024 * 1024  # 200MB hard cap

_IMAGE_MAGIC = {
    '.jpg':  [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.png':  [b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'],
    '.webp': [b'RIFF'],
    '.bmp':  [b'BM'],
    '.gif':  [b'GIF87a', b'GIF89a'],
}

_MAGIC_SNIFF_BYTES = 12

def _validate_image_magic(path, ext):
    expected = _IMAGE_MAGIC.get(ext.lower())
    if not expected:
        return b''
    try:
        with open(path, 'rb') as f:
            head = f.read(_MAGIC_SNIFF_BYTES)
    except OSError:
        return b''
    for sig in expected:
        if head.startswith(sig):
            return head
    raise HTTPException(
        status_code=422,
        detail=(
            'Face image magic bytes do not match extension ' + repr(ext) + '; '
            'got ' + repr(head[:8]) + ', expected one of ' + repr([s[:8] for s in expected])
        ),
    )



def now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def fetch_provider_config(connection, name: str = "wav2lip_onnx") -> dict:
    seed_runtime_providers(connection)
    row = connection.execute(
        "SELECT * FROM provider_configs WHERE category='avatar' AND name=?",
        (name,),
    ).fetchone()
    if row is None:
        return {"configured": False, "enabled": False, "model_path": None}
    cfg = json.loads(row["config_json"] or "{}")
    return {
        "configured": True,
        "enabled": bool(row["enabled"]),
        "is_default": bool(row["is_default"]),
        "model_path": cfg.get("model_path"),
        "ffmpeg_binary": cfg.get("ffmpeg_binary") or "ffmpeg",
        "auto_download": bool(cfg.get("auto_download", False)),
        "fps": float(cfg.get("fps", 25.0)),
        "max_dimension": int(cfg.get("max_dimension", 320)),
    }


def row_payload(row) -> dict:
    base = dict(row)
    return {
        "uuid": base["uuid"],
        "avatar_name": base["avatar_name"],
        "ref_face_path": base["ref_face_path"],
        "ref_audio_path": base["ref_audio_path"],
        "default_audio_path": base["default_audio_path"],
        "language": base["language"],
        "permission_note": base["permission_note"],
        "enabled": bool(base["enabled"]),
        "created_at": base["created_at"],
        "voice": f"avatar:{base['uuid']}",
    }


def create_router(get_db, ref_face_dir: str | None = None, audio_dir: str | None = None, output_dir: str | None = None):
    router = APIRouter(prefix="/avatar-clones", tags=["avatar-clones"])
    face_root = Path(ref_face_dir or Path(__file__).parent / "data" / "avatar_clone_faces")
    audio_root = Path(audio_dir or Path(__file__).parent / "data" / "avatar_clone_audios")
    output_root = Path(output_dir or Path(__file__).parent / "data" / "avatar_outputs")
    for d in (face_root, audio_root, output_root):
        d.mkdir(parents=True, exist_ok=True)

    @router.get("")
    def list_clones(enabled: bool | None = Query(default=None)):
        connection = get_db()
        try:
            seed_runtime_providers(connection)
            if enabled is None:
                rows = connection.execute(
                    "SELECT * FROM avatar_clones ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM avatar_clones WHERE enabled=? ORDER BY created_at DESC",
                    (1 if enabled else 0,),
                ).fetchall()
            return [row_payload(row) for row in rows]
        finally:
            connection.close()

    @router.post("")
    async def create_clone(
        avatar_name: str = Form(..., max_length=120),
        language: str = Form("zh", max_length=16),
        permission_note: str = Form("", max_length=2000),
        ref_face: UploadFile = File(...),
        ref_audio: UploadFile | None = File(default=None),
    ):
        if not ref_face.filename:
            raise HTTPException(status_code=422, detail="ref_face filename is required")
        face_ext = Path(ref_face.filename).suffix.lower()
        if face_ext not in ALLOWED_FACE_EXT:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported face image extension {face_ext!r}; allowed: {sorted(ALLOWED_FACE_EXT)}",
            )

        new_uuid = str(uuid.uuid4())
        face_dest = face_root / f"{new_uuid}{face_ext}"
        size = 0
        with face_dest.open("wb") as out:
            while True:
                chunk = await ref_face.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FACE_BYTES:
                    out.close()
                    face_dest.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail=f"Face image exceeds cap {MAX_FACE_BYTES} bytes")
                out.write(chunk)
        if size < 256:
            face_dest.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Face image too small (<256B)")
        _validate_image_magic(face_dest, face_ext)

        audio_dest_path = ""
        if ref_audio is not None and ref_audio.filename:
            try:
                audio_ext = safe_extension(ref_audio.filename, ALLOWED_AUDIO_EXT)
            except ValueError as exc:
                face_dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported audio extension; allowed: {sorted(ALLOWED_AUDIO_EXT)} ({exc})",
                )
            audio_dest = audio_root / f"{new_uuid}{audio_ext}"
            audio_size = 0
            with audio_dest.open("wb") as out:
                while True:
                    chunk = await ref_audio.read(64 * 1024)
                    if not chunk:
                        break
                    audio_size += len(chunk)
                    if audio_size > MAX_AUDIO_BYTES:
                        out.close()
                        audio_dest.unlink(missing_ok=True)
                        face_dest.unlink(missing_ok=True)
                        raise HTTPException(status_code=413, detail=f"Audio exceeds cap {MAX_AUDIO_BYTES} bytes")
                    out.write(chunk)
            audio_dest_path = str(audio_dest)

        connection = get_db()
        try:
            seed_runtime_providers(connection)
            connection.execute(
                "INSERT INTO avatar_clones (id, uuid, avatar_name, ref_face_path, ref_audio_path, default_audio_path, language, permission_note, enabled, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    f"avatar_{new_uuid}",
                    new_uuid,
                    avatar_name.strip()[:120],
                    str(face_dest),
                    audio_dest_path,
                    audio_dest_path,
                    (language or "zh").lower()[:16],
                    permission_note.strip()[:2000],
                    now_epoch(),
                ),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM avatar_clones WHERE uuid=?", (new_uuid,)).fetchone()
            return row_payload(row)
        finally:
            connection.close()

    @router.get("/{avatar_uuid}")
    def get_clone(avatar_uuid: str):
        connection = get_db()
        try:
            row = connection.execute("SELECT * FROM avatar_clones WHERE uuid=?", (avatar_uuid,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Avatar clone not found")
            return row_payload(row)
        finally:
            connection.close()

    @router.delete("/{avatar_uuid}")
    def delete_clone(avatar_uuid: str):
        connection = get_db()
        try:
            row = connection.execute("SELECT * FROM avatar_clones WHERE uuid=?", (avatar_uuid,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Avatar clone not found")
            for path_str in (row["ref_face_path"], row["ref_audio_path"], row["default_audio_path"]):
                if not path_str:
                    continue
                try:
                    p = Path(path_str)
                    resolved = p.resolve()
                    if face_root in resolved.parents or audio_root in resolved.parents:
                        p.unlink(missing_ok=True)
                except OSError:
                    pass
            for ext in (".mp4", ".wav", ".png"):
                (output_root / f"{avatar_uuid}{ext}").unlink(missing_ok=True)
            connection.execute("DELETE FROM avatar_clones WHERE uuid=?", (avatar_uuid,))
            connection.commit()
            return {"deleted": True, "uuid": avatar_uuid}
        finally:
            connection.close()

    @router.post("/{avatar_uuid}/synthesize")
    def synthesize(avatar_uuid: str):
        connection = get_db()
        try:
            row = connection.execute("SELECT * FROM avatar_clones WHERE uuid=? AND enabled=1", (avatar_uuid,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Active avatar clone not found")
            cfg = fetch_provider_config(connection)
            if not cfg["configured"]:
                raise HTTPException(status_code=422, detail="Wav2Lip provider not configured")
            provider = build_wav2lip_provider(
                model_path=cfg["model_path"],
                auto_download=cfg["auto_download"],
                ffmpeg_binary=cfg["ffmpeg_binary"],
                max_dimension=cfg["max_dimension"],
                fps=cfg["fps"],
            )
            audio_source = row["default_audio_path"]
            if not audio_source or not Path(audio_source).is_file():
                raise HTTPException(status_code=422, detail="Avatar has no default_audio_path; upload ref_audio during create_clone")
            output = output_root / f"{avatar_uuid}.mp4"
            try:
                result = provider.synthesize(
                    face_image_path=row["ref_face_path"],
                    audio_path=audio_source,
                    destination_path=output,
                )
            except ProviderError as exc:
                raise HTTPException(status_code=502, detail=f"Wav2Lip synthesize failed: {exc}") from exc
            if not output.is_file() or output.stat().st_size == 0:
                raise HTTPException(status_code=502, detail="Wav2Lip produced empty output")
            if output.stat().st_size > MAX_OUTPUT_BYTES:
                output.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Wav2Lip output exceeds cap {MAX_OUTPUT_BYTES} bytes")
            return {
                "uuid": avatar_uuid,
                "mode": result.get("mode"),
                "fallback_used": result.get("fallback_used", False),
                "model_present": result.get("model_present", False),
                "elapsed_seconds": result.get("elapsed_seconds"),
                "output_url": f"/avatar-clones/{avatar_uuid}/output",
                "bytes": output.stat().st_size,
            }
        finally:
            connection.close()

    @router.get("/{avatar_uuid}/output")
    def get_output(avatar_uuid: str):
        path = output_root / f"{avatar_uuid}.mp4"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Avatar output not found")
        from fastapi.responses import FileResponse
        return FileResponse(str(path), media_type="video/mp4", filename=f"{avatar_uuid}.mp4")

    async def _stream_to_path(upload: UploadFile, dest: Path, max_bytes: int) -> int:
        size = 0
        with dest.open("wb") as out:
            while True:
                chunk = await upload.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail=f"Upload exceeds cap {max_bytes} bytes")
                out.write(chunk)
        return size

    @router.put("/{avatar_uuid}/ref-face")
    async def replace_ref_face(avatar_uuid: str, ref_face: UploadFile = File(...)):
        connection = get_db()
        try:
            row = connection.execute("SELECT uuid, ref_face_path FROM avatar_clones WHERE uuid=?", (avatar_uuid,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Avatar clone not found")
            if not ref_face.filename:
                raise HTTPException(status_code=422, detail="ref_face filename is required")
            face_ext = Path(ref_face.filename).suffix.lower()
            if face_ext not in ALLOWED_FACE_EXT:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported face image extension {face_ext!r}; allowed: {sorted(ALLOWED_FACE_EXT)}",
                )
            new_dest = face_root / f"{avatar_uuid}{face_ext}"
            await _stream_to_path(ref_face, new_dest, MAX_FACE_BYTES)
            if new_dest.stat().st_size < 256:
                new_dest.unlink(missing_ok=True)
                raise HTTPException(status_code=422, detail="Face image too small (<256B)")
            _validate_image_magic(new_dest, face_ext)
            old_path = Path(row["ref_face_path"]) if row["ref_face_path"] else None
            if old_path and old_path != new_dest and old_path.is_file():
                try:
                    old_path.unlink()
                except OSError:
                    pass
            connection.execute(
                "UPDATE avatar_clones SET ref_face_path=? WHERE uuid=?",
                (str(new_dest), avatar_uuid),
            )
            connection.commit()
            updated = connection.execute("SELECT * FROM avatar_clones WHERE uuid=?", (avatar_uuid,)).fetchone()
            return row_payload(updated)
        finally:
            connection.close()

    @router.put("/{avatar_uuid}/ref-audio")
    async def replace_ref_audio(avatar_uuid: str, ref_audio: UploadFile = File(...)):
        connection = get_db()
        try:
            row = connection.execute("SELECT uuid, ref_audio_path, default_audio_path FROM avatar_clones WHERE uuid=?", (avatar_uuid,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Avatar clone not found")
            if not ref_audio.filename:
                raise HTTPException(status_code=422, detail="ref_audio filename is required")
            audio_ext = Path(ref_audio.filename).suffix.lower()
            if audio_ext not in ALLOWED_AUDIO_EXT:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported audio extension {audio_ext!r}; allowed: {sorted(ALLOWED_AUDIO_EXT)}",
                )
            new_dest = audio_root / f"{avatar_uuid}{audio_ext}"
            await _stream_to_path(ref_audio, new_dest, MAX_AUDIO_BYTES)
            if new_dest.stat().st_size < 64:
                new_dest.unlink(missing_ok=True)
                raise HTTPException(status_code=422, detail="Audio too small (<64B)")
            for old_key in ("ref_audio_path", "default_audio_path"):
                old_path = Path(row[old_key]) if row[old_key] else None
                if old_path and old_path != new_dest and old_path.is_file():
                    try:
                        old_path.unlink()
                    except OSError:
                        pass
            connection.execute(
                "UPDATE avatar_clones SET ref_audio_path=?, default_audio_path=? WHERE uuid=?",
                (str(new_dest), str(new_dest), avatar_uuid),
            )
            connection.commit()
            updated = connection.execute("SELECT * FROM avatar_clones WHERE uuid=?", (avatar_uuid,)).fetchone()
            return row_payload(updated)
        finally:
            connection.close()

    @router.patch("/{avatar_uuid}/meta")
    def update_meta(avatar_uuid: str, body: dict):
        connection = get_db()
        try:
            row = connection.execute("SELECT * FROM avatar_clones WHERE uuid=?", (avatar_uuid,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Avatar clone not found")
            updates = {}
            if "avatar_name" in body:
                name = (body["avatar_name"] or "").strip()
                if not name:
                    raise HTTPException(status_code=422, detail="avatar_name cannot be empty")
                if len(name) > 120:
                    raise HTTPException(status_code=422, detail="avatar_name too long (>120)")
                updates["avatar_name"] = name
            if "language" in body:
                lang = (body["language"] or "").strip()
                if len(lang) > 16:
                    raise HTTPException(status_code=422, detail="language too long (>16)")
                updates["language"] = lang or "zh"
            if "permission_note" in body:
                note = str(body["permission_note"] or "")
                if len(note) > 2000:
                    raise HTTPException(status_code=422, detail="permission_note too long (>2000)")
                updates["permission_note"] = note
            if "enabled" in body:
                updates["enabled"] = 1 if body["enabled"] else 0
            if not updates:
                raise HTTPException(status_code=422, detail="no editable fields supplied")
            set_clause = ", ".join(f"{k}=?" for k in updates.keys())
            params = list(updates.values()) + [avatar_uuid]
            connection.execute(
                f"UPDATE avatar_clones SET {set_clause} WHERE uuid=?",
                params,
            )
            connection.commit()
            updated = connection.execute("SELECT * FROM avatar_clones WHERE uuid=?", (avatar_uuid,)).fetchone()
            return row_payload(updated)
        finally:
            connection.close()

    @router.get("/{avatar_uuid}/ref-face")
    def get_ref_face(avatar_uuid: str):
        connection = get_db()
        try:
            row = connection.execute(
                "SELECT ref_face_path FROM avatar_clones WHERE uuid=?",
                (avatar_uuid,),
            ).fetchone()
            if row is None or not row["ref_face_path"]:
                raise HTTPException(status_code=404, detail="Avatar ref-face not found")
            path = Path(row["ref_face_path"])
            if not path.is_file():
                raise HTTPException(status_code=404, detail="Avatar ref-face file missing")
            from fastapi.responses import FileResponse
            media_type = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else f"image/{path.suffix.lower().lstrip('.') or 'png'}"
            return FileResponse(str(path), media_type=media_type)
        finally:
            connection.close()

    @router.get("/provider/health")
    def provider_health():
        connection = get_db()
        try:
            cfg = fetch_provider_config(connection)
            if not cfg["configured"]:
                raise HTTPException(status_code=422, detail="Wav2Lip provider not configured")
            provider = build_wav2lip_provider(
                model_path=cfg["model_path"],
                auto_download=cfg["auto_download"],
                ffmpeg_binary=cfg["ffmpeg_binary"],
                max_dimension=cfg["max_dimension"],
                fps=cfg["fps"],
            )
            return {"configured": True, **provider.healthcheck()}
        except HTTPException:
            raise
        finally:
            connection.close()

    return router
