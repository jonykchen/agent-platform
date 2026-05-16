"""Model Gateway 异常类体系

【核心概念】为什么需要自定义异常体系？
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Model Gateway 作为模型统一入口，异常处理需要解决：
1. 多提供商错误统一：不同提供商的错误码和消息格式不一致
2. 用户友好提示：技术错误转换为用户可理解的提示
3. 故障隔离与降级：单个提供商故障不影响整体服务
4. 可观测性：异常携带足够信息用于问题排查

【异常层次结构图】
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                      BaseGatewayException                               │
│                      (网关基础异常)                                      │
│                            │                                            │
│            ┌───────────────┼───────────────┬───────────────┐           │
│            │               │               │               │           │
│            ▼               ▼               ▼               ▼           │
│  AllProvidersDownError  ModelTimeoutError  ModelContent  Provider     │
│  (所有提供商不可用)       (调用超时)        FilteredError  Unavailable │
│                                           (内容过滤)      Error        │
│                                           │               (单提供商)    │
│                                           │                            │
│                                           ▼                            │
│                                    InvalidModelRequestError            │
│                                    (无效请求)                          │
│                                            │                           │
│                                            ▼                           │
│                                    RateLimitExceededError              │
│                                    (频率超限)                          │
└─────────────────────────────────────────────────────────────────────────┘

【错误码规范表】
┌──────────────────┬─────────────────────────────┬─────────────────────┐
│  错误码           │  含义                       │  HTTP 状态码         │
├──────────────────┼─────────────────────────────┼─────────────────────┤
│  ERR_MODEL_*     │  模型相关错误               │  502/503/504        │
│  ERR_PROVIDER_*   │  提供商相关错误             │  503                │
│  ERR_RATE_LIMIT  │  限流错误                   │  429                │
│  ERR_INVALID_*   │  参数校验错误               │  400                │
│  ERR_TIMEOUT     │  超时错误                   │  504                │
└──────────────────┴─────────────────────────────┴─────────────────────┘

【异常处理最佳实践】
1. 捕获与转换：捕获底层异常后转换为网关异常
   ```python
   try:
       response = await provider.call()
   except httpx.TimeoutError as e:
       raise ModelTimeoutError(timeout_s=self.config.timeout) from e
   ```

2. 错误聚合：多个提供商失败时聚合错误信息
   ```python
   raise AllProvidersDownError() from last_exception
   ```

3. 用户友好：始终提供 user_message
   - message：技术信息，用于日志和调试
   - user_message：用户友好信息，用于前端展示

4. 携带上文：使用 details 存储排查所需信息
   ```python
   raise ProviderUnavailableError(
       provider="qwen",
       reason=f"HTTP {status_code}: {error_body}"
   )
   ```

【跨服务错误传递】
HTTP 响应格式统一：
{
    "error": "ERR_MODEL_TIMEOUT",
    "message": "模型调用超时 (30s)",
    "user_message": "AI 响应超时，请稍后重试",
    "details": {"timeout_s": 30}
}

【与 Orchestrator 对齐】
Orchestrator 定义了更完整的异常体系（见 orchestrator/app/core/exceptions.py），
Model Gateway 异常应与 Orchestrator 的 ERR_MODEL_* 系列对齐。

【参考】
- Google API 错误模型: https://cloud.google.com/apis/design/errors
- HTTP 状态码映射: 4xx 客户端错误, 5xx 服务端错误
"""

from typing import Any


class BaseGatewayException(Exception):
    """网关基础异常 - 所有网关异常的基类

    【设计模式】Template Method + Information Expert

    子类只需提供特定参数，基类负责：
    1. 错误码标准化
    2. 默认用户消息生成
    3. to_dict() 序列化

    使用示例：
        # 直接抛出
        raise ModelTimeoutError(timeout_s=30)

        # 捕获并转换
        try:
            await call_provider()
        except ProviderUnavailableError as e:
            logger.warning(f"Provider failed: {e.details}")
            # 尝试下一个提供商...

        # 响应格式化
        except BaseGatewayException as e:
            return JSONResponse(status_code=503, content=e.to_dict())
    """

    def __init__(
        self,
        message: str,
        code: str = "ERR_UNKNOWN",
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        # 技术信息 - 用于日志和调试
        # 包含足够的技术细节，便于问题排查
        self.message = message

        # 错误码 - 用于前端/客户端处理
        # 格式：ERR_<模块>_<具体错误>
        self.code = code

        # 用户友好信息 - 用于前端展示
        # 不包含技术细节，用户可理解的建议
        self.user_message = user_message or message

        # 额外上下文 - 用于问题排查
        # 存储请求 ID、提供商名称、超时时间等
        self.details = details or {}

        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为 API 响应格式

        用于 FastAPI 异常处理器返回 JSON 响应。
        与 Orchestrator 响应格式保持一致。
        """
        return {
            "error": self.code,
            "message": self.message,
            "user_message": self.user_message,
            "details": self.details,
        }


# ─────────────────────────────────────────────────────────────────────────
# 提供商级错误 - 所有提供商都不可用
# ─────────────────────────────────────────────────────────────────────────


class AllProvidersDownError(BaseGatewayException):
    """所有模型提供商不可用

    【触发场景】
    - 所有配置的提供商都处于熔断状态
    - 所有提供商都返回 5xx 错误
    - 网络问题导致无法连接任何提供商

    【处理建议】
    1. 检查网络连通性
    2. 检查各提供商服务状态
    3. 查看熔断器状态（Redis）
    4. 考虑增加备用提供商

    【降级策略】
    - 返回缓存结果（如有）
    - 提示用户稍后重试
    - 触发告警通知运维
    """

    def __init__(self):
        super().__init__(
            "所有模型提供商不可用",
            code="ERR_MODEL_ALL_PROVIDERS_DOWN",
            user_message="AI 服务暂时不可用，请稍后重试",
        )


# ─────────────────────────────────────────────────────────────────────────
# 调用级错误 - 单次请求失败
# ─────────────────────────────────────────────────────────────────────────


class ModelTimeoutError(BaseGatewayException):
    """模型调用超时

    【触发场景】
    - LLM API 响应时间超过 request_timeout_s
    - 网络延迟过高
    - 模型服务过载

    【处理建议】
    1. 检查超时配置是否合理（通常 30 秒）
    2. 检查网络延迟
    3. 考虑使用流式响应减少超时感知
    4. 检查模型服务负载

    【调优建议】
    - 普通对话：10-15 秒足够
    - 长文本生成：20-30 秒
    - 代码生成：15-25 秒
    """

    def __init__(self, timeout_s: float):
        super().__init__(
            f"模型调用超时 ({timeout_s}s)",
            code="ERR_MODEL_TIMEOUT",
            user_message="AI 响应超时，请稍后重试",
            details={"timeout_s": timeout_s},
        )


class ModelContentFilteredError(BaseGatewayException):
    """内容被安全过滤

    【触发场景】
    - 用户输入包含敏感内容（暴力、色情等）
    - 模型判断输出内容可能有害
    - 触发提供商的内容安全策略

    【处理建议】
    1. 记录被过滤的内容用于分析
    2. 提示用户调整输入
    3. 考虑实现本地敏感词过滤前置

    【合规注意】
    - 不同提供商的安全策略不同
    - 需要记录被过滤原因用于合规审计
    """

    def __init__(self, reason: str = ""):
        super().__init__(
            f"内容被安全过滤: {reason}",
            code="ERR_MODEL_CONTENT_FILTERED",
            user_message="输入内容可能包含不当信息，请调整后重试",
            details={"reason": reason},
        )


# ─────────────────────────────────────────────────────────────────────────
# 提供商级错误 - 单个提供商问题
# ─────────────────────────────────────────────────────────────────────────


class ProviderUnavailableError(BaseGatewayException):
    """单个提供商不可用

    【触发场景】
    - 提供商 API 返回 5xx 错误
    - 网络连接失败
    - API Key 无效或过期
    - 配额用尽

    【处理建议】
    1. 记录失败的提供商名称和原因
    2. 触发熔断器计数
    3. 自动切换到备用提供商
    4. 后台异步检查提供商恢复状态

    【熔断器联动】
    连续失败达到 circuit_breaker_threshold 后，
    该提供商将被熔断 circuit_breaker_timeout_s 时间。
    """

    def __init__(self, provider: str, reason: str = ""):
        super().__init__(
            f"提供商 {provider} 不可用: {reason}",
            code="ERR_PROVIDER_UNAVAILABLE",
            user_message="AI 服务暂时不可用，正在尝试其他服务",
            details={"provider": provider, "reason": reason},
        )


# ─────────────────────────────────────────────────────────────────────────
# 请求级错误 - 参数或频率问题
# ─────────────────────────────────────────────────────────────────────────


class InvalidModelRequestError(BaseGatewayException):
    """无效的模型请求

    【触发场景】
    - 请求参数格式错误
    - 不支持的模型名称
    - 参数超出范围（如 temperature > 2）
    - 缺少必要参数

    【处理建议】
    1. 检查请求参数格式
    2. 验证模型名称是否正确
    3. 检查参数范围

    【常见错误】
    - temperature: 应为 0-2 之间的浮点数
    - max_tokens: 应为正整数
    - model: 应为支持的模型名称
    """

    def __init__(self, message: str, details=None):
        super().__init__(
            message,
            code="ERR_INVALID_MODEL_REQUEST",
            user_message="请求参数有误",
            details=details,
        )


class RateLimitExceededError(BaseGatewayException):
    """请求频率超限

    【触发场景】
    - 短时间内请求次数超过限制
    - 触发提供商的速率限制
    - 触发网关的限流策略

    【处理建议】
    1. 实现指数退避重试
    2. 使用 retry_after 提示用户等待时间
    3. 检查是否有异常流量

    【限流策略】
    - 提供商级别：每个提供商独立的限流
    - 租户级别：每个租户的限流
    - 全局级别：网关整体限流
    """

    def __init__(self, retry_after: int = 60):
        super().__init__(
            "请求过于频繁",
            code="ERR_RATE_LIMIT_EXCEEDED",
            user_message=f"请 {retry_after} 秒后重试",
            details={"retry_after": retry_after},
        )
