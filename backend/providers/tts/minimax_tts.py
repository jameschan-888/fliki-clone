# P7-1 MiniMax TTS HTTP adapter (cloud API, zero-dep).
# Pure HTTP client; never embeds the model. Talks to MiniMax T2A v2 API.
# Replaces Edge TTS (better quality / more languages / 8 model variants)
# and local GPT-SoVITS clone (no local GPU required).
#
# P7-Persist: voice_id cache now keyed by ref_audio SHA256 (not path).
# Persistence is the caller's job: feed entries via load_cache() at startup
# and write new entries via the public clone_voice() helper.
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import httpx

from providers.base import ProviderError, TTSProvider


DEFAULT_BASE_URL = "https://api.minimaxi.com"
DEFAULT_MODEL = "speech-02-turbo"
DEFAULT_TIMEOUT = 30.0
DEFAULT_VOICE = "male-qn-qingse"
MAX_AUDIO_BYTES = 32 * 1024 * 1024  # 32MB hard cap

# MiniMax voice_id 限制 8-256 字符; 派生值控制在 64 以内 (前缀 + 32 stem + 16 sha).
_VOICE_ID_MAX_LEN = 64


class MiniMaxTTSError(ProviderError):
    pass


def sha256_of_file(path: str | Path) -> str:
    """计算参考音频的 SHA256 (供 router 持久化时复用)."""
    p = Path(path)
    digest = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def derive_voice_id(sha256_hex: str, ref_path: Path) -> str:
    """基于 sha256 派生确定的 voice_id (跨进程/重启/路径变更仍稳定).
    ref_path 仅签名兼容, 实际只读 sha256_hex.
    """
    short = sha256_hex[:32].lower()
    voice_id = f"fliki_{short}".lower()
    return voice_id.replace("-", "_")[:_VOICE_ID_MAX_LEN]


class MiniMaxTTSProvider(TTSProvider):
    name = "minimax"

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
            raise ProviderError("MINIMAX_API_KEY not configured (set env var or pass api_key=)")
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.timeout = float(timeout or DEFAULT_TIMEOUT)
        # sha256_hex -> voice_id 缓存. 旧版用 path 作 key, 同一路径改了内容仍命中旧 voice_id
        # (实际上是用户感受到"声音丢了"). 持久化由 caller 负责 (load_cache at startup).
        self._voice_id_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Cache wiring (P7-Persist)
    # ------------------------------------------------------------------
    def load_cache(self, cache: dict[str, str]) -> None:
        """从持久化 (e.g. minimax_voice_clones 表) 预填 sha256 -> voice_id 缓存."""
        if not cache:
            return
        self._voice_id_cache.update(cache)

    def cache_snapshot(self) -> dict[str, str]:
        """导出当前缓存 (供 caller 落盘)."""
        return dict(self._voice_id_cache)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def synthesize(
        self,
        text: str,
        destination,
        voice: str | None = None,
    ) -> dict[str, Any]:
        """Plain TTS via T2A v2. voice=voice_id (system preset or pre-cloned id)."""
        if not text or not str(text).strip():
            raise ProviderError("MiniMax synthesize requires non-empty text")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "model": self.model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice or DEFAULT_VOICE,
                "speed": 1.0,
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }

        try:
            response = httpx.post(
                f"{self.base_url}/v1/t2a_v2",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise MiniMaxTTSError(f"MiniMax HTTP call failed: {exc}") from exc

        return self._parse_response(response, destination, voice or DEFAULT_VOICE, language="zh")

    def clone_voice(
        self,
        ref_audio_path: str,
        ref_text: str = "",
        language: str = "zh",
    ) -> dict[str, Any]:
        """上传 ref_audio + 调 voice_clone, 返回 {voice_id, sha256, cached, model}.
        缓存命中: 跳过 MiniMax API 直接返回 (caller 可以选择仍写表, 也可跳过).
        """
        if not ref_audio_path or not Path(ref_audio_path).exists():
            raise ProviderError(f"MiniMax reference audio not found: {ref_audio_path!r}")
        ref_path = Path(ref_audio_path)
        sha256_hex = sha256_of_file(ref_path)
        cached = self._voice_id_cache.get(sha256_hex)
        if cached:
            return {"voice_id": cached, "sha256": sha256_hex, "cached": True, "model": self.model}
        voice_id = self._upload_and_clone(ref_path, sha256_hex, ref_text, language)
        self._voice_id_cache[sha256_hex] = voice_id
        return {"voice_id": voice_id, "sha256": sha256_hex, "cached": False, "model": self.model}

    def synthesize_with_voice_id(
        self,
        text: str,
        destination,
        voice_id: str,
        language: str = "zh",
    ) -> dict[str, Any]:
        """用预克隆的 voice_id 合成音频 (不再上传)."""
        if not text or not str(text).strip():
            raise ProviderError("MiniMax synthesize_with_voice_id requires non-empty text")
        if not voice_id:
            raise ProviderError("MiniMax synthesize_with_voice_id requires voice_id")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": 1.0,
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }
        try:
            response = httpx.post(
                f"{self.base_url}/v1/t2a_v2",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise MiniMaxTTSError(f"MiniMax T2A call failed: {exc}") from exc
        return self._parse_response(response, destination, voice_id, language=language)

    def synthesize_with_refs(
        self,
        text: str,
        destination,
        ref_audio_path: str,
        ref_text: str = "",
        language: str = "zh",
        ref_language: str | None = None,
    ) -> dict[str, Any]:
        """向后兼容: clone + synthesize (旧 API).
        新代码请用 clone_voice() + synthesize_with_voice_id() 两步走, 配合 minimax_voice_clones router.
        """
        clone = self.clone_voice(ref_audio_path, ref_text, language)
        result = self.synthesize_with_voice_id(text, destination, clone["voice_id"], language=language)
        # 兼容性: 旧 API 在 voice 字段上加 clone: 前缀
        result["voice"] = f"clone:{clone['voice_id']}"
        return result

    def healthcheck(self) -> dict[str, Any]:
        started = time.time()
        try:
            payload = {
                "model": self.model,
                "text": "hi",
                "stream": False,
                "voice_setting": {"voice_id": DEFAULT_VOICE, "speed": 1.0, "vol": 1.0, "pitch": 0},
                "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
            }
            response = httpx.post(
                f"{self.base_url}/v1/t2a_v2",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=min(self.timeout, 8.0),
            )
            latency_ms = int((time.time() - started) * 1000)
            if response.status_code == 401:
                return {"base_url": self.base_url, "ok": False, "latency_ms": latency_ms,
                        "http_status": 401, "error": "invalid API key"}
            if response.status_code >= 500:
                return {"base_url": self.base_url, "ok": False, "latency_ms": latency_ms,
                        "http_status": response.status_code, "error": f"HTTP {response.status_code}"}
            if response.status_code >= 400:
                return {"base_url": self.base_url, "ok": False, "latency_ms": latency_ms,
                        "http_status": response.status_code, "error": response.text[:200]}
            try:
                body = response.json()
                ok = body.get("base_resp", {}).get("status_code") == 0
                err = None if ok else body.get("base_resp", {}).get("status_msg", "unknown")
            except Exception:
                ok = False
                err = "invalid JSON"
            return {"base_url": self.base_url, "ok": ok, "latency_ms": latency_ms,
                    "http_status": response.status_code, "error": err}
        except httpx.HTTPError as exc:
            return {"base_url": self.base_url, "ok": False,
                    "latency_ms": int((time.time() - started) * 1000),
                    "http_status": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _upload_and_clone(
        self,
        ref_path: Path,
        sha256_hex: str,
        ref_text: str,
        language: str,
    ) -> str:
        """上传 ref 音频 + 调 voice_clone, 返回 voice_id.
        派生 voice_id 用 sha256 (而非 path), 保证同一文件内容跨进程得到同一 voice_id.
        """
        try:
            with open(ref_path, "rb") as f:
                up_resp = httpx.post(
                    f"{self.base_url}/v1/files/upload",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (ref_path.name, f, "audio/mpeg")},
                    timeout=self.timeout,
                )
        except httpx.HTTPError as exc:
            raise MiniMaxTTSError(f"MiniMax upload failed: {exc}") from exc
        if up_resp.status_code >= 400:
            raise MiniMaxTTSError(f"MiniMax upload HTTP {up_resp.status_code}: {up_resp.text[:200]}")
        try:
            up_body = up_resp.json()
        except json.JSONDecodeError as exc:
            raise MiniMaxTTSError(f"MiniMax upload returned invalid JSON: {exc}") from exc
        file_id = (up_body.get("file", {}) or {}).get("file_id") or up_body.get("file_id")
        if not file_id:
            raise MiniMaxTTSError(f"MiniMax upload response missing file_id: {up_body}")

        voice_id = derive_voice_id(sha256_hex, ref_path)

        try:
            clone_resp = httpx.post(
                f"{self.base_url}/v1/voice_clone",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "file_id": file_id,
                    "voice_id": voice_id,
                    "prompt_text": ref_text or "",
                    "model": self.model,
                },
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise MiniMaxTTSError(f"MiniMax clone failed: {exc}") from exc
        if clone_resp.status_code >= 400:
            raise MiniMaxTTSError(f"MiniMax clone HTTP {clone_resp.status_code}: {clone_resp.text[:200]}")
        try:
            clone_body = clone_resp.json()
        except json.JSONDecodeError as exc:
            raise MiniMaxTTSError(f"MiniMax clone returned invalid JSON: {exc}") from exc
        base = clone_body.get("base_resp", {}) or {}
        if base.get("status_code", 0) != 0:
            raise MiniMaxTTSError(f"MiniMax clone failed: {base.get('status_msg','unknown')}")
        return voice_id

    def _parse_response(
        self,
        response: httpx.Response,
        destination: Path,
        voice: str,
        language: str,
    ) -> dict[str, Any]:
        if response.status_code == 401:
            raise MiniMaxTTSError("MiniMax auth failed (401): check MINIMAX_API_KEY")
        if response.status_code >= 400:
            raise MiniMaxTTSError(
                f"MiniMax returned HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise MiniMaxTTSError(f"MiniMax returned invalid JSON: {exc}") from exc

        base = body.get("base_resp", {}) or {}
        if base.get("status_code", 0) != 0:
            raise MiniMaxTTSError(
                f"MiniMax T2A failed: {base.get('status_msg', 'unknown')}"
            )

        hex_audio = (body.get("data", {}) or {}).get("audio", "")
        if not hex_audio:
            raise MiniMaxTTSError("MiniMax response missing data.audio")
        try:
            audio_bytes = bytes.fromhex(hex_audio)
        except ValueError as exc:
            raise MiniMaxTTSError(f"MiniMax audio is not valid hex: {exc}") from exc

        if not audio_bytes:
            raise MiniMaxTTSError("MiniMax returned empty audio body")
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise MiniMaxTTSError(
                f"MiniMax audio too large: {len(audio_bytes)} bytes > cap {MAX_AUDIO_BYTES}"
            )

        destination.write_bytes(audio_bytes)
        extra = body.get("extra_info", {}) or {}
        return {
            "provider": self.name,
            "voice": voice,
            "language": language,
            "local_path": str(destination),
            "bytes": len(audio_bytes),
            "audio_length_ms": extra.get("audio_length"),
        }
