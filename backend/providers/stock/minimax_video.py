# P7-4 MiniMax Video HTTP adapter (cloud API, Hailuo-2.3).
# AI text-to-video generation (1080P, 6s). Submits async task, polls
# until completed, downloads MP4. Replaces Pexels/Pixabay stock video
# for fully custom AI-generated B-roll footage.
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from providers.base import ProviderError, StockProvider


DEFAULT_BASE_URL = "https://api.minimaxi.com"
DEFAULT_MODEL = "MiniMax-Hailuo-2.3"
DEFAULT_TIMEOUT = 30.0  # 单次 HTTP 超时
POLL_INTERVAL = 5.0
MAX_POLLS = 240  # 240 * 5s = 20 分钟上限
MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100MB cap


class MiniMaxVideoError(ProviderError):
    pass


class MiniMaxVideoProvider(StockProvider):
    """StockProvider 接口实现: 用 AI 文生视频替代 stock 视频.
    fetch(query, destination) 会阻塞最长 20 分钟等待生成完成."""
    name = "minimax_video"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = POLL_INTERVAL,
        max_polls: int = MAX_POLLS,
    ):
        import os
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
        if not self.api_key:
            raise ProviderError("MINIMAX_API_KEY not configured")
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.timeout = float(timeout or DEFAULT_TIMEOUT)
        self.poll_interval = float(poll_interval or POLL_INTERVAL)
        self.max_polls = int(max_polls or MAX_POLLS)

    def fetch(
        self,
        query: str,
        destination,
        duration: int = 6,
        resolution: str = "1080P",
    ) -> dict[str, Any]:
        if not query or not str(query).strip():
            raise ProviderError("MiniMax video fetch requires non-empty prompt")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        # 1) 提交任务
        submit_payload = {
            "model": self.model,
            "prompt": query,
            "duration": max(1, min(duration, 10)),  # 通常 6
            "resolution": resolution if resolution in ("768P", "1080P") else "1080P",
        }
        try:
            submit_resp = httpx.post(
                f"{self.base_url}/v1/video_generation",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=submit_payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise MiniMaxVideoError(f"MiniMax video submit HTTP error: {exc}") from exc

        if submit_resp.status_code == 401:
            raise MiniMaxVideoError("MiniMax video auth failed (401)")
        if submit_resp.status_code >= 400:
            raise MiniMaxVideoError(
                f"MiniMax video submit HTTP {submit_resp.status_code}: {submit_resp.text[:200]}"
            )
        try:
            submit_body = submit_resp.json()
        except json.JSONDecodeError as exc:
            raise MiniMaxVideoError(f"MiniMax video submit invalid JSON: {exc}") from exc

        base = submit_body.get("base_resp", {}) or {}
        if base.get("status_code", 0) != 0:
            raise MiniMaxVideoError(
                f"MiniMax video submit failed: {base.get('status_msg', 'unknown')}"
            )

        task_id = (submit_body.get("task_id")
                   or submit_body.get("data", {}).get("task_id")
                   or submit_body.get("id"))
        if not task_id:
            raise MiniMaxVideoError(f"MiniMax video submit missing task_id: {submit_body}")

        # 2) 轮询直到完成 (最常见: Preparing/Processing/Success/Failed)
        status_payload = None
        final_body = None
        for attempt in range(1, self.max_polls + 1):
            try:
                poll_resp = httpx.post(
                    f"{self.base_url}/v1/video_generation/{task_id}",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={},
                    timeout=self.timeout,
                )
            except httpx.HTTPError as exc:
                raise MiniMaxVideoError(f"MiniMax video poll HTTP error: {exc}") from exc

            if poll_resp.status_code == 401:
                raise MiniMaxVideoError("MiniMax video poll auth failed (401)")
            if poll_resp.status_code >= 500:
                # 暂时性错误, 继续轮询
                time.sleep(self.poll_interval)
                continue
            if poll_resp.status_code >= 400:
                raise MiniMaxVideoError(
                    f"MiniMax video poll HTTP {poll_resp.status_code}: {poll_resp.text[:200]}"
                )
            try:
                final_body = poll_resp.json()
            except json.JSONDecodeError as exc:
                time.sleep(self.poll_interval)
                continue

            status_payload = final_body.get("status") or final_body.get("data", {}).get("status")
            base_resp = final_body.get("base_resp", {}) or {}
            if base_resp.get("status_code", 0) != 0:
                # 任务级错误
                err_msg = base_resp.get("status_msg", "unknown")
                if status_payload in ("Failed", "FAIL", "failed"):
                    raise MiniMaxVideoError(f"MiniMax video task failed: {err_msg}")
                # 暂时性, 继续轮询
            if status_payload in ("Success", "SUCCESS", "success", "completed", "COMPLETED"):
                break
            if status_payload in ("Failed", "FAIL", "failed"):
                raise MiniMaxVideoError(f"MiniMax video task failed: {base_resp.get('status_msg', status_payload)}")
            time.sleep(self.poll_interval)
        else:
            raise MiniMaxVideoError(f"MiniMax video poll timeout after {self.max_polls} attempts")

        # 3) 提取 video_url / file_id / hex
        data = final_body.get("data", {}) or {}
        video_url = (data.get("video_url") or data.get("url")
                     or final_body.get("video_url") or final_body.get("file", {}).get("url"))
        hex_video = data.get("video") or final_body.get("video")

        if video_url:
            try:
                r = httpx.get(video_url, timeout=self.timeout, follow_redirects=True)
                r.raise_for_status()
                video_bytes = r.content
            except httpx.HTTPError as exc:
                raise MiniMaxVideoError(f"MiniMax video URL fetch failed: {exc}") from exc
        elif hex_video:
            try:
                video_bytes = bytes.fromhex(hex_video)
            except ValueError as exc:
                raise MiniMaxVideoError(f"MiniMax video not valid hex: {exc}") from exc
        else:
            raise MiniMaxVideoError("MiniMax video response missing video_url / video hex")

        if not video_bytes:
            raise MiniMaxVideoError("MiniMax video returned empty body")
        if len(video_bytes) > MAX_VIDEO_BYTES:
            raise MiniMaxVideoError(
                f"MiniMax video too large: {len(video_bytes)} > {MAX_VIDEO_BYTES}"
            )

        destination.write_bytes(video_bytes)
        return {
            "provider": self.name,
            "prompt": query,
            "duration_seconds": submit_payload["duration"],
            "resolution": submit_payload["resolution"],
            "task_id": task_id,
            "source_url": video_url,
            "local_path": str(destination),
            "bytes": len(video_bytes),
            "poll_attempts": attempt,
        }

    def healthcheck(self) -> dict[str, Any]:
        # Video healthcheck 只验提交接口 (不能真生成 6s 视频)
        started = time.time()
        if not self.api_key:
            return {"base_url": self.base_url, "ok": False, "latency_ms": 0,
                    "http_status": None, "error": "MINIMAX_API_KEY not set", "model": self.model}
        try:
            payload = {
                "model": self.model,
                "prompt": "blue sky",
                "duration": 6,
                "resolution": "720P",
            }
            r = httpx.post(
                f"{self.base_url}/v1/video_generation",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=min(self.timeout, 10.0),
            )
            latency_ms = int((time.time() - started) * 1000)
            if r.status_code == 401:
                return {"base_url": self.base_url, "ok": False, "latency_ms": latency_ms,
                        "http_status": 401, "error": "invalid API key", "model": self.model}
            if r.status_code >= 500:
                return {"base_url": self.base_url, "ok": False, "latency_ms": latency_ms,
                        "http_status": r.status_code, "error": f"server HTTP {r.status_code}", "model": self.model}
            if r.status_code >= 400:
                return {"base_url": self.base_url, "ok": False, "latency_ms": latency_ms,
                        "http_status": r.status_code, "error": r.text[:200], "model": self.model}
            try:
                body = r.json()
                ok = body.get("base_resp", {}).get("status_code") == 0
                err = None if ok else body.get("base_resp", {}).get("status_msg", "unknown")
            except Exception:
                ok = False
                err = "invalid JSON"
            return {"base_url": self.base_url, "ok": ok, "latency_ms": latency_ms,
                    "http_status": r.status_code, "error": err, "model": self.model}
        except httpx.HTTPError as exc:
            return {"base_url": self.base_url, "ok": False,
                    "latency_ms": int((time.time() - started) * 1000),
                    "http_status": None, "error": str(exc), "model": self.model}
