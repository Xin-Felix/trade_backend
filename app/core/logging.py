"""统一日志配置。

为所有日志输出附加 request_id，支持纯文本和 JSON 两种格式，
便于排查问题时按请求链路追踪。
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """为每条日志注入当前请求的 request_id。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """结构化 JSON 日志格式器。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", "-"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """纯文本日志格式器。"""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def configure_logging(level: str = "INFO", json_format: bool = False) -> None:
    """配置根日志记录器。

    Args:
        level: 日志级别，如 DEBUG/INFO/WARNING/ERROR。
        json_format: 是否输出 JSON 结构化日志，生产环境建议开启。
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_format else TextFormatter())
    handler.addFilter(RequestIdFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    """获取已附加 request_id filter 的 logger。"""
    logger = logging.getLogger(name)
    logger.addFilter(RequestIdFilter())
    return logger


def set_request_id(request_id: str | None = None) -> str:
    """设置当前上下文的 request_id，返回实际使用的 id。"""
    rid = request_id or uuid.uuid4().hex[:16]
    request_id_var.set(rid)
    return rid
