"""日志配置

【G-SEC-02】集成敏感信息脱敏过滤器
"""

import sys
import re

import structlog


def setup_logging(environment: str = "production", debug: bool = False) -> None:
    """配置 structlog 日志"""

    json_output = environment in ("production", "prod", "staging")

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _SensitiveDataProcessor(),  # 敏感信息脱敏
    ]

    if json_output:
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.JSONRenderer(sort_keys=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger("INFO"),
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        )
    else:
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger("DEBUG"),
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        )


class _SensitiveDataProcessor(structlog.types.Processor):
    """过滤日志中的敏感数据

    【G-SEC-02】敏感信息必须脱敏
    """

    PATTERNS = {
        "phone": (r"1[3-9]\d{9}", lambda m: f"{m.group()[:3]}****{m.group()[-4:]}"),
        "id_card": (r"\d{17}[\dXx]", lambda m: f"{m.group()[:6]}********{m.group()[-4:]}"),
        "bank_card": (r"\d{16,19}", lambda m: f"****{m.group()[-4:]}"),
        "email": (r"[^@\s]+@[^@\s]+", lambda m: f"{m.group()[0]}***@{m.group().split('@')[1]}"),
        "api_key": (r"(?:sk-|api[_-]?key[_-]?)[a-zA-Z0-9]{20,}", lambda m: f"{m.group()[:4]}...{'*' * (len(m.group()) - 4)}"),
    }

    SENSITIVE_FIELDS = {
        "password", "passwd", "pwd", "secret", "token",
        "api_key", "apikey", "authorization", "auth",
        "credential", "private_key", "privatekey",
    }

    def __call__(self, logger, method_name, event_dict):
        for key, value in event_dict.items():
            # 敏感字段名直接隐藏
            if key.lower() in self.SENSITIVE_FIELDS:
                event_dict[key] = "********"
                continue

            if isinstance(value, str):
                for field_type, (pattern, replacer) in self.PATTERNS.items():
                    value = re.sub(pattern, replacer, value)
                if len(value) > 500:
                    value = value[:500] + "... (truncated)"
                event_dict[key] = value
        return event_dict


get_logger = structlog.get_logger