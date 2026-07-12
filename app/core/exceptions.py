"""全局异常处理。

统一后端错误响应格式，让 iOS/前端能以一致方式处理异常。
"""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _normalize_detail(detail):
    """将异常 detail 统一为前端可处理的格式。

    - 字符串：保持字符串
    - 字典/列表：保持原结构（用于 402 等需要结构化数据的场景）
    - 其他：转成字符串
    """
    if isinstance(detail, (str, dict, list)):
        return detail
    return str(detail)


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理 HTTPException，确保返回 JSON 且 detail 格式一致。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": _normalize_detail(exc.detail)},
        headers=getattr(exc, "headers", None) or {},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求参数校验失败（422）。"""
    # 提取第一条错误信息，避免返回过长的 FastAPI 默认结构
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = " -> ".join(str(x) for x in first.get("loc", []))
        msg = first.get("msg", "参数校验失败")
        message = f"{loc}: {msg}" if loc else msg
    else:
        message = "请求参数校验失败"

    return JSONResponse(
        status_code=422,
        content={"detail": message},
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """兜底：未捕获的异常返回 500，不暴露堆栈。"""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )
