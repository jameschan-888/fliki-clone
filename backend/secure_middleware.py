"""rev35 P0-1: 安全头 + CORS 白名单.

- 默认响应追加 4 个安全头 (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, CSP).
- CORS 按 FLIKI_ALLOWED_ORIGINS (逗号分隔) 白名单放行; 未设置时仅允许默认本地前端.
- 单一 middleware 同时完成两件事, 避免与 FastAPI 内置 CORSMiddleware 重复设置.
"""
from __future__ import annotations

import os
from typing import Iterable

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


DEFAULT_ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://127.0.0.1:5180",
    "http://localhost:5180",
)


def _parse_origins(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_ALLOWED_ORIGINS)
    parts = [item.strip() for item in value.split(",")]
    return [item for item in parts if item]


def _build_csp() -> str:
    # rev35 起步策略: 默认 self, 允许本地 inline <script> 与 data: 媒体 (vite build 注入的 js 内联),
    # frame-ancestors 'none' 防 clickjacking. 后续按页面再加.
    return (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "font-src 'self' data:; "
        "connect-src 'self' ws: wss: http: https:; "
        "frame-ancestors 'none'"
    )


def install_security_middleware(app: FastAPI, allowed_origins: Iterable[str] | None = None) -> None:
    """安装安全头 + CORS 白名单中间件. 同源 / 没 Origin 头的请求直接放行."""
    origins = list(allowed_origins) if allowed_origins is not None else _parse_origins(os.environ.get("FLIKI_ALLOWED_ORIGINS"))
    origin_set = {o.rstrip("/") for o in origins}
    csp = _build_csp()

    class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next) -> Response:
            origin = request.headers.get("origin")
            normalized = origin.rstrip("/") if origin else None
            cors_allowed = normalized in origin_set if normalized else False

            response: Response = await call_next(request)

            response.headers.setdefault("x-content-type-options", "nosniff")
            response.headers.setdefault("x-frame-options", "DENY")
            response.headers.setdefault("referrer-policy", "no-referrer")
            response.headers.setdefault("content-security-policy", csp)
            response.headers.setdefault("permissions-policy", "geolocation=(), microphone=(), camera=()")

            if cors_allowed and normalized is not None:
                response.headers["access-control-allow-origin"] = normalized
                response.headers["vary"] = "Origin"
                response.headers.setdefault("access-control-allow-credentials", "true")
                response.headers.setdefault("access-control-allow-methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
                response.headers.setdefault("access-control-allow-headers", "Authorization, Content-Type, X-Request-ID")
                response.headers.setdefault("access-control-max-age", "600")

            if request.method == "OPTIONS" and cors_allowed:
                # CORS preflight: 直接返回 204, 不再走业务路由.
                return Response(status_code=204, headers=dict(response.headers))

            return response

    app.add_middleware(_SecurityHeadersMiddleware)
