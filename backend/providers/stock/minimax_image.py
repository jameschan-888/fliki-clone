# P7-3 MiniMax Image HTTP adapter (cloud API, image-01).
# AI-generates still images from text prompts; replaces Pexels/Pixabay
# for custom-tailored scene visuals with full creative control.
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from providers.base import ProviderError, StockProvider


DEFAULT_BASE_URL = "https://api.minimaxi.com"
DEFAULT_MODEL = "image-01"
DEFAULT_TIMEOUT = 60.0
MAX_IMAGE_BYTES = 16 * 1024 * 1024  # 16MB cap
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_N = 1


class MiniMaxImageError(ProviderError):
    pass


class MiniMaxImageProvider(StockProvider):
    name = "minimax_image"

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

    def fetch(
        self,
        query: str,
        destination,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        prompt_optimizer: bool = True,
        n: int = DEFAULT_N,
    ) -> dict[str, Any]:
        if not query or not str(query).strip():
            raise ProviderError("MiniMax image fetch requires non-empty prompt")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "model": self.model,
            "prompt": query,
            "aspect_ratio": aspect_ratio,
            "response_format": "url",
            "n": max(1, min(n, 4)),
            "prompt_optimizer": prompt_optimizer,
        }

        try:
            response = httpx.post(
                f"{self.base_url}/v1/image_generation",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise MiniMaxImageError(f"MiniMax image HTTP call failed: {exc}") from exc

        return self._parse_response(response, destination, query)

    def healthcheck(self) -> dict[str, Any]:
        started = time.time()
        try:
            payload = {
                "model": self.model,
                "prompt": "blue sky",
                "aspect_ratio": "1:1",
                "response_format": "url",
                "n": 1,
                "prompt_optimizer": False,
            }
            response = httpx.post(
                f"{self.base_url}/v1/image_generation",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=min(self.timeout, 10.0),
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

    def _parse_response(self, response: httpx.Response, destination: Path, prompt: str) -> dict[str, Any]:
        if response.status_code == 401:
            raise MiniMaxImageError("MiniMax image auth failed (401)")
        if response.status_code >= 400:
            raise MiniMaxImageError(
                f"MiniMax image HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise MiniMaxImageError(f"MiniMax image invalid JSON: {exc}") from exc

        base = body.get("base_resp", {}) or {}
        if base.get("status_code", 0) != 0:
            raise MiniMaxImageError(
                f"MiniMax image failed: {base.get('status_msg', 'unknown')}"
            )

        data = body.get("data", {}) or {}
        # MiniMax 返回 image_urls 或 image_base64 数组 (n 张图)
        urls = data.get("image_urls") or data.get("urls") or []
        b64_list = data.get("image_base64") or data.get("base64") or []

        if urls:
            url = urls[0]
            try:
                r = httpx.get(url, timeout=self.timeout, follow_redirects=True)
                r.raise_for_status()
                image_bytes = r.content
                source_url = url
            except httpx.HTTPError as exc:
                raise MiniMaxImageError(f"MiniMax image URL fetch failed: {exc}") from exc
        elif b64_list:
            import base64
            try:
                image_bytes = base64.b64decode(b64_list[0])
                source_url = None
            except Exception as exc:
                raise MiniMaxImageError(f"MiniMax image base64 decode failed: {exc}") from exc
        else:
            raise MiniMaxImageError("MiniMax image response missing image_urls / image_base64")

        if not image_bytes:
            raise MiniMaxImageError("MiniMax image returned empty body")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise MiniMaxImageError(
                f"MiniMax image too large: {len(image_bytes)} > {MAX_IMAGE_BYTES}"
            )

        destination.write_bytes(image_bytes)
        return {
            "provider": self.name,
            "prompt": prompt,
            "source_url": source_url,
            "local_path": str(destination),
            "bytes": len(image_bytes),
            "n_requested": max(1, min(
                (body.get("metadata", {}) or {}).get("n", 1), 4
            )),
        }
