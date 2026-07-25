from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class ErrorResult:
    error_code: str
    message_zh: str
    hint: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class LingjianError(Exception):
    """统一错误类型，借鉴灵剪 packages/core/errors.py。

    - error_code: 机器可读，便于前端按码展示/国际化。
    - message_zh: 中文用户消息。
    - hint: 修复方向。
    - details: 任意上下文（field / value / path 等）。
    """

    def __init__(self, error_code: str, message_zh: str, hint: str = "", details: dict[str, Any] | None = None, status_code: int = 400):
        super().__init__(message_zh)
        self.error_code = error_code
        self.message_zh = message_zh
        self.hint = hint
        self.details = details or {}
        self.status_code = status_code

    def to_result(self) -> ErrorResult:
        return ErrorResult(self.error_code, self.message_zh, self.hint, self.details)


# ===== 常用错误码（与后端语义对齐）=====
MOCK_PROVIDER_BLOCKS_RELEASE = "MOCK_PROVIDER_BLOCKS_RELEASE"
PROVIDER_NOT_FOUND = "PROVIDER_NOT_FOUND"
PROVIDER_CONFIG_INVALID = "PROVIDER_CONFIG_INVALID"
DRAFT_NOT_FOUND = "DRAFT_NOT_FOUND"
DRAFT_NOT_EDITABLE = "DRAFT_NOT_EDITABLE"
DRAFT_NOT_CONFIRMED = "DRAFT_NOT_CONFIRMED"
DRAFT_EMPTY = "DRAFT_EMPTY"
SCENE_NOT_FOUND = "SCENE_NOT_FOUND"
LANGUAGE_VOICE_MISMATCH = "LANGUAGE_VOICE_MISMATCH"
RUN_NOT_FOUND = "RUN_NOT_FOUND"
RUN_NOT_FAILED = "RUN_NOT_FAILED"
RENDER_JOB_NOT_FOUND = "RENDER_JOB_NOT_FOUND"
UPLOAD_NOT_FOUND = "UPLOAD_NOT_FOUND"
MEDIA_NOT_FOUND = "MEDIA_NOT_FOUND"
PATH_UNSAFE = "PATH_UNSAFE"


def to_http_exception(error: LingjianError) -> HTTPException:
    """把 LingjianError 转 FastAPI HTTPException，detail 用机器码 + 提示的字典。"""
    detail = {
        "error_code": error.error_code,
        "message_zh": error.message_zh,
        "hint": error.hint,
        "details": error.details,
    }
    return HTTPException(status_code=error.status_code, detail=detail)


def register_error_handlers(app: FastAPI) -> None:
    """在 FastAPI app 上挂统一错误处理。

    - LingjianError：转统一响应体 {error_code, message, hint, details}。
    - HTTPException：保留 FastAPI 默认 detail，但额外加 error_code=MAPPING_BY_STATUS。
    - 其他未捕获异常：返回 500 + UNKNOWN_ERROR，hint 指向 server log。
    """
    @app.exception_handler(LingjianError)
    async def _lingjian_handler(_request: Request, exc: LingjianError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message_zh,
                "hint": exc.hint,
                "details": exc.details,
            },
        )

    @app.exception_handler(HTTPException)
    async def _http_handler(_request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error_code" in detail:
            payload = {
                "error_code": detail.get("error_code"),
                "message": detail.get("message_zh") or str(detail.get("message") or ""),
                "hint": detail.get("hint", ""),
                "details": detail.get("details", {}),
            }
        else:
            payload = {
                "error_code": _status_to_error_code(exc.status_code),
                "message": str(detail) if detail is not None else "",
                "hint": "",
                "details": {},
            }
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def _generic_handler(_request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "UNKNOWN_ERROR",
                "message": str(exc)[:500] or exc.__class__.__name__,
                "hint": "请查看后端日志获取完整堆栈。",
                "details": {"exception": exc.__class__.__name__},
            },
        )


_STATUS_TO_CODE = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
}


def _status_to_error_code(status: int) -> str:
    return _STATUS_TO_CODE.get(status, f"HTTP_{status}")
