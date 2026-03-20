"""统一的异常类体系 (C-01)

所有业务异常必须继承自基类，确保错误码和消息格式一致。
跨服务的错误码定义见 contracts/proto/common/error_code.proto。
"""

from typing import Any, Optional


class BasePlatformException(Exception):
    """平台基础异常"""

    def __init__(
        self,
        message: str,
        code: str = "ERR_UNKNOWN",
        user_message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.user_message = user_message or message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "user_message": self.user_message,
            "details": self.details,
        }


# ====== 通用错误 (10xxx) ======

class InvalidRequestError(BasePlatformException):
    def __init__(self, message: str, details=None):
        super().__init(message, code="ERR_INVALID_REQUEST", user_message="请求参数有误", details=details)


class UnauthorizedError(BasePlatformException):
    def __init__(self, message: str = "未授权"):
        super().__init(message, code="ERR_UNAUTHORIZED", user_message="请先登录")


class RateLimitedError(BasePlatformException):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            "请求过于频繁",
            code="ERR_RATE_LIMITED",
            user_message=f"请 {retry_after} 秒后重试",
            details={"retry_after": retry_after},
        )


class TimeoutError(BasePlatformException):
    def __init__(self, operation: str, timeout_s: float):
        super().__init__(
            f"{operation} 超时 ({timeout_s}s)",
            code="ERR_TIMEOUT",
            user_message="请求处理超时，请稍后重试",
            details={"operation": operation, "timeout_s": timeout_s},
        )


class ServiceUnavailableError(BasePlatformException):
    def __init__(self, service: str):
        super().__init__(
            f"服务 {service} 不可用",
            code="ERR_SERVICE_UNAVAILABLE",
            user_message="服务暂时不可用，请稍后重试",
            details={"service": service},
        )


# ====== Agent 编排错误 (20xxx) ======

class MaxStepsExceededError(BasePlatformException):
    def __init__(self, max_steps: int):
        super().__init__(
            f"超过最大步骤数 ({max_steps})",
            code="ERR_AGENT_MAX_STEPS_EXCEEDED",
            user_message="任务复杂度过高，已自动终止",
            details={"max_steps": max_steps},
        )


class ContextTooLongError(BasePlatformException):
    def __init__(self, current_tokens: int, max_tokens: int):
        super().__init__(
            f"上下文过长 ({current_tokens}/{max_tokens})",
            code="ERR_AGENT_CONTEXT_TOO_LONG",
            user_message="对话过长，请开启新会话",
            details={"current_tokens": current_tokens, "max_tokens": max_tokens},
        )


class ToolNotFoundError(BasePlatformException):
    def __init__(self, tool_name: str):
        super().__init__(
            f"工具不存在: {tool_name}",
            code="ERR_AGENT_TOOL_NOT_FOUND",
            user_message=f"系统内部错误：找不到工具 [{tool_name[:16]}]",
            details={"tool_name": tool_name},
        )


# ====== 模型网关错误 (30xxx) ======

class AllProvidersDownError(BasePlatformException):
    def __init__(self):
        super().__init__(
            "所有模型提供商不可用",
            code="ERR_MODEL_ALL_PROVIDERS_DOWN",
            user_message="AI 服务暂时不可用，请稍后重试",
        )


class ModelContentFilteredError(BasePlatformException):
    def __init__(self, reason: str = ""):
        super().__init__(
            f"内容被安全过滤: {reason}",
            code="ERR_MODEL_CONTENT_FILTERED",
            user_message="输入内容可能包含不当信息，请调整后重试",
            details={"reason": reason},
        )


class ModelTimeoutError(BasePlatformException):
    def __init__(self, timeout_s: float):
        super().__init__(
            f"模型调用超时 ({timeout_s}s)",
            code="ERR_MODEL_TIMEOUT",
            user_message="AI 响应超时，请稍后重试",
            details={"timeout_s": timeout_s},
        )


# ====== 工具总线错误 (40xxx) ======

class ToolValidationError(BasePlatformException):
    def __init__(self, tool_name: str, reason: str):
        super().__init__(
            f"工具参数校验失败 [{tool_name}]: {reason}",
            code="ERR_TOOL_VALIDATION_FAILED",
            user_message=f"参数不正确: {reason}",
            details={"tool_name": tool_name, "reason": reason},
        )


class ToolExecutionFailedError(BasePlatformException):
    def __init__(self, tool_name: str, reason: str):
        super().__init__(
            f"工具执行失败 [{tool_name}]: {reason}",
            code="ERR_TOOL_EXECUTION_FAILED",
            user_message="工具执行失败，请稍后重试",
            details={"tool_name": tool_name, "reason": reason},
        )


class ToolRiskRejectedError(BasePlatformException):
    def __init__(self, reason: str):
        super().__init__(
            f"操作被风控拒绝: {reason}",
            code="ERR_TOOL_RISK_REJECTED",
            user_message=f"该操作被安全策略阻止: {reason}",
            details={"reason": reason},
        )


class ApprovalRequiredError(BasePlatformException):
    def __init__(self, approval_id: str):
        super().__init__(
            f"需要人工审批: {approval_id}",
            code="ERR_TOOL_APPROVAL_REQUIRED",
            user_message="该操作需要人工审批，已提交审批申请",
            details={"approval_id": approval_id},
        )