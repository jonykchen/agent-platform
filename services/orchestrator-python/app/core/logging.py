"""统一的日志配置模块 (M-01)

使用 structlog 作为结构化日志框架。
"""

import sys
import time

import structlog
from typing import Any, Optional


def setup_logging(
    environment: str = "production",
    log_level: str = "INFO",
    json_output: bool = True,
) -> None:
    """配置 structlog 日志

    Args:
        environment: dev/test/staging/prod
        log_level: 日志级别
        json_output: 是否输出 JSON 格式（生产环境必须 True）
    """

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _SensitiveDataProcessor(),
        _RequestContextProcessor(),
    ]

    if json_output or environment in ("production", "prod", "staging"):
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(sort_keys=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )
    else:
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )


class _SensitiveDataProcessor(structlog.types.Processor):
    """过滤日志中的敏感数据"""

    PATTERNS = {
        "phone": (r"1[3-9]\d{9}", lambda m: f"{m.group()[:3]}****{m.group()[-4:]}"),
        "id_card": (r"\d{17}[\dXx]", lambda m: f"{m.group()[:6]}********{m.group()[-4:]}"),
        "bank_card": (r"\d{16,19}", lambda m: f"****{m.group()[-4:]}"),
        "email": (r"[^@\s]+@[^@\s]+", lambda m: f"{m.group()[0]}***@{m.group().split('@')[1]}"),
    }

    def __call__(self, logger, method_name, event_dict):
        import re

        for key, value in event_dict.items():
            if isinstance(value, str):
                for field_type, (pattern, replacer) in self.PATTERNS.items():
                    value = re.sub(pattern, replacer, value)
                if len(value) > 500:
                    value = value[:500] + "... (truncated)"
                event_dict[key] = value
        return event_dict


class _RequestContextProcessor(structlog.types.Processor):
    """从上下文变量中提取 request_id / trace_id 等"""

    def __call__(self, logger, method_name, event_dict):
        try:
            from app.api.middleware.request_context import get_request_id, get_tenant_id, get_user_id
            event_dict.setdefault("request_id", get_request_id(""))
            event_dict.setdefault("tenant_id", get_tenant_id(""))
            event_dict.setdefault("user_id", get_user_id(""))
        except ImportError:
            pass
        return event_dict


# 全局 Logger
get_logger = structlog.get_logger