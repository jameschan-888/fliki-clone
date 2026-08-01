# P8-OmniVoice: 本地 TTS provider (OpenAI 兼容协议), 走 OmniVoice-Studio :3900
# OmniVoice-Studio 是 debpalash/OmniVoice-Studio (AGPL-3.0), 自带 14 个 TTS 引擎 + 11 个 ASR
# + VoxCPM2 零样本声音克隆. 我们只通过 HTTP 调用, 不内嵌模型, 不污染许可证.
#
# 协议:
#   POST {base_url}/v1/audio/speech
#   body: {"model": "tts-1" | engine_id, "input": text, "voice": "alloy" | voice_id, ...}
#   -> audio bytes (mp3/wav/opus)
#
# 部署:
#   docker run -d --name omnivoice -p 127.0.0.1:3900:3900 ^
#     -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_DISABLE_XET=1 ^
#     -e OMNIVOICE_TTS_BACKEND=kittentts ^
#     -v D:/workspace/docker-volumes/omnivoice-data:/app/omnivoice_data ^
#     ghcr.io/debpalash/omnivoice-studio:latest
#   模型按需下载到 D 盘缓存; 健康检查: curl http://localhost:3900/health
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from providers.base import ProviderError, TTSProvider


DEFAULT_BASE_URL = "http://127.0.0.1:3900"
DEFAULT_MODEL = "tts-1"          # OpenAI 兼容默认
DEFAULT_VOICE = "alloy"          # OpenAI 兼容默认
DEFAULT_TIMEOUT = 60.0
MAX_AUDIO_BYTES = 32 * 1024 * 1024  # 32MB hard cap, 同 minimax_tts


class OmniVoiceTTSError(ProviderError):
    pass


def _env_base_url() -> str:
    return os.getenv("OMNIVOICE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _env_api_key() -> str | None:
    # OmniVoice 默认无鉴权; 暴露 OMNIVOICE_API_KEY 给反代场景 (caddy/nginx basic auth)
    return os.getenv("OMNIVOICE_API_KEY") or None


def _env_model() -> str:
    return os.getenv("OMNIVOICE_MODEL") or DEFAULT_MODEL


def _resolve_voice(voice):
    """voice 协议: 'omnivoice:<engine>:<voice_id>' -> 直接用 voice_id;
    其他: 原样传给 OmniVoice (用户已知 OmniVoice voice 命名)."""
    if not voice:
        return DEFAULT_VOICE
    if voice.startswith("omnivoice:"):
        rest = voice[len("omnivoice:"):]
        # omnivoice:<voice_id> 或 omnivoice:<engine>:<voice_id> 都接受
        return rest.split(":")[-1] or DEFAULT_VOICE
    return voice


def is_omnivoice_voice(voice):
    """检测 voice 是否显式指定走 OmniVoice (前缀 omnivoice:)."""
    return bool(voice) and str(voice).startswith("omnivoice:")


class OmniVoiceTTSProvider(TTSProvider):
    name = "omnivoice"

    def __init__(
        self,
        base_url=None,
        api_key=None,
        model=None,
        timeout=DEFAULT_TIMEOUT,
    ):
        self.base_url = (base_url or _env_base_url()).rstrip("/")
        self.api_key = api_key if api_key is not None else _env_api_key()
        self.model = model or _env_model()
        self.timeout = timeout

    def synthesize(self, text, destination, voice=None, **kwargs):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not text or not str(text).strip():
            raise OmniVoiceTTSError("OmniVoice TTS requires non-empty text")

        payload = {
            "model": self.model,
            "input": str(text).strip(),
            "voice": _resolve_voice(voice),
            "response_format": kwargs.get("response_format", "mp3"),
            "speed": kwargs.get("speed", 1.0),
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/v1/audio/speech"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.ConnectError as exc:
            raise OmniVoiceTTSError(
                f"OmniVoice unreachable at {self.base_url}: {exc}. "
                "Start with: docker run -d -p 127.0.0.1:3900:3900 "
                "-v D:/workspace/docker-volumes/omnivoice-data:/app/omnivoice_data "
                "ghcr.io/debpalash/omnivoice-studio:latest"
            ) from exc
        except httpx.HTTPError as exc:
            raise OmniVoiceTTSError(f"OmniVoice HTTP error: {exc}") from exc

        if resp.status_code != 200:
            err = (resp.text or "")[:300]
            raise OmniVoiceTTSError(
                f"OmniVoice TTS failed (status={resp.status_code}): {err}"
            )

        audio_bytes = resp.content
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise OmniVoiceTTSError(
                f"OmniVoice returned {len(audio_bytes)} bytes, exceeds {MAX_AUDIO_BYTES}"
            )
        if len(audio_bytes) < 256:
            raise OmniVoiceTTSError(
                f"OmniVoice returned suspiciously small audio: {len(audio_bytes)} bytes"
            )

        destination.write_bytes(audio_bytes)
        return {
            "provider": self.name,
            "voice": payload["voice"],
            "model": self.model,
            "local_path": str(destination),
            "bytes": len(audio_bytes),
        }


def build_omnivoice_provider(
    base_url=None,
    api_key=None,
    model=None,
    timeout=DEFAULT_TIMEOUT,
):
    return OmniVoiceTTSProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=timeout,
    )
