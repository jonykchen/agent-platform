"""统一的异常类体系 (C-01)

【核心概念】为什么需要自定义异常体系？
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

在微服务架构中，异常处理需要解决以下问题：
1. 错误码统一：前后端、跨服务使用一致的错误码
2. 消息分离：技术信息（日志）vs 用户友好信息（前端展示）
3. 追踪关联：错误发生时携带 request_id 用于排查
4. 分类清晰：按模块/严重程度分类错误

【设计原则】
┌─────────────────────────────────────────────────────────────────────────┐
│  原则                │  实现方式                                       │
├──────────────────────┼──────────────────────────────────────────────────┤
│  单一继承根          │  所有异常继承 BasePlatformException              │
│  错误码规范          │  ERR_<模块>_<具体错误>，如 ERR_AGENT_MAX_STEPS  │
│  双消息机制          │  message（技术）+ user_message（用户友好）       │
│  详情携带            │  details 字典存储上下文信息                     │
│  模块分组            │  按错误码范围分组：10xxx(通用), 20xxx(Agent)...  │
└─────────────────────────────────────────────────────────────────────────┘

【错误码分类规范】
- 10xxx：通用错误（请求错误、认证、限流、超时）
- 20xxx：Agent 编排错误（步骤超限、上下文过长、工具不存在）
- 30xxx：模型网关错误（提供商不可用、内容过滤、超时）
- 40xxx：工具总线错误（参数校验、执行失败、风控拒绝）

【跨服务错误传递】
gRPC/HTTP 响应格式统一：
{
    "error": "ERR_CODE",
    "message": "技术信息（日志用）",
    "user_message": "用户友好信息（前端展示）",
    "details": {...}  // 可选的额外上下文
}

【与 Java 服务对齐】
错误码定义在 contracts/proto/common/error_code.proto，
Java 端使用 BusinessException，Python 端使用本模块，
确保跨服务错误码一致。

【参考】
- Google API 错误模型: https://cloud.google.com/apis/design/errors
- HTTP 状态码映射: 4xx 客户端错误, 5xx 服务端错误
"""

from typing import Any


class BasePlatformException(Exception):
    """平台基础异常 - 所有业务异常的基类

    【设计模式】Template Method + Information Expert

    子类只需提供特定参数，基类负责：
    1. 错误码标准化
    2. 默认用户消息生成
    3. to_dict() 序列化

    使用示例：
        # 直接抛出
        raise InvalidRequestError("订单号格式错误", details={"order_id": "xxx"})

        # 捕获并转换
        try:
            ...
        except SomeError as e:
            raise ToolExecutionFailedError("query_order", str(e)) from e

        # 响应格式化
        except BasePlatformException as e:
            return JSONResponse(status_code=400, content=e.to_dict())
    """

    # HTTP 状态码 - 异常处理中间件据此返回对应状态码（默认 400 客户端错误）
    # 子类可覆盖（如限流/配额超限 → 429，服务不可用 → 503）
    status_code: int = 400

    def __init__(
        self,
        message: str,
        code: str = "ERR_UNKNOWN",
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        # 技术信息 - 用于日志和调试
        self.message = message
        # 错误码 - 用于前端/客户端处理
        self.code = code
        # 用户友好信息 - 用于前端展示
        self.user_message = user_message or message
        # 额外上下文 - 用于问题排查
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为 API 响应格式

        用于 FastAPI 异常处理器返回 JSON 响应。
        """
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
    status_code = 429  # Too Many Requests

    def __init__(self, retry_after: int = 60):
        super().__init__(
            "请求过于频繁",
            code="ERR_RATE_LIMITED",
            user_message=f"请 {retry_after} 秒后重试",
            details={"retry_after": retry_after},
        )


class QuotaExceededError(BasePlatformException):
    status_code = 429  # Too Many Requests

    def __init__(self, message: str = "配额已用尽"):
        super().__init__(
            message,
            code="ERR_QUOTA_EXCEEDED",
            user_message="您的使用配额已用尽，请联系管理员",
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


class ToolBusUnavailableError(BasePlatformException):
    def __init__(self, reason: str = ""):
        super().__init__(
            f"工具总线服务不可用: {reason}",
            code="ERR_TOOLBUS_UNAVAILABLE",
            user_message="工具服务暂时不可用，请稍后重试",
            details={"reason": reason},
        )


class DatabaseError(BasePlatformException):
    def __init__(self, message: str, details=None):
        super().__init__(
            message,
            code="ERR_DATABASE_ERROR",
            user_message="数据服务异常，请稍后重试",
            details=details,
        )


class DatabaseConnectionError(BasePlatformException):
    def __init__(self, message: str):
        super().__init__(
            message,
            code="ERR_DATABASE_CONNECTION",
            user_message="数据服务连接失败，请稍后重试",
        )
