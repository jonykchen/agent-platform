"""异常到 gRPC Status 的映射

将 Python 异常转换为 gRPC StatusCode 和 ErrorDetail。

【核心概念】gRPC 错误处理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

gRPC 使用 Status 对象传递错误信息：
- code: 状态码（如 INVALID_ARGUMENT、UNAVAILABLE）
- details: 详细错误消息

Python 侧需要：
1. 捕获业务异常
2. 映射到合适的 StatusCode
3. 创建 ErrorDetail proto 消息
4. 调用 context.abort() 终止请求

【映射规则】
┌─────────────────────────────────────────────────────────────────────────┐
│ Python Exception              │ gRPC StatusCode                      │
├───────────────────────────────┼───────────────────────────────────────┤
│ InvalidRequestError           │ INVALID_ARGUMENT                      │
│ UnauthorizedError             │ UNAUTHENTICATED                       │
│ RateLimitedError              │ RESOURCE_EXHAUSTED                    │
│ TimeoutError                  │ DEADLINE_EXCEEDED                     │
│ ServiceUnavailableError       │ UNAVAILABLE                           │
│ MaxStepsExceededError         │ FAILED_PRECONDITION                   │
│ ToolNotFoundError             │ NOT_FOUND                             │
│ 其他 BasePlatformException     │ INTERNAL                              │
│ 其他异常                      │ INTERNAL                              │
└─────────────────────────────────────────────────────────────────────────┘

【参考】
- gRPC Status: https://grpc.github.io/grpc/python/grpc.html#grpc.StatusCode
- Google API 错误模型: https://cloud.google.com/apis/design/errors
"""

from typing import Tuple

import grpc
import structlog

from app.gen.common import error_code_pb2
from app.core.exceptions import (
    BasePlatformException,
    InvalidRequestError,
    UnauthorizedError,
    RateLimitedError,
    TimeoutError,
    ServiceUnavailableError,
    MaxStepsExceededError,
    ContextTooLongError,
    ToolNotFoundError,
    AllProvidersDownError,
    ModelContentFilteredError,
    ModelTimeoutError,
    ToolValidationError,
    ToolExecutionFailedError,
    ToolRiskRejectedError,
    ApprovalRequiredError,
    ToolBusUnavailableError,
)

logger = structlog.get_logger()


# 错误码字符串到枚举的映射
_ERROR_CODE_MAP = {
    "ERR_INVALID_REQUEST": error_code_pb2.ERR_INVALID_REQUEST,
    "ERR_UNAUTHORIZED": error_code_pb2.ERR_UNAUTHORIZED,
    "ERR_FORBIDDEN": error_code_pb2.ERR_FORBIDDEN,
    "ERR_NOT_FOUND": error_code_pb2.ERR_NOT_FOUND,
    "ERR_RATE_LIMITED": error_code_pb2.ERR_RATE_LIMITED,
    "ERR_TIMEOUT": error_code_pb2.ERR_TIMEOUT,
    "ERR_SERVICE_UNAVAILABLE": error_code_pb2.ERR_SERVICE_UNAVAILABLE,
    "ERR_INTERNAL": error_code_pb2.ERR_INTERNAL,
    "ERR_AGENT_MAX_STEPS_EXCEEDED": error_code_pb2.ERR_AGENT_MAX_STEPS_EXCEEDED,
    "ERR_AGENT_CONTEXT_TOO_LONG": error_code_pb2.ERR_AGENT_CONTEXT_TOO_LONG,
    "ERR_AGENT_TOOL_NOT_FOUND": error_code_pb2.ERR_AGENT_TOOL_NOT_FOUND,
    "ERR_MODEL_ALL_PROVIDERS_DOWN": error_code_pb2.ERR_MODEL_ALL_PROVIDERS_DOWN,
    "ERR_MODEL_CONTENT_FILTERED": error_code_pb2.ERR_MODEL_CONTENT_FILTERED,
    "ERR_MODEL_TIMEOUT": error_code_pb2.ERR_MODEL_TIMEOUT,
    "ERR_TOOL_VALIDATION_FAILED": error_code_pb2.ERR_TOOL_VALIDATION_FAILED,
    "ERR_TOOL_EXECUTION_FAILED": error_code_pb2.ERR_TOOL_EXECUTION_FAILED,
    "ERR_TOOL_RISK_REJECTED": error_code_pb2.ERR_TOOL_RISK_REJECTED,
    "ERR_TOOL_APPROVAL_REQUIRED": error_code_pb2.ERR_TOOL_APPROVAL_REQUIRED,
    "ERR_TOOLBUS_UNAVAILABLE": error_code_pb2.ERR_TOOL_NOT_AVAILABLE,
}


def map_exception_to_grpc_status(
    exc: Exception,
    request_id: str = "",
    trace_id: str = "",
) -> Tuple[grpc.StatusCode, str]:
    """将异常映射到 gRPC Status

    Args:
        exc: Python 异常
        request_id: 请求 ID（用于追踪）
        trace_id: OpenTelemetry Trace ID

    Returns:
        (StatusCode, details_message)
    """
    # 记录异常日志
    logger.error(
        "grpc_exception",
        error_type=type(exc).__name__,
        message=str(exc),
        request_id=request_id,
    )

    # 通用错误 (10xxx)
    if isinstance(exc, InvalidRequestError):
        return grpc.StatusCode.INVALID_ARGUMENT, exc.message

    if isinstance(exc, UnauthorizedError):
        return grpc.StatusCode.UNAUTHENTICATED, exc.message

    if isinstance(exc, RateLimitedError):
        return grpc.StatusCode.RESOURCE_EXHAUSTED, exc.user_message

    if isinstance(exc, TimeoutError):
        return grpc.StatusCode.DEADLINE_EXCEEDED, exc.message

    if isinstance(exc, ServiceUnavailableError):
        return grpc.StatusCode.UNAVAILABLE, exc.message

    # Agent 编排错误 (20xxx)
    if isinstance(exc, MaxStepsExceededError):
        return grpc.StatusCode.FAILED_PRECONDITION, exc.message

    if isinstance(exc, ContextTooLongError):
        return grpc.StatusCode.FAILED_PRECONDITION, exc.message

    if isinstance(exc, ToolNotFoundError):
        return grpc.StatusCode.NOT_FOUND, exc.message

    # 模型网关错误 (30xxx)
    if isinstance(exc, AllProvidersDownError):
        return grpc.StatusCode.UNAVAILABLE, exc.message

    if isinstance(exc, ModelContentFilteredError):
        return grpc.StatusCode.FAILED_PRECONDITION, exc.message

    if isinstance(exc, ModelTimeoutError):
        return grpc.StatusCode.DEADLINE_EXCEEDED, exc.message

    # 工具总线错误 (40xxx)
    if isinstance(exc, ToolValidationError):
        return grpc.StatusCode.INVALID_ARGUMENT, exc.message

    if isinstance(exc, ToolExecutionFailedError):
        return grpc.StatusCode.INTERNAL, exc.message

    if isinstance(exc, ToolRiskRejectedError):
        return grpc.StatusCode.PERMISSION_DENIED, exc.message

    if isinstance(exc, ApprovalRequiredError):
        return grpc.StatusCode.FAILED_PRECONDITION, exc.message

    if isinstance(exc, ToolBusUnavailableError):
        return grpc.StatusCode.UNAVAILABLE, exc.message

    # 其他平台异常
    if isinstance(exc, BasePlatformException):
        return grpc.StatusCode.INTERNAL, exc.message

    # 未知异常
    return grpc.StatusCode.INTERNAL, f"Internal error: {str(exc)}"


def create_error_detail(
    exc: BasePlatformException,
    request_id: str = "",
    trace_id: str = "",
    service: str = "orchestrator-python",
) -> error_code_pb2.ErrorDetail:
    """创建 ErrorDetail protobuf 消息

    Args:
        exc: 平台异常
        request_id: 请求 ID
        trace_id: 追踪 ID
        service: 来源服务名

    Returns:
        ErrorDetail 消息
    """
    import time

    # 映射错误码
    code = _ERROR_CODE_MAP.get(exc.code, error_code_pb2.ERR_UNKNOWN)

    return error_code_pb2.ErrorDetail(
        code=code,
        message=exc.message,
        user_message=exc.user_message,
        request_id=request_id,
        trace_id=trace_id,
        timestamp=int(time.time() * 1000),
        service=service,
    )
