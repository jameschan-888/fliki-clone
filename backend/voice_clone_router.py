# P5D-3 Voice Clones CRUD + preview against GPT-SoVITS.
# All external HTTP calls are guarded so the import path stays usable in tests
# even when no GPT-SoVITS service is running on the host.
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

from providers.base import ProviderError
from providers.tts import (
    build_gpt_sovits_provider,
    detect_provider_for_voice,
    GPT_SOVITS_CLONE_PREFIX,
)
from provider_config import provider_payload, seed_runtime_providers


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
        "ref_text": base["ref_text"],
        "sample_text": base["sample_text"],
        "language": base["language"],
        "enabled": bool(base["enabled"]),
        "voice": f"{GPT_SOVITS_CLONE_PREFIX}{base['uuid']}",
        "created_at": base["created_at"],
    }


def fetch_provider_config(connection, name: str = "gpt_sovits") -> dict:
    seed_runtime_providers(connection)
    row = connection.execute(
        "SELECT * FROM provider_configs WHERE category='tts' AND name=?",
        (name,),
    ).fetchone()
    if row is None:
        return {"base_url": None, "enabled": False, "model": None, "configured": False}
    config = json.loads(row["config_json"] or "{}")
    env_override = os.getenv("FLIKI_GPT_SOVITS_URL", "").strip()
    return {
        "base_url": env_override or config.get("base_url"),
        "enabled": bool(row["enabled"]),
        "is_default": bool(row["is_default"]),
        "model": config.get("model"),
        "configured": True,
    }


def resolve_provider(connection) -> tuple:
    cfg = fetch_provider_config(connection)
    if not cfg["base_url"]:
        raise HTTPException(status_code=422, detail="GPT-SoVITS provider has no base_url; configure it via /provider-configs/tts/gpt_sovits")
    return build_gpt_sovits_provider(base_url=cfg["base_url"]), cfg


def create_router(get_db, ref_audio_dir: str | None = None, preview_dir: str | None = None):
    router = APIRouter(prefix="/voice-clones", tags=["voice-clones"])
    ref_root = Path(ref_audio_dir or Path(__file__).parent / "data" / "voice_clone_refs")
    preview_root = Path(preview_dir or Path(__file__).parent / "data" / "voice_previews" / "clone")
    ref_root.mkdir(parents=True, exist_ok=True)
    preview_root.mkdir(parents=True, exist_ok=True)

    @router.get("")
    def list_clones(enabled: bool | None = Query(default=None)):
        connection = get_db()
        try:
            seed_runtime_providers(connection)
            if enabled is None:
                rows = connection.execute(
                    "SELECT * FROM voice_clones ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM voice_clones WHERE enabled=? ORDER BY created_at DESC",
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

        connection = get_db()
        try:
            seed_runtime_providers(connection)
            connection.execute(
                "INSERT INTO voice_clones (id, uuid, cloned_name, ref_audio_path, ref_text, sample_text, language, enabled, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    f"clone_{new_uuid}",
                    new_uuid,
                    cloned_name.strip()[:120],
                    str(dest),
                    ref_text.strip()[:2000],
                    sample_text.strip()[:2000] or ref_text.strip()[:2000],
                    (language or "zh").lower()[:16],
                    now_epoch(),
                ),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM voice_clones WHERE uuid=?", (new_uuid,)
            ).fetchone()
            return row_payload(row)
        finally:
            connection.close()

    @router.get("/{voice_uuid}")
    def get_clone(voice_uuid: str):
        connection = get_db()
        try:
            row = connection.execute(
                "SELECT * FROM voice_clones WHERE uuid=?", (voice_uuid,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Voice clone not found")
            return row_payload(row)
        finally:
            connection.close()

    @router.delete("/{voice_uuid}")
    def delete_clone(voice_uuid: str):
        connection = get_db()
        try:
            row = connection.execute(
                "SELECT * FROM voice_clones WHERE uuid=?", (voice_uuid,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Voice clone not found")
            # Remove ref file if it lives under our managed ref_root
            try:
                ref_path = Path(row["ref_audio_path"])
                if ref_root in ref_path.resolve().parents:
                    ref_path.unlink(missing_ok=True)
            except OSError:
                pass
            preview_file = preview_root / f"{voice_uuid}.mp3"
            preview_file.unlink(missing_ok=True)
            connection.execute("DELETE FROM voice_clones WHERE uuid=?", (voice_uuid,))
            connection.commit()
            return {"deleted": True, "uuid": voice_uuid}
        finally:
            connection.close()

    @router.post("/{voice_uuid}/preview")
    def preview_clone(voice_uuid: str, text: str | None = None):
        connection = get_db()
        try:
            row = connection.execute(
                "SELECT * FROM voice_clones WHERE uuid=? AND enabled=1", (voice_uuid,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Active voice clone not found")
            provider, cfg = resolve_provider(connection)
            target_text = (text or row["sample_text"] or row["ref_text"] or "你好").strip()
            destination = preview_root / f"{voice_uuid}.mp3"
            try:
                result = provider.synthesize_with_refs(
                    target_text,
                    destination,
                    ref_audio_path=row["ref_audio_path"],
                    ref_text=row["ref_text"],
                    language=row["language"] or "zh",
                )
            except ProviderError as exc:
                raise HTTPException(status_code=502, detail=f"GPT-SoVITS preview failed: {exc}") from exc
            return {
                "uuid": voice_uuid,
                "provider": cfg.get("model") or "gpt_sovits",
                "base_url": cfg["base_url"],
                "preview_url": f"/voice-previews/clone/{voice_uuid}.mp3",
                "bytes": result["bytes"],
                "text": target_text,
            }
        finally:
            connection.close()

    @router.get("/provider/health")
    def provider_health():
        connection = get_db()
        try:
            provider, cfg = resolve_provider(connection)
            return {"configured": True, **provider.healthcheck(), "model": cfg.get("model")}
        except HTTPException:
            raise
        finally:
            connection.close()
        import sys; print("PROV_HEALTH called", file=sys.stderr, flush=True)
        connection = get_db()
        try:
            provider, cfg = resolve_provider(connection)
            return {"configured": True, **provider.healthcheck(), "model": cfg.get("model")}
        except HTTPException:
            raise
        finally:
            connection.close()

    return router
