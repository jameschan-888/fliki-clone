# P7-2 MiniMax Music HTTP adapter (cloud API, music-3.0).
# AI-generates BGM with optional lyrics; replaces Freesound stock with
# truly custom / copyright-clean background music.
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from providers.base import MusicProvider, ProviderError


DEFAULT_BASE_URL = "https://api.minimaxi.com"
DEFAULT_MODEL = "music-3.0"
DEFAULT_TIMEOUT = 60.0
MAX_AUDIO_BYTES = 32 * 1024 * 1024  # 32MB cap


class MiniMaxMusicError(ProviderError):
    pass


class MiniMaxMusicProvider(MusicProvider):
    name = "minimax_music"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        import os
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
        if not self.api_key:
            raise ProviderError("MINIMAX_API_KEY not configured")
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.timeout = float(timeout or DEFAULT_TIMEOUT)

    # ------------------------------------------------------------------
    # Public API (MusicProvider.fetch signature, extended with lyrics=)
    # ------------------------------------------------------------------
    def fetch(
        self,
        query: str,
        destination,
        lyrics: str | None = None,
        duration_seconds: int | None = None,
    ) -> dict[str, Any]:
        if not query or not str(query).strip():
            raise ProviderError("MiniMax music fetch requires non-empty query (style prompt)")

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "model": self.model,
            "prompt": query,
            "audio_setting": {
                "sample_rate": 44100,
                "bitrate": 256000,
                "format": "mp3",
            },
        }
        if lyrics:
            payload["lyrics"] = lyrics
        if duration_seconds:
            payload["duration"] = duration_seconds

        try:
            response = httpx.post(
                f"{self.base_url}/v1/music_generation",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise MiniMaxMusicError(f"MiniMax music HTTP call failed: {exc}") from exc

        return self._parse_response(response, destination, query, lyrics)

    def healthcheck(self) -> dict[str, Any]:
        started = time.time()
        try:
            payload = {
                "model": self.model,
                "prompt": "calm piano, 5 second loop",
                "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3"},
            }
            response = httpx.post(
                f"{self.base_url}/v1/music_generation",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=min(self.timeout, 12.0),
            )
            latency_ms = int((time.time() - started) * 1000)
            if response.status_code == 401:
                return {"base_url": self.base_url, "ok": False, "latency_ms": latency_ms,
                        "http_status": 401, "error": "invalid API key", "model": self.model}
            if response.status_code >= 500:
                return {"base_url": self.base_url, "ok": False, "latency_ms": latency_ms,
                        "http_status": response.status_code, "error": f"server HTTP {response.status_code}", "model": self.model}
            if response.status_code >= 400:
                return {"base_url": self.base_url, "ok": False, "latency_ms": latency_ms,
                        "http_status": response.status_code, "error": response.text[:200], "model": self.model}
            try:
                body = response.json()
                ok = body.get("base_resp", {}).get("status_code") == 0
                err = None if ok else body.get("base_resp", {}).get("status_msg", "unknown")
            except Exception:
                ok = False
                err = "invalid JSON"
            return {"base_url": self.base_url, "ok": ok, "latency_ms": latency_ms,
                    "http_status": response.status_code, "error": err, "model": self.model}
        except httpx.HTTPError as exc:
            return {"base_url": self.base_url, "ok": False,
                    "latency_ms": int((time.time() - started) * 1000),
                    "http_status": None, "error": str(exc), "model": self.model}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _parse_response(
        self, response: httpx.Response, destination: Path, prompt: str, lyrics: str | None
    ) -> dict[str, Any]:
        if response.status_code == 401:
            raise MiniMaxMusicError("MiniMax music auth failed (401)")
        if response.status_code >= 400:
            raise MiniMaxMusicError(
                f"MiniMax music HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise MiniMaxMusicError(f"MiniMax music invalid JSON: {exc}") from exc

        base = body.get("base_resp", {}) or {}
        if base.get("status_code", 0) != 0:
            raise MiniMaxMusicError(
                f"MiniMax music failed: {base.get('status_msg', 'unknown')}"
            )

        # 响应字段: data.audio (hex) 或 data.audio_url (URL)
        data = body.get("data", {}) or {}
        hex_audio = data.get("audio", "")
        audio_url = data.get("audio_url", "") or data.get("url", "")

        if hex_audio:
            try:
                audio_bytes = bytes.fromhex(hex_audio)
            except ValueError as exc:
                raise MiniMaxMusicError(f"MiniMax music audio not valid hex: {exc}") from exc
        elif audio_url:
            # 下载 URL 版本
            try:
                r = httpx.get(audio_url, timeout=self.timeout)
                r.raise_for_status()
                audio_bytes = r.content
            except httpx.HTTPError as exc:
                raise MiniMaxMusicError(f"MiniMax music URL fetch failed: {exc}") from exc
        else:
            raise MiniMaxMusicError("MiniMax music response missing data.audio / data.audio_url")

        if not audio_bytes:
            raise MiniMaxMusicError("MiniMax music returned empty audio body")
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise MiniMaxMusicError(
                f"MiniMax music audio too large: {len(audio_bytes)} > {MAX_AUDIO_BYTES}"
            )

        destination.write_bytes(audio_bytes)
        extra = body.get("extra_info", {}) or {}
        return {
            "provider": self.name,
            "prompt": prompt,
            "lyrics": lyrics,
            "local_path": str(destination),
            "bytes": len(audio_bytes),
            "audio_length_ms": extra.get("audio_length"),
        }
