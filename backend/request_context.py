"""rev35 P0-2: Request ID + JSON access log.

- 中间件读 X-Request-ID 头, 缺失时生成 req-<8 hex>; 写入 response header.
- 每个请求结束后通过 fliki.access logger 输出一行 JSON (method/path/status/duration_ms/request_id/remote).
- 通过 contextvars 暴露当前请求 ID, 业务代码可读取并写进错误响应.
"""
from __future__ import annotations

import json
import logging
import re
import secrets
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{4,128}$")
_current_request_id: ContextVar[str] = ContextVar("fliki_request_id", default="")
_access_logger = logging.getLogger("fliki.access")


def current_request_id() -> str:
    return _current_request_id.get()


def _new_request_id() -> str:
    return "req-" + uuid.uuid4().hex[:8]


def _normalize(value: str | None) -> str:
    if not value:
        return _new_request_id()
    candidate = value.strip()
    if not REQUEST_ID_PATTERN.match(candidate):
        return _new_request_id()
    return candidate


def install_request_context(app) -> None:
    class _RequestContextMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next) -> Response:
            request_id = _normalize(request.headers.get(REQUEST_ID_HEADER))
            token = _current_request_id.set(request_id)
            start = time.perf_counter()
            try:
                response: Response = await call_next(request)
            except Exception:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                _access_logger.info(
                    json.dumps(
                        {
                            "request_id": request_id,
                            "method": request.method,
                            "path": request.url.path,
                            "status": 500,
                            "duration_ms": round(elapsed_ms, 2),
                            "remote": request.client.host if request.client else None,
                            "error": "unhandled",
                        },
                        ensure_ascii=False,
                    )
                )
                _current_request_id.reset(token)
                raise
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            response.headers[REQUEST_ID_HEADER] = request_id
            _access_logger.info(
                json.dumps(
                    {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": round(elapsed_ms, 2),
                        "remote": request.client.host if request.client else None,
                    },
                    ensure_ascii=False,
                )
            )
            _current_request_id.reset(token)
            return response

    app.add_middleware(_RequestContextMiddleware)
