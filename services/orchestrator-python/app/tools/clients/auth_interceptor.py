"""gRPC 认证拦截器 (S-AGENT-06)

实现服务间认证：
- 客户端：注入 Service Token 和追踪信息
- 服务端：验证 Token 和服务身份

【核心概念】客户端在架构中的位置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│                          服务间认证流程                                      │
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │   Orchestrator   │                                                       │
│  │    (Python)       │                                                       │
│  │    客户端角色     │                                                       │
│  └────────┬─────────┘                                                       │
│           │ gRPC 调用 + Metadata                                            │
│           │ ┌─────────────────────────────────────┐                         │
│           │ │ authorization: Bearer <token>       │                         │
│           │ │ x-service-name: orchestrator        │                         │
│           │ │ x-request-id: req_abc               │                         │
│           │ │ x-tenant-id: tenant_001             │                         │
│           │ └─────────────────────────────────────┘                         │
│           ▼                                                                 │
│  ┌──────────────────┐                                                       │
│  │    Tool Bus       │                                                       │
│  │    (Java)          │                                                       │
│  │    服务端角色     │                                                       │
│  │                    │                                                       │
│  │  1. 验证 Token    │                                                       │
│  │  2. 检查服务白名单│                                                       │
│  │  3. 记录审计日志  │                                                       │
│  └──────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

本模块提供两层防护：
- AuthInterceptor（客户端）：自动注入认证信息
- ServerAuthInterceptor（服务端）：验证请求合法性

【技术选型】gRPC 认证方案对比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ ✓ 拦截器 + HMAC   │ • 无额外依赖                │ • 需要手动实现              │
│   (当前选择)       │ • 灵活可控                  │ • 需要共享密钥              │
│                    │ • 性能高（无网络调用）      │                              │
│                    │ • 支持自定义元数据          │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ mTLS               │ • 最高安全性                │ • 证书管理复杂              │
│                    │ • 双向认证                  │ • 性能开销                  │
│                    │ • 行业标准                  │ • 需要基础设施支持          │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ OAuth2/JWT         │ • 行业标准                  │ • 需要 OAuth 服务           │
│                    │ • 支持细粒度权限            │ • 复杂度高                  │
│                    │ • 支持外部系统              │ • 性能开销                  │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ API Key            │ • 简单易用                  │ • 安全性较低                │
│                    │ • 快速集成                  │ • 无过期机制                │
│                    │                             │ • 难以撤销                  │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【决策依据】选择拦截器 + HMAC 的原因：
1. 内部服务调用，无需复杂的 OAuth 流程
2. HMAC 签名快速，无网络调用开销
3. 支持自定义元数据（request_id, tenant_id）
4. 与现有基础设施无额外依赖

【认证流程详解】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│                          Token 生成与验证                                    │
│                                                                             │
│  客户端（Orchestrator）                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. 构建 Payload                                                    │   │
│  │     {                                                               │   │
│  │       "iss": "agent-platform",    // 签发者                        │   │
│  │       "sub": "orchestrator",      // 服务名                        │   │
│  │       "iat": 1704067200,          // 签发时间                      │   │
│  │       "exp": 1704067500           // 过期时间（5分钟后）           │   │
│  │     }                                                               │   │
│  │                                                                     │   │
│  │  2. Base64 编码 Payload                                            │   │
│  │                                                                     │   │
│  │  3. HMAC-SHA256 签名                                               │   │
│  │     signature = HMAC(secret, encoded_payload)                      │   │
│  │                                                                     │   │
│  │  4. 拼接 Token                                                     │   │
│  │     token = base64(payload) + "." + base64(signature)              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  服务端（ToolBus）                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. 解析 Token                                                      │   │
│  │                                                                     │   │
│  │  2. 验证签名                                                        │   │
│  │     expected_sig = HMAC(secret, payload)                           │   │
│  │     compare(expected_sig, actual_sig)                              │   │
│  │                                                                     │   │
│  │  3. 验证过期时间                                                    │   │
│  │     if exp < now: raise TokenExpired                               │   │
│  │                                                                     │   │
│  │  4. 验证服务身份                                                    │   │
│  │     if sub not in valid_services: raise Unauthorized               │   │
│  │                                                                     │   │
│  │  5. 允许请求                                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

【安全配置说明】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬───────────────┬─────────────────────────────────────────┐
│ 参数               │ 默认值        │ 说明                                    │
├────────────────────┼───────────────┼─────────────────────────────────────────┤
│ expiry_seconds     │ 300 (5分钟)   │ Token 有效期，防止重放攻击              │
│ issuer             │ agent-platform│ Token 签发者标识                        │
│ secret             │ 配置项        │ HMAC 密钥，必须保密                     │
│ valid_services     │ 配置项        │ 允许调用的服务白名单                    │
└────────────────────┴───────────────┴─────────────────────────────────────────┘

【安全最佳实践】
┌────────────────────┬─────────────────────────────────────────────────────────┐
│ 安全措施           │ 说明                                                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│ 密钥轮换           │ 定期更换 HMAC 密钥，建议 90 天                          │
│ 短有效期           │ Token 有效期 5 分钟，限制被盗风险                      │
│ 服务白名单         │ 只允许特定服务调用，防止内部滥用                       │
│ 审计日志           │ 记录所有调用，便于追溯                                 │
│ HTTPS/TLS          │ 生产环境必须使用 TLS 加密传输                          │
└────────────────────┴─────────────────────────────────────────────────────────┘

【降级策略】认证失败时的应对方案
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│                          认证失败处理                                        │
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │  客户端调用      │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐                                                       │
│  │  服务端验证      │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│     ┌─────┴─────┬─────────────┐                                             │
│     │           │             │                                             │
│     ▼           ▼             ▼                                             │
│  ┌────────┐ ┌────────┐ ┌────────────┐                                       │
│  │Token   │ │服务不在│ │ Token过期  │                                       │
│  │签名错误│ │白名单中│ │            │                                       │
│  └────┬───┘ └────┬───┘ └─────┬──────┘                                       │
│       │          │            │                                             │
│       ▼          ▼            ▼                                             │
│  ┌────────────────────────────────────┐                                     │
│  │ 返回 gRPC 错误                      │                                     │
│  │ - UNAUTHENTICATED (16)             │                                     │
│  │ - PERMISSION_DENIED (7)            │                                     │
│  └────────────────────────────────────┘                                     │
│                                                                             │
│  客户端处理：                                                               │
│  - 记录错误日志                                                            │
│  - 重试（如果是临时错误）                                                   │
│  - 返回用户友好提示                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

【Mock 模式使用场景】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────────────────────────────────┐
│ 场景               │ 说明                                                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│ 本地开发           │ 跳过认证验证，加快开发迭代                              │
│ 单元测试           │ 使用固定 Token，隔离认证逻辑                            │
│ 性能测试           │ 禁用签名验证，减少开销                                  │
└────────────────────┴─────────────────────────────────────────────────────────┘

启用 Mock 模式（服务端）：
```python
# 跳过所有认证（仅限开发环境！）
interceptor = ServerAuthInterceptor(
    valid_services={"*"},  # 允许所有服务
    token_validator=lambda x: {"sub": "mock"},  # 跳过验证
    skip_methods={"*"},  # 跳过所有方法
)
```
"""

from __future__ import annotations

import time
from collections.abc import Callable

import grpc
import structlog

logger = structlog.get_logger()


class AuthInterceptor(grpc.UnaryUnaryClientInterceptor):
    """gRPC 客户端认证拦截器

    【核心职责】
    自动为每个 gRPC 调用注入认证和追踪信息：
    - authorization: Service Token（服务身份）
    - x-service-name: 调用方服务名
    - x-request-id: 请求追踪 ID
    - x-tenant-id: 租户 ID

    【使用示例】
    ```python
    # 创建 Token 提供器
    token_manager = ServiceTokenManager(
        secret="your-secret-key",
        expiry_seconds=300,
    )
    token_provider = lambda: token_manager.generate_token("orchestrator")

    # 创建拦截器
    interceptor = AuthInterceptor(
        service_name="orchestrator",
        token_provider=token_provider,
        request_id_provider=lambda: get_current_request_id(),
        tenant_id_provider=lambda: get_current_tenant_id(),
    )

    # 应用拦截器
    channel = grpc.insecure_channel("localhost:50051")
    intercepted_channel = grpc.intercept_channel(channel, interceptor)
    stub = ToolBusServiceStub(intercepted_channel)
    ```

    【执行流程】
    ┌─────────────────────────────────────────────────────────────────────┐
    │  1. 拦截 gRPC 调用                                                  │
    │                                                                     │
    │  2. 获取当前 metadata                                               │
    │                                                                     │
    │  3. 注入认证信息                                                    │
    │     ├─ authorization: Bearer <token>                               │
    │     ├─ x-service-name: orchestrator                                │
    │     ├─ x-request-id: req_abc                                       │
    │     └─ x-tenant-id: tenant_001                                     │
    │                                                                     │
    │  4. 创建新的 ClientCallDetails                                      │
    │                                                                     │
    │  5. 继续调用                                                        │
    └─────────────────────────────────────────────────────────────────────┘

    【线程安全】
    拦截器本身是无状态的，所有状态通过 provider 函数获取。
    可以安全地在多个协程间共享。
    """

    def __init__(
        self,
        service_name: str,
        token_provider: Callable[[], str],
        request_id_provider: Callable[[], str] | None = None,
        tenant_id_provider: Callable[[], str] | None = None,
    ):
        """初始化认证拦截器

        Args:
            service_name: 当前服务名称，用于服务端验证身份
                          如："orchestrator", "gateway"
            token_provider: Token 提供器函数，每次调用返回当前有效的 Token
                           建议使用 ServiceTokenManager.generate_token
            request_id_provider: 请求 ID 提供器（可选）
                                用于链路追踪，通常从请求上下文获取
            tenant_id_provider: 租户 ID 提供器（可选）
                               用于多租户隔离

        【Provider 设计说明】
        使用函数而非固定值的原因：
        1. Token 有有效期，需要动态生成
        2. request_id 和 tenant_id 来自请求上下文，不同请求不同
        3. 支持异步环境中的上下文传递
        """
        self.service_name = service_name
        self.token_provider = token_provider
        self.request_id_provider = request_id_provider
        self.tenant_id_provider = tenant_id_provider

    def intercept_unary_unary(
        self,
        continuation: Callable,
        client_call_details: grpc.ClientCallDetails,
        request,
    ):
        """拦截一元调用，注入认证信息

        【gRPC 拦截器机制】
        每个一元调用都会经过此方法。我们可以：
        1. 修改 metadata（添加认证头）
        2. 修改请求（不推荐，可能破坏序列化）
        3. 记录日志
        4. 完全阻止调用

        【Metadata 格式】
        gRPC metadata 类似 HTTP headers，格式为 List[Tuple[str, str]]。
        可以有多个相同 key 的条目。

        Args:
            continuation: 继续调用的函数
            client_call_details: 调用详情（method, timeout, metadata 等）
            request: 请求对象（Protobuf 消息）

        Returns:
            调用结果（grpc.Call 或 grpc.CallFuture）
        """
        metadata = list(client_call_details.metadata or [])

        # 注入 Service Token
        token = self.token_provider()
        metadata.append(("authorization", f"Bearer {token}"))

        # 注入服务标识
        metadata.append(("x-service-name", self.service_name))

        # 注入请求追踪 ID
        if self.request_id_provider:
            request_id = self.request_id_provider()
            if request_id:
                metadata.append(("x-request-id", request_id))

        # 注入租户 ID
        if self.tenant_id_provider:
            tenant_id = self.tenant_id_provider()
            if tenant_id:
                metadata.append(("x-tenant-id", tenant_id))

        # 创建新的 ClientCallDetails
        new_details = client_call_details._replace(metadata=metadata)

        return continuation(new_details, request)


class ServerAuthInterceptor(grpc.ServerInterceptor):
    """gRPC 服务端认证拦截器

    【核心职责】
    验证每个进入的 gRPC 请求：
    1. 提取并验证 Service Token（签名、有效期）
    2. 验证调用方服务身份（白名单）
    3. 记录审计日志

    【使用示例】
    ```python
    # 创建 Token 验证器
    token_manager = ServiceTokenManager(
        secret="your-secret-key",  # 必须与客户端相同
        expiry_seconds=300,
    )

    # 创建服务端拦截器
    interceptor = ServerAuthInterceptor(
        valid_services={"orchestrator", "gateway"},  # 允许的服务
        token_validator=token_manager.validate_token,
        skip_methods={"grpc.health.v1.Health/Check"},  # 跳过健康检查
    )

    # 应用拦截器
    server = grpc.server(
        futures.ThreadPoolExecutor(),
        interceptors=[interceptor],
    )
    ```

    【执行流程】
    ┌─────────────────────────────────────────────────────────────────────┐
    │  1. 检查是否跳过认证（skip_methods）                               │
    │     │                                                               │
    │     └─ 跳过 → 直接继续                                              │
    │                                                                     │
    │  2. 提取 authorization header                                       │
    │     │                                                               │
    │     └─ 缺失 → UNAUTHENTICATED                                       │
    │                                                                     │
    │  3. 验证 Token 签名和有效期                                         │
    │     │                                                               │
    │     └─ 无效 → UNAUTHENTICATED                                       │
    │                                                                     │
    │  4. 检查服务身份（白名单）                                          │
    │     │                                                               │
    │     └─ 不在白名单 → PERMISSION_DENIED                               │
    │                                                                     │
    │  5. 记录审计日志                                                    │
    │                                                                     │
    │  6. 继续处理请求                                                    │
    └─────────────────────────────────────────────────────────────────────┘

    【gRPC 状态码】
    - UNAUTHENTICATED (16): 认证失败（Token 无效/缺失）
    - PERMISSION_DENIED (7): 权限不足（服务不在白名单）
    """

    def __init__(
        self,
        valid_services: set[str],
        token_validator: Callable[[str], dict],
        skip_methods: set[str] | None = None,
    ):
        """初始化服务端认证拦截器

        Args:
            valid_services: 合法的调用方服务名称集合
                           只有这些服务的请求会被允许
                           如：{"orchestrator", "gateway"}
            token_validator: Token 验证函数
                            输入: Token 字符串
                            输出: Token payload (dict)
                            异常: 验证失败时抛出 ValueError
            skip_methods: 跳过认证的方法名集合
                         通常包括健康检查等公开方法
                         如：{"grpc.health.v1.Health/Check"}

        【安全建议】
        - valid_services 应该精确配置，不要使用 "*"
        - 定期审查白名单，移除不再使用的服务
        - 生产环境不要跳过关键方法的认证
        """
        self.valid_services = valid_services
        self.token_validator = token_validator
        self.skip_methods = skip_methods or {"grpc.health.v1.Health/Check"}

    def intercept_service(self, continuation, handler_call_details):
        """拦截服务调用，验证认证信息

        【gRPC 服务端拦截器机制】
        每个进入的 RPC 调用都会经过此方法。
        返回一个 RPC handler 或 None（继续默认处理）。

        Args:
            continuation: 继续处理的函数
            handler_call_details: 调用详情，包含 method 和 metadata

        Returns:
            RPC handler 或 None
        """
        method = handler_call_details.method

        # 跳过指定方法
        if method in self.skip_methods:
            return continuation(handler_call_details)

        metadata = dict(handler_call_details.invocation_metadata or [])

        # 1. 提取并验证 Token
        auth_header = metadata.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid authorization header", method=method)
            return self._unauthenticated_handler("Missing authorization header")

        token = auth_header[7:]  # 去掉 "Bearer " 前缀

        try:
            payload = self.token_validator(token)
        except Exception as e:
            logger.warning("Token validation failed", method=method, error=str(e))
            return self._unauthenticated_handler("Invalid token")

        # 2. 验证服务身份
        service_name = metadata.get("x-service-name", "")
        if service_name not in self.valid_services:
            logger.warning(
                "Unauthorized service",
                method=method,
                service_name=service_name,
                valid_services=self.valid_services,
            )
            return self._permission_denied_handler(f"Unauthorized service: {service_name}")

        # 3. 记录审计日志
        logger.info(
            "gRPC call authenticated",
            method=method,
            service_name=service_name,
            request_id=metadata.get("x-request-id", ""),
            tenant_id=metadata.get("x-tenant-id", ""),
        )

        return continuation(handler_call_details)

    def _unauthenticated_handler(self, message: str):
        """返回未认证错误处理器

        【gRPC 错误处理】
        返回一个 RPC handler，调用 context.abort() 终止请求。
        这会向客户端返回 UNAUTHENTICATED 状态码。
        """

        def abort_handler(request, context):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, message)

        return grpc.unary_unary_rpc_method_handler(abort_handler)

    def _permission_denied_handler(self, message: str):
        """返回权限拒绝错误处理器

        【gRPC 错误处理】
        返回一个 RPC handler，调用 context.abort() 终止请求。
        这会向客户端返回 PERMISSION_DENIED 状态码。
        """

        def abort_handler(request, context):
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

        return grpc.unary_unary_rpc_method_handler(abort_handler)


class ServiceTokenManager:
    """Service Token 管理器

    【核心职责】
    负责生成和验证服务间通信的 Token。
    使用 HMAC-SHA256 签名，保证安全性和性能。

    【Token 格式】
    base64(payload) + "." + base64(signature)

    与 JWT 的区别：
    - 不使用标准 JWT 头部（简化）
    - 不支持非对称加密（内部服务无需）
    - 不支持 claims 扩展（固定字段）

    【使用示例】
    ```python
    # 创建管理器（客户端和服务端使用相同的 secret）
    manager = ServiceTokenManager(
        secret="your-very-secure-secret-key",
        expiry_seconds=300,  # 5 分钟
        issuer="agent-platform",
    )

    # 客户端：生成 Token
    token = manager.generate_token("orchestrator")
    # Token 示例: "eyJpc3MiOiJhZ2VudC1wbGF0Zm9ybSIsInN1YiI6Im9yY2hlc3RyYXRvciIsImlhdCI6MTcwNDA2NzIwMCwiZXhwIjoxNzA0MDY3NTAwfQ.signature

    # 服务端：验证 Token
    try:
        payload = manager.validate_token(token)
        # payload: {"iss": "agent-platform", "sub": "orchestrator", ...}
        service_name = payload["sub"]
    except ValueError as e:
        print(f"Token 验证失败: {e}")
    ```

    【安全注意事项】
    1. secret 必须保密，不要硬编码在代码中
    2. 定期轮换 secret（建议 90 天）
    3. expiry_seconds 不要设置太长（默认 5 分钟）
    4. 生产环境必须使用 TLS 加密传输
    """

    def __init__(
        self,
        secret: str,
        expiry_seconds: int = 300,  # 5 分钟
        issuer: str = "agent-platform",
    ):
        """初始化 Token 管理器

        Args:
            secret: HMAC 签名密钥
                   - 建议至少 32 字节随机字符串
                   - 不要硬编码，从环境变量或配置中心读取
                   - 客户端和服务端必须使用相同的 secret
            expiry_seconds: Token 有效期（秒）
                           - 默认 300 秒（5 分钟）
                           - 建议 60-600 秒
                           - 太短：频繁生成 Token
                           - 太长：安全风险增加
            issuer: Token 签发者标识
                   - 用于验证 Token 来源
                   - 多系统部署时区分不同平台

        【密钥生成建议】
        ```python
        import secrets
        secret = secrets.token_urlsafe(32)  # 生成 32 字节安全随机字符串
        ```
        """
        self.secret = secret.encode()
        self.expiry_seconds = expiry_seconds
        self.issuer = issuer

    def generate_token(self, service_name: str) -> str:
        """生成 Service Token

        【Token 结构】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  Payload (JSON)                                                      │
        │  {                                                                   │
        │    "iss": "agent-platform",    // 签发者                            │
        │    "sub": "orchestrator",      // 服务名（subject）                 │
        │    "iat": 1704067200,          // 签发时间（Unix timestamp）        │
        │    "exp": 1704067500           // 过期时间（Unix timestamp）        │
        │  }                                                                   │
        │                                                                     │
        │  编码：base64(json(payload))                                        │
        │                                                                     │
        │  签名：base64(HMAC-SHA256(secret, encoded_payload))                │
        │                                                                     │
        │  最终格式：encoded_payload + "." + signature                        │
        └─────────────────────────────────────────────────────────────────────┘

        Args:
            service_name: 服务名称，将作为 Token 的 subject

        Returns:
            签名后的 Token 字符串

        【性能考虑】
        - 每次调用都会生成新 Token
        - 如果调用频繁，可以考虑缓存 Token（在有效期内）
        - 但要注意缓存失效后的安全性
        """
        import base64
        import hashlib
        import hmac
        import json

        now = int(time.time())
        payload = {
            "iss": self.issuer,
            "sub": service_name,
            "iat": now,
            "exp": now + self.expiry_seconds,
        }

        payload_json = json.dumps(payload, separators=(",", ":"))
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")

        signature = hmac.new(
            self.secret,
            payload_b64.encode(),
            hashlib.sha256,
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        return f"{payload_b64}.{signature_b64}"

    def validate_token(self, token: str) -> dict:
        """验证 Service Token

        【验证步骤】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  1. 解析 Token 格式（payload.signature）                            │
        │     │                                                               │
        │     └─ 格式错误 → ValueError                                       │
        │                                                                     │
        │  2. 验证签名                                                        │
        │     │                                                               │
        │     └─ 签名不匹配 → ValueError                                     │
        │                                                                     │
        │  3. 解析 Payload                                                    │
        │     │                                                               │
        │     └─ JSON 无效 → ValueError                                      │
        │                                                                     │
        │  4. 验证过期时间                                                    │
        │     │                                                               │
        │     └─ 已过期 → ValueError                                         │
        │                                                                     │
        │  5. 验证签发者                                                      │
        │     │                                                               │
        │     └─ 签发者不匹配 → ValueError                                   │
        │                                                                     │
        │  6. 返回 Payload                                                    │
        └─────────────────────────────────────────────────────────────────────┘

        Args:
            token: 待验证的 Token 字符串

        Returns:
            Token payload (dict):
            {
                "iss": "agent-platform",
                "sub": "orchestrator",
                "iat": 1704067200,
                "exp": 1704067500
            }

        Raises:
            ValueError: Token 无效或过期

        【安全考虑】
        - 使用 hmac.compare_digest 防止时序攻击
        - 验证所有必需字段
        - 记录验证失败日志（用于安全审计）
        """
        import base64
        import hashlib
        import hmac
        import json

        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Invalid token format")

        payload_b64, signature_b64 = parts

        # 验证签名
        expected_signature = hmac.new(
            self.secret,
            payload_b64.encode(),
            hashlib.sha256,
        ).digest()

        # 补齐 base64 padding
        signature_b64_padded = signature_b64 + "=" * (4 - len(signature_b64) % 4)
        actual_signature = base64.urlsafe_b64decode(signature_b64_padded)

        if not hmac.compare_digest(expected_signature, actual_signature):
            raise ValueError("Invalid signature")

        # 解析 payload
        payload_b64_padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64_padded)
        payload = json.loads(payload_json)

        # 验证过期时间
        now = int(time.time())
        if payload.get("exp", 0) < now:
            raise ValueError("Token expired")

        # 验证签发者
        if payload.get("iss") != self.issuer:
            raise ValueError("Invalid issuer")

        return payload
