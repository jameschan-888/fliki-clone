# P7-Persist MiniMax Voice Clones CRUD + preview.
# Mirror of voice_clone_router.py but backed by MiniMax cloud clone
# (ref_audio -> upload -> voice_clone -> persistent voice_id).
#
# Persistence: minimax_voice_clones table (sha256-keyed cache survives restart).
# This router is the single source of truth for MiniMax clone records.
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

from providers.base import ProviderError
from providers.tts import build_minimax_provider
from providers.tts.minimax_tts import sha256_of_file


ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus"}
MAX_REF_AUDIO_BYTES = 20 * 1024 * 1024  # 20MB cap; references are short samples


def now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def row_payload(row) -> dict:
    base = dict(row)
    return {
        "uuid": base["uuid"],
        "cloned_name": base["cloned_name"],
        "ref_audio_path": base["ref_audio_path"],
        "ref_audio_sha256": base["ref_audio_sha256"],
        "ref_text": base["ref_text"],
        "sample_text": base["sample_text"],
        "language": base["language"],
        "voice_id": base["voice_id"],
        "model": base["model"],
        "provider": base["provider"],
        "enabled": bool(base["enabled"]),
        "voice": f"minimax-clone:{base['voice_id']}",
        "created_at": base["created_at"],
        "updated_at": base["updated_at"],
    }


def fetch_minimax_config(connection) -> dict:
    """Mirror fetch_provider_config for the minimax TTS provider."""
    row = connection.execute(
        "SELECT * FROM provider_configs WHERE category='tts' AND name='minimax'"
    ).fetchone()
    if row is None:
        return {"base_url": None, "enabled": False, "model": None, "configured": False}
    config = json.loads(row["config_json"] or "{}")
    return {
        "base_url": config.get("base_url") or "https://api.minimaxi.com",
        "enabled": bool(row["enabled"]),
        "model": config.get("model") or "speech-02-turbo",
        "configured": True,
    }


def resolve_provider(connection) -> tuple:
    cfg = fetch_minimax_config(connection)
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=422,
            detail="MINIMAX_API_KEY not configured; set it via .env or /provider-configs/tts/minimax",
        )
    return build_minimax_provider(api_key=api_key, model=cfg["model"]), cfg


def _voice_exists(connection, sha256_hex: str) -> dict | None:
    row = connection.execute(
        "SELECT * FROM minimax_voice_clones WHERE ref_audio_sha256=? AND enabled=1",
        (sha256_hex,),
    ).fetchone()
    return dict(row) if row else None


def create_router(get_db, ref_audio_dir: str | None = None, preview_dir: str | None = None):
    router = APIRouter(prefix="/minimax-voice-clones", tags=["minimax-voice-clones"])
    ref_root = Path(ref_audio_dir or Path(__file__).parent / "data" / "minimax_voice_clone_refs")
    preview_root = Path(preview_dir or Path(__file__).parent / "data" / "voice_previews" / "minimax_clone")
    ref_root.mkdir(parents=True, exist_ok=True)
    preview_root.mkdir(parents=True, exist_ok=True)

    @router.get("")
    def list_clones(enabled: bool | None = Query(default=None)):
        connection = get_db()
        try:
            if enabled is None:
                rows = connection.execute(
                    "SELECT * FROM minimax_voice_clones ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM minimax_voice_clones WHERE enabled=? ORDER BY created_at DESC",
                    (1 if enabled else 0,),
                ).fetchall()
            return [row_payload(row) for row in rows]
        finally:
            connection.close()

    @router.post("")
    async def create_clone(
        cloned_name: str = Form(..., max_length=120),
        ref_text: str = Form("", max_length=2000),
        sample_text: str = Form("", max_length=2000),
        language: str = Form("zh", max_length=16),
        ref_audio: UploadFile = File(...),
    ):
        if not ref_audio.filename:
            raise HTTPException(status_code=422, detail="ref_audio filename is required")
        ext = Path(ref_audio.filename).suffix.lower()
        if ext not in ALLOWED_AUDIO_EXT:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported reference audio extension {ext!r}; allowed: {sorted(ALLOWED_AUDIO_EXT)}",
            )

        new_uuid = str(uuid.uuid4())
        dest = ref_root / f"{new_uuid}{ext}"
        size = 0
        with dest.open("wb") as out:
            while True:
                chunk = await ref_audio.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_REF_AUDIO_BYTES:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Reference audio exceeds cap {MAX_REF_AUDIO_BYTES} bytes",
                    )
                out.write(chunk)
        if size < 1024:
            dest.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Reference audio too small (<1KB); upload a longer sample")

        # 算 sha256 (供 duplicate 检查 + 派生 voice_id)
        try:
            sha256_hex = sha256_of_file(dest)
        except OSError as exc:
            dest.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"Cannot read ref_audio: {exc}") from exc

        connection = get_db()
        try:
            provider, cfg = resolve_provider(connection)
            # 同 sha256 已有 → 直接返回旧记录 (避免重复调用 MiniMax clone)
            existing = _voice_exists(connection, sha256_hex)
            if existing:
                return {
                    "duplicate": True,
                    "voice": row_payload(existing),
                }

            # 调 MiniMax clone_voice
            try:
                clone = provider.clone_voice(
                    ref_audio_path=str(dest),
                    ref_text=ref_text.strip()[:2000],
                    language=(language or "zh").lower()[:16],
                )
            except ProviderError as exc:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=502, detail=f"MiniMax clone failed: {exc}") from exc

            now = now_epoch()
            connection.execute(
                "INSERT INTO minimax_voice_clones "
                "(id, uuid, cloned_name, ref_audio_path, ref_audio_sha256, ref_text, sample_text, language, voice_id, model, provider, enabled, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (
                    f"minimax_clone_{new_uuid}",
                    new_uuid,
                    cloned_name.strip()[:120],
                    str(dest),
                    sha256_hex,
                    ref_text.strip()[:2000],
                    sample_text.strip()[:2000] or ref_text.strip()[:2000],
                    (language or "zh").lower()[:16],
                    clone["voice_id"],
                    clone["model"],
                    "minimax",
                    now,
                    now,
                ),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM minimax_voice_clones WHERE uuid=?", (new_uuid,)
            ).fetchone()
            return {"duplicate": False, "voice": row_payload(row)}
        finally:
            connection.close()

    @router.get("/{voice_uuid}")
    def get_clone(voice_uuid: str):
        connection = get_db()
        try:
            row = connection.execute(
                "SELECT * FROM minimax_voice_clones WHERE uuid=?", (voice_uuid,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="MiniMax voice clone not found")
            return row_payload(row)
        finally:
            connection.close()

    @router.delete("/{voice_uuid}")
    def delete_clone(voice_uuid: str):
        connection = get_db()
        try:
            row = connection.execute(
                "SELECT * FROM minimax_voice_clones WHERE uuid=?", (voice_uuid,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="MiniMax voice clone not found")
            try:
                ref_path = Path(row["ref_audio_path"])
                if ref_root in ref_path.resolve().parents:
                    ref_path.unlink(missing_ok=True)
            except OSError:
                pass
            preview_file = preview_root / f"{voice_uuid}.mp3"
            preview_file.unlink(missing_ok=True)
            connection.execute(
                "DELETE FROM minimax_voice_clones WHERE uuid=?", (voice_uuid,)
            )
            connection.commit()
            return {"deleted": True, "uuid": voice_uuid}
        finally:
            connection.close()

    @router.post("/{voice_uuid}/preview")
    def preview_clone(voice_uuid: str, text: str | None = None):
        connection = get_db()
        try:
            row = connection.execute(
                "SELECT * FROM minimax_voice_clones WHERE uuid=? AND enabled=1",
                (voice_uuid,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Active MiniMax voice clone not found")
            provider, cfg = resolve_provider(connection)
            # 把 cache 预填, 避免一遍预览再走 upload
            provider.load_cache({row["ref_audio_sha256"]: row["voice_id"]})
            target_text = (text or row["sample_text"] or row["ref_text"] or "你好").strip()
            destination = preview_root / f"{voice_uuid}.mp3"
            try:
                result = provider.synthesize_with_voice_id(
                    target_text,
                    destination,
                    voice_id=row["voice_id"],
                    language=row["language"] or "zh",
                )
            except ProviderError as exc:
                raise HTTPException(status_code=502, detail=f"MiniMax preview failed: {exc}") from exc
            return {
                "uuid": voice_uuid,
                "provider": cfg.get("model") or "minimax",
                "base_url": cfg["base_url"],
                "preview_url": f"/voice-previews/minimax_clone/{voice_uuid}.mp3",
                "bytes": result["bytes"],
                "text": target_text,
            }
        finally:
            connection.close()

    @router.get("/provider/health")
    def provider_health():
        connection = get_db()
        try:
            cfg = fetch_minimax_config(connection)
            api_key = os.getenv("MINIMAX_API_KEY", "").strip()
            return {
                "provider": "minimax",
                "category": "tts",
                "configured": bool(api_key),
                "enabled": cfg["enabled"],
                "model": cfg.get("model"),
                "base_url": cfg.get("base_url"),
                "api_key_present": bool(api_key),
            }
        finally:
            connection.close()

    return router
