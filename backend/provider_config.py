import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

SECRET_ENV = {
    ("stock", "pexels"): "PEXELS_API_KEY",
    ("stock", "pixabay"): "PIXABAY_API_KEY",
    ("music", "freesound"): "FREESOUND_API_KEY",
}


def now_epoch():
    return int(datetime.now(timezone.utc).timestamp())


def mask_secret(value):
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-4:]}"


class ProviderUpdateBody(BaseModel):
    enabled: bool | None = None
    is_default: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    base_url: str | None = Field(default=None, max_length=1000)
    model: str | None = Field(default=None, max_length=200)
    api_key: str | None = Field(default=None, max_length=4000)
    extra: dict | None = None


def provider_secret(category, name, config):
    env_name = config.get("api_key_env") or SECRET_ENV.get((category, name))
    return os.getenv(env_name, "") if env_name else ""


def provider_payload(row):
    config = json.loads(row["config_json"] or "{}")
    secret = provider_secret(row["category"], row["name"], config)
    return {
        "id": row["id"], "category": row["category"], "name": row["name"],
        "enabled": bool(row["enabled"]), "is_default": bool(row["is_default"]),
        "priority": row["priority"], "base_url": config.get("base_url"),
        "model": config.get("model"), "extra": config.get("extra", {}),
        "has_api_key": bool(secret), "api_key_masked": mask_secret(secret), "is_mock": bool(config.get("is_mock", False)),
    }


def seed_runtime_providers(connection):
    providers = [
        ("provider_stock_pexels", "stock", "pexels", 1, 1, 0, {"api_key_env":"PEXELS_API_KEY","base_url":"https://api.pexels.com"}),
        ("provider_stock_pixabay", "stock", "pixabay", 1, 0, 10, {"api_key_env":"PIXABAY_API_KEY","base_url":"https://pixabay.com/api"}),
        ("provider_tts_edge", "tts", "edge_tts", 1, 1, 0, {"model":"zh-CN-XiaoxiaoNeural"}),
        ("provider_tts_gpt_sovits", "tts", "gpt_sovits", 0, 0, 50, {"base_url":"http://127.0.0.1:9880","model":"GPT-SoVITS-v2","api_key_env":"FLIKI_GPT_SOVITS_URL"}),
        ("provider_avatar_wav2lip", "avatar", "wav2lip_onnx", 0, 1, 0, {"model_path":"data/models/wav2lip_onnx","ffmpeg_binary":"ffmpeg","auto_download":False,"fps":25.0,"max_dimension":320}),
        ("provider_music_freesound", "music", "freesound", 1, 1, 0, {"api_key_env":"FREESOUND_API_KEY","base_url":"https://freesound.org/apiv2"}),
        ("provider_music_silence", "music", "silence", 1, 0, 100, {}),
        ("provider_text_mock", "text", "mock", 1, 1, 100, {"is_mock": True}),
        ("provider_stock_mock", "stock", "mock", 1, 0, 100, {"is_mock": True}),
        ("provider_tts_mock", "tts", "mock", 1, 0, 100, {"is_mock": True}),
        ("provider_music_mock", "music", "mock", 1, 0, 100, {"is_mock": True}),
        ("provider_avatar_mock", "avatar", "mock", 1, 0, 100, {"is_mock": True}),
    ]
    for row in providers:
        connection.execute("INSERT OR IGNORE INTO provider_configs (id, category, name, enabled, is_default, priority, config_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (*row[:-1], json.dumps(row[-1]), now_epoch()))
    connection.commit()


def create_router(get_db):
    router=APIRouter(prefix="/provider-configs",tags=["provider-configs"])

    @router.get("")
    def list_configs(category: str | None = None):
        connection=get_db()
        try:
            seed_runtime_providers(connection)
            if category:
                rows=connection.execute("SELECT * FROM provider_configs WHERE category=? ORDER BY priority,name",(category,)).fetchall()
            else:
                rows=connection.execute("SELECT * FROM provider_configs ORDER BY category,priority,name").fetchall()
            return [provider_payload(row) for row in rows]
        finally: connection.close()

    @router.put("/{category}/{name}")
    def update_config(category: str,name: str,body: ProviderUpdateBody):
        connection=get_db()
        try:
            seed_runtime_providers(connection)
            row=connection.execute("SELECT * FROM provider_configs WHERE category=? AND name=?",(category,name)).fetchone()
            if row is None: raise HTTPException(status_code=404,detail="Provider config not found")
            config=json.loads(row["config_json"] or "{}")
            if body.api_key is not None:
                env_name=config.get("api_key_env") or SECRET_ENV.get((category,name))
                if not env_name: raise HTTPException(status_code=422,detail="This provider has no local API key slot")
                os.environ[env_name]=body.api_key
            for field in ("base_url","model","extra"):
                value=getattr(body,field)
                if value is not None: config[field]=value
            enabled=row["enabled"] if body.enabled is None else int(body.enabled)
            is_default=row["is_default"] if body.is_default is None else int(body.is_default)
            priority=row["priority"] if body.priority is None else body.priority
            if is_default:
                connection.execute("UPDATE provider_configs SET is_default=0 WHERE category=?",(category,))
            connection.execute("UPDATE provider_configs SET enabled=?,is_default=?,priority=?,config_json=? WHERE id=?",(enabled,is_default,priority,json.dumps(config),row["id"]))
            connection.commit()
            return provider_payload(connection.execute("SELECT * FROM provider_configs WHERE id=?",(row["id"],)).fetchone())
        finally: connection.close()

    return router
