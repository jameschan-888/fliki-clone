"""rev24 阶段 D D2-1: 统一错误响应格式.

所有 4xx/5xx 响应统一为 {error_code, message, hint, details, status} 结构.
前端 ApiError 类型 + formatApiError(err, fallback) helper 见 app/src/api/errors.ts.
"""
from typing import Any, Dict, Optional
from fastapi import HTTPException

# ====== 错误码常量 (snake_case, 前端可枚举) ======
# 400
ERR_BAD_REQUEST = "BAD_REQUEST"
# 401
ERR_INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
ERR_MISSING_TOKEN = "MISSING_TOKEN"
ERR_TOKEN_EXPIRED = "TOKEN_EXPIRED"
# 403
ERR_ADMIN_ONLY = "ADMIN_ONLY"
ERR_FORBIDDEN = "FORBIDDEN"
# 404
ERR_NOT_FOUND = "NOT_FOUND"
ERR_USER_NOT_FOUND = "USER_NOT_FOUND"
ERR_RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
# 409
ERR_CONFLICT = "CONFLICT"
ERR_EMAIL_EXISTS = "EMAIL_EXISTS"
ERR_ALREADY_EXISTS = "ALREADY_EXISTS"
ERR_INVALID_STATE = "INVALID_STATE"
MOCK_PROVIDER_BLOCKS_RELEASE = "MOCK_PROVIDER_BLOCKS_RELEASE"
ERR_MOCK_PROVIDER_BLOCKS_RELEASE = MOCK_PROVIDER_BLOCKS_RELEASE
# 422
ERR_VALIDATION_ERROR = "VALIDATION_ERROR"
# 429
ERR_RATE_LIMITED = "RATE_LIMITED"
# 500
ERR_INTERNAL_ERROR = "INTERNAL_ERROR"
# 502/503
ERR_PROVIDER_DOWN = "PROVIDER_DOWN"
ERR_SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
# 兜底
ERR_UNKNOWN = "UNKNOWN_ERROR"


# ====== 状态码 -> 默认 error_code ======
DEFAULT_ERROR_CODE_BY_STATUS = {
    400: ERR_BAD_REQUEST,
    401: ERR_MISSING_TOKEN,
    403: ERR_FORBIDDEN,
    404: ERR_NOT_FOUND,
    409: ERR_CONFLICT,
    422: ERR_VALIDATION_ERROR,
    429: ERR_RATE_LIMITED,
    500: ERR_INTERNAL_ERROR,
    502: ERR_PROVIDER_DOWN,
    503: ERR_SERVICE_UNAVAILABLE,
}


def make_error_response(
    status_code: int,
    error_code=None,
    message=None,
    hint=None,
    details=None,
):
    """构造统一错误响应体 (status 必填, 其他字段给空默认值)."""
    return {
        "error_code": error_code or DEFAULT_ERROR_CODE_BY_STATUS.get(status_code, ERR_UNKNOWN),
        "message": message or "",
        "hint": hint or "",
        "details": details or {},
        "status": status_code,
    }


class LingjianError(HTTPException):
    def __init__(self, error_code, message, hint="", details=None, status_code=400):
        self.error_code = error_code
        self.message = message
        self.hint = hint
        self.details = details or {}
        super().__init__(
            status_code=status_code,
            detail=make_error_response(status_code, error_code, message, hint, self.details),
        )


def normalize_http_exception_detail(detail):
    """把 FastAPI HTTPException 的 detail 转成统一格式.

    - dict 形态: 透传 (假设已经按 {error_code, message, hint, details} 写),
                 缺省字段补空, status 后续由 handler 填
    - str 形态: 包成默认格式, error_code 由 handler 按 status_code 填
    - None/其他: 用空 message
    """
    if isinstance(detail, dict):
        return {
            "error_code": detail.get("error_code", "") or "",
            "message": detail.get("message", "") or "",
            "hint": detail.get("hint", "") or "",
            "details": detail.get("details", {}) or {},
            "status": detail.get("status", 0) or 0,
        }
    elif isinstance(detail, str):
        return {
            "error_code": "",
            "message": detail,
            "hint": "",
            "details": {},
            "status": 0,
        }
    else:
        return {
            "error_code": "",
            "message": str(detail) if detail is not None else "",
            "hint": "",
            "details": {},
            "status": 0,
        }



def register_error_handlers(app):
    """rev24 阶段 D D2-1: 把 3 个 exception handler 注册到 FastAPI app.

    - HTTPException (所有 4xx/5xx 抛出) -> 统一 error_code + message + hint + details + status
    - RequestValidationError (pydantic 验证失败) -> 422 + VALIDATION_ERROR + details.errors
    - Exception (兜底) -> 500 + INTERNAL_ERROR (不泄露 stack)
    """
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(HTTPException)
    async def _http_handler(request, exc):
        body = normalize_http_exception_detail(exc.detail)
        if not body["error_code"]:
            body["error_code"] = DEFAULT_ERROR_CODE_BY_STATUS.get(exc.status_code, ERR_UNKNOWN)
        body["status"] = exc.status_code
        headers = getattr(exc, "headers", None)
        return JSONResponse(status_code=exc.status_code, content=body, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request, exc):
        return JSONResponse(
            status_code=422,
            content=make_error_response(
                422,
                ERR_VALIDATION_ERROR,
                "请求参数验证失败",
                "检查 body / query / path 参数, 对照 API 文档",
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content=make_error_response(
                500,
                ERR_INTERNAL_ERROR,
                "服务器内部错误",
                "查看后端日志 / 联系管理员",
                {"path": str(request.url.path) if request else ""},
            ),
        )
