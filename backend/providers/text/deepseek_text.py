"""DeepSeek 文本 provider (OpenAI 兼容协议).

DeepSeek API 与 OpenAI Chat Completions 兼容, 直接复用 httpx POST.
env: DEEPSEEK_API_KEY, 默认 base_url = https://api.deepseek.com
model: deepseek-chat (默认) / deepseek-reasoner (R1) / deepseek-coder.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from providers.base import ProviderError, TextProvider

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 1.0


class DeepSeekError(ProviderError):
    pass


class DeepSeekTextProvider(TextProvider):
    name = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise ProviderError("DEEPSEEK_API_KEY not configured")
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.timeout = float(timeout or DEFAULT_TIMEOUT)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> dict[str, Any]:
        if not prompt or not str(prompt).strip():
            raise ProviderError("DeepSeek generate requires non-empty prompt")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max(1, min(int(max_tokens or DEFAULT_MAX_TOKENS), 8192)),
            "temperature": float(temperature if temperature is not None else DEFAULT_TEMPERATURE),
            "stream": False,
        }

        try:
            response = httpx.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers={
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        except httpx.HTTPError as e:
            raise DeepSeekError(f"DeepSeek HTTP error: {e}") from e

        if response.status_code >= 400:
            raise DeepSeekError(f"DeepSeek API {response.status_code}: {response.text[:300]}")

        try:
            data = response.json()
        except ValueError as e:
            raise DeepSeekError(f"DeepSeek non-JSON response: {response.text[:200]}") from e

        choices = data.get("choices") or []
        if not choices:
            raise DeepSeekError(f"DeepSeek empty choices: {data}")
        content = (choices[0].get("message") or {}).get("content") or ""
        return {
            "content": content,
            "model": data.get("model", self.model),
            "usage": data.get("usage") or {},
        }
