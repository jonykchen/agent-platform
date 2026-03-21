"""模型网关异常类"""

from typing import Any, Optional


class BaseGatewayException(Exception):
    """网关基础异常"""

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


class AllProvidersDownError(BaseGatewayException):
    """所有提供商不可用"""

    def __init__(self):
        super().__init__(
            "所有模型提供商不可用",
            code="ERR_MODEL_ALL_PROVIDERS_DOWN",
            user_message="AI 服务暂时不可用，请稍后重试",
        )


class ModelTimeoutError(BaseGatewayException):
    """模型调用超时"""

    def __init__(self, timeout_s: float):
        super().__init__(
            f"模型调用超时 ({timeout_s}s)",
            code="ERR_MODEL_TIMEOUT",
            user_message="AI 响应超时，请稍后重试",
            details={"timeout_s": timeout_s},
        )


class ModelContentFilteredError(BaseGatewayException):
    """内容被安全过滤"""

    def __init__(self, reason: str = ""):
        super().__init__(
            f"内容被安全过滤: {reason}",
            code="ERR_MODEL_CONTENT_FILTERED",
            user_message="输入内容可能包含不当信息，请调整后重试",
            details={"reason": reason},
        )


class ProviderUnavailableError(BaseGatewayException):
    """单个提供商不可用"""

    def __init__(self, provider: str, reason: str = ""):
        super().__init__(
            f"提供商 {provider} 不可用: {reason}",
            code="ERR_PROVIDER_UNAVAILABLE",
            user_message="AI 服务暂时不可用，正在尝试其他服务",
            details={"provider": provider, "reason": reason},
        )


class InvalidModelRequestError(BaseGatewayException):
    """无效的模型请求"""

    def __init__(self, message: str, details=None):
        super().__init__(
            message,
            code="ERR_INVALID_MODEL_REQUEST",
            user_message="请求参数有误",
            details=details,
        )


class RateLimitExceededError(BaseGatewayException):
    """请求频率超限"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            f"请求过于频繁",
            code="ERR_RATE_LIMIT_EXCEEDED",
            user_message=f"请 {retry_after} 秒后重试",
            details={"retry_after": retry_after},
        )
