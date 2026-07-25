# P5D-3 GPT-SoVITS HTTP adapter.
# Pure HTTP client; never embeds the model. Talks to a user-run GPT-SoVITS
# FastAPI service (default http://127.0.0.1:9880).
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from providers.base import ProviderError, TTSProvider


DEFAULT_BASE_URL = "http://127.0.0.1:9880"
DEFAULT_TIMEOUT = 30.0
MAX_AUDIO_BYTES = 32 * 1024 * 1024  # 32MB hard cap to bound disk/ram on weak hw


class GPTSoVITSError(ProviderError):
    pass


class GPTSoVITSProvider(TTSProvider):
    name = "gpt_sovits"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        endpoint: str = "/tts",
    ):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = float(timeout or DEFAULT_TIMEOUT)
        self.endpoint = "/" + endpoint.strip("/")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def synthesize(self, text: str, destination, voice: str | None = None) -> dict[str, Any]:
        # The base TTSProvider signature only takes (text, destination, voice).
        # For GPT-SoVITS we ALWAYS need reference audio + transcript; the caller
        # must use synthesize_with_refs(). We refuse plain calls to keep semantics
        # explicit instead of silently producing gibberish.
        raise ProviderError(
            "GPTSoVITSProvider requires synthesize_with_refs(text, destination, ref_audio_path, ref_text, language). "
            "The base synthesize(text, destination, voice) is unsupported for clone TTS."
        )

    def synthesize_with_refs(
        self,
        text: str,
        destination,
        ref_audio_path: str,
        ref_text: str,
        language: str = "zh",
        ref_language: str | None = None,
    ) -> dict[str, Any]:
        if not text or not str(text).strip():
            raise ProviderError("GPT-SoVITS synthesize requires non-empty text")
        if not ref_audio_path or not Path(ref_audio_path).exists():
            raise ProviderError(f"GPT-SoVITS reference audio not found: {ref_audio_path!r}")

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "ref_audio_path": str(ref_audio_path),
            "prompt_text": ref_text or "",
            "prompt_lang": self._lang_to_gpt(ref_language or language),
            "text": text,
            "text_lang": self._lang_to_gpt(language),
            "media_type": "wav",
            "streaming_mode": False,
        }

        try:
            response = httpx.post(
                f"{self.base_url}{self.endpoint}",
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise GPTSoVITSError(f"GPT-SoVITS HTTP call failed: {exc}") from exc

        if response.status_code >= 400:
            raise GPTSoVITSError(
                f"GPT-SoVITS returned HTTP {response.status_code}: {response.text[:200]}"
            )

        # GPT-SoVITS returns either a wav file or a JSON {audio: "<base64>"}.
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            try:
                body = response.json()
            except json.JSONDecodeError as exc:
                raise GPTSoVITSError(f"GPT-SoVITS returned invalid JSON: {exc}") from exc
            audio_b64 = body.get("audio") or body.get("data") or ""
            if not audio_b64:
                raise GPTSoVITSError("GPT-SoVITS JSON missing audio field")
            import base64
            audio_bytes = base64.b64decode(audio_b64)
        else:
            audio_bytes = response.content

        if not audio_bytes:
            raise GPTSoVITSError("GPT-SoVITS returned empty audio body")
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise GPTSoVITSError(
                f"GPT-SoVITS audio too large: {len(audio_bytes)} bytes > cap {MAX_AUDIO_BYTES}"
            )

        destination.write_bytes(audio_bytes)
        return {
            "provider": self.name,
            "voice": f"clone:{Path(ref_audio_path).stem}",
            "language": language,
            "local_path": str(destination),
            "bytes": len(audio_bytes),
        }

    def healthcheck(self) -> dict[str, Any]:
        started = time.time()
        try:
            response = httpx.get(f"{self.base_url}/", timeout=min(self.timeout, 5.0))
            latency_ms = int((time.time() - started) * 1000)
            ok = response.status_code < 500
            return {
                "base_url": self.base_url,
                "ok": ok,
                "latency_ms": latency_ms,
                "http_status": response.status_code,
                "error": None if ok else f"HTTP {response.status_code}",
            }
        except httpx.HTTPError as exc:
            return {
                "base_url": self.base_url,
                "ok": False,
                "latency_ms": int((time.time() - started) * 1000),
                "http_status": None,
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _lang_to_gpt(language):
        table = {
            "zh": "zh", "zh-cn": "zh", "zh-hans": "zh", "chinese": "zh",
            "en": "en", "en-us": "en", "en-gb": "en", "english": "en",
            "ja": "ja", "jp": "ja", "japanese": "ja",
            "ko": "ko", "kr": "ko", "korean": "ko",
        }
        return table.get((language or "").lower(), "zh")
