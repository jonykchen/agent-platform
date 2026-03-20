"""日志配置"""

import sys

import structlog


def setup_logging(environment: str = "production", debug: bool = False) -> None:
    """配置 structlog 日志"""

    json_output = environment in ("production", "prod", "staging")

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
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


get_logger = structlog.get_logger
