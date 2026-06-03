"""FastAPI 依赖注入

【核心概念】依赖注入模式
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FastAPI 的依赖注入系统是构建可维护 API 的核心：
1. 解耦：路由与具体实现分离
2. 复用：通用逻辑（认证、数据库）可复用
3. 测试：依赖可轻松替换为 Mock
4. 文档：自动生成 OpenAPI 文档

【技术选型】Depends vs Middleware
┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 适用场景                    │ 示例                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Depends (选择)     │ 路由级别、需要返回值        │ get_current_user            │
│                    │ 可选依赖                    │                             │
│                    │ 需要在路径操作中使用        │                             │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Middleware         │ 全局、请求/响应处理         │ 日志、追踪、CORS            │
│                    │ 不需要返回值                │                             │
│                    │ 在路由之前执行              │                             │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【依赖类型】
1. 配置依赖：get_config()
2. 基础设施依赖：get_database_pool(), get_redis()
3. 认证依赖：get_current_tenant(), get_current_user()
4. 业务依赖：get_quota_manager()

【使用示例】
```python
from fastapi import Depends, APIRouter
from app.api.deps import get_config, get_current_user
from app.core.config import AppConfig

router = APIRouter()

@router.get("/profile")
async def get_profile(
    user_id: str = Depends(get_current_user),
    config: AppConfig = Depends(get_config),
):
    return {"user_id": user_id, "app_name": config.app_name}
```

【参考】
- FastAPI 依赖注入: https://fastapi.tiangolo.com/tutorial/dependencies/
- 依赖覆盖（测试）: https://fastapi.tiangolo.com/advanced/testing-dependencies/
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, TYPE_CHECKING

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import redis.asyncio as redis
import structlog

from app.core.config import AppConfig, get_config
from app.infrastructure.database import Pool, get_database_pool

if TYPE_CHECKING:
    from app.memory.session_store import SessionStore
    from app.tools.registry import ToolRegistry
    from app.prompts.loader import PromptLoader

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════════════════
# 配置依赖
# ═══════════════════════════════════════════════════════════════════════════


def get_app_config() -> AppConfig:
    """获取应用配置（兼容别名）

    提供更明确的函数名，同时保持与 get_config 一致。

    Returns:
        AppConfig: 应用配置实例

    使用示例:
        ```python
        @router.get("/info")
        async def get_info(config: AppConfig = Depends(get_app_config)):
            return {"version": config.app_version}
        ```
    """
    return get_config()


# 类型别名，简化依赖注入
ConfigDep = Annotated[AppConfig, Depends(get_app_config)]


# ═══════════════════════════════════════════════════════════════════════════
# 基础设施依赖
# ═══════════════════════════════════════════════════════════════════════════


async def get_database_pool_dep() -> Pool:
    """获取数据库连接池（依赖注入版本）

    用于需要数据库连接的路由。

    Returns:
        asyncpg.Pool: 数据库连接池

    Raises:
        HTTPException: 连接池未初始化

    使用示例:
        ```python
        @router.get("/users/{user_id}")
        async def get_user(
            user_id: str,
            pool: Pool = Depends(get_database_pool_dep),
        ):
            async with pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE id = $1", user_id
                )
            return user
        ```
    """
    try:
        return get_database_pool()
    except RuntimeError as e:
        logger.error("database_pool_not_initialized", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available",
        )


# 类型别名
DatabasePoolDep = Annotated[Pool, Depends(get_database_pool_dep)]


async def get_redis(request: Request) -> redis.Redis:
    """获取 Redis 客户端

    从应用状态获取 Redis 客户端实例。

    Args:
        request: FastAPI Request 对象

    Returns:
        redis.Redis: Redis 客户端

    Raises:
        HTTPException: Redis 不可用

    使用示例:
        ```python
        @router.get("/cache/{key}")
        async def get_cache(
            key: str,
            redis_client: redis.Redis = Depends(get_redis),
        ):
            value = await redis_client.get(key)
            return {"key": key, "value": value}
        ```
    """
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis connection not available",
        )
    return redis_client


# 类型别名
RedisDep = Annotated[redis.Redis, Depends(get_redis)]


async def get_session_store(request: Request) -> "SessionStore":
    """获取会话存储

    Args:
        request: FastAPI Request 对象

    Returns:
        SessionStore: 会话存储实例

    使用示例:
        ```python
        @router.get("/history/{session_id}")
        async def get_history(
            session_id: str,
            store: SessionStore = Depends(get_session_store),
        ):
            messages = await store.get_messages(session_id)
            return {"messages": messages}
        ```
    """
    from app.memory.session_store import get_session_store as _get_session_store

    return _get_session_store()


# 类型别名
SessionStoreDep = Annotated["SessionStore", Depends(get_session_store)]


# ═══════════════════════════════════════════════════════════════════════════
# 认证依赖
# ═══════════════════════════════════════════════════════════════════════════

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


def get_current_tenant(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> str:
    """获取当前租户 ID

    从请求头获取租户 ID，用于多租户隔离。

    Args:
        x_tenant_id: X-Tenant-ID 请求头

    Returns:
        str: 租户 ID

    Raises:
        HTTPException: 租户 ID 缺失

    使用示例:
        ```python
        @router.get("/orders")
        async def list_orders(
            tenant_id: str = Depends(get_current_tenant),
        ):
            # 自动按租户过滤
            return {"tenant_id": tenant_id}
        ```
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required",
        )
    return x_tenant_id


# 类型别名
TenantIdDep = Annotated[str, Depends(get_current_tenant)]


def get_current_user(
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security)
    ] = None,
) -> str:
    """获取当前用户 ID

    从请求头或 JWT Token 获取用户 ID。

    优先级：
    1. X-User-ID 请求头（内部服务调用）
    2. JWT Token 中的 sub 字段（外部调用）

    Args:
        x_user_id: X-User-ID 请求头
        credentials: Bearer Token

    Returns:
        str: 用户 ID

    Raises:
        HTTPException: 用户认证失败

    使用示例:
        ```python
        @router.get("/profile")
        async def get_profile(
            user_id: str = Depends(get_current_user),
        ):
            return {"user_id": user_id}
        ```
    """
    # 优先使用请求头（内部服务调用）
    if x_user_id:
        return x_user_id

    # 尝试从 JWT 解析（外部调用）
    if credentials:
        try:
            token = credentials.credentials
            payload = _verify_jwt_token(token)
            user_id = payload.get("sub")
            if user_id:
                return user_id
        except UnauthorizedError as e:
            logger.warning(
                "jwt_verification_failed",
                error=e.message,
                error_code=e.code,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=e.user_message,
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.warning("jwt_parse_failed", error=str(e))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _verify_jwt_token(token: str) -> dict:
    """完整 JWT 验证

    验证项：
    1. 签名验证（使用 HS256 算法）
    2. 过期时间验证（exp 字段）
    3. 签发时间验证（iat 字段）
    4. Token 类型验证（type 字段必须为 access）

    Args:
        token: JWT Token 字符串

    Returns:
        dict: 解码后的 payload

    Raises:
        UnauthorizedError: 验证失败
    """
    import jwt

    try:
        payload = jwt.decode(
            token,
            config.jwt_secret,
            algorithms=[config.jwt_algorithm],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require": ["exp", "iat", "sub"],
            },
        )

        # 验证 token 类型（如果有）
        token_type = payload.get("type")
        if token_type and token_type != "access":
            raise UnauthorizedError("Invalid token type")

        return payload

    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token 已过期，请重新登录")
    except jwt.InvalidSignatureError:
        raise UnauthorizedError("Token 签名无效")
    except jwt.InvalidAlgorithmError:
        raise UnauthorizedError("Token 使用了不支持的算法")
    except jwt.MissingRequiredClaimError as e:
        raise UnauthorizedError(f"Token 缺少必要字段: {e.claim}")
    except jwt.InvalidTokenError as e:
        raise UnauthorizedError(f"Token 无效: {str(e)}")


# 类型别名
UserIdDep = Annotated[str, Depends(get_current_user)]


def get_optional_user(
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security)
    ] = None,
) -> str | None:
    """获取可选用户 ID

    与 get_current_user 类似，但不强制要求认证。

    Returns:
        str | None: 用户 ID（可能为 None）

    使用示例:
        ```python
        @router.get("/public/{item_id}")
        async def get_public_item(
            item_id: str,
            user_id: str | None = Depends(get_optional_user),
        ):
            # 公开资源，但登录用户可能看到更多信息
            return {"item_id": item_id, "viewer": user_id}
        ```
    """
    try:
        if x_user_id:
            return x_user_id
        if credentials:
            # 简化处理
            return getattr(credentials, "user_id", None)
    except Exception:
        pass
    return None


# 类型别名
OptionalUserIdDep = Annotated[str | None, Depends(get_optional_user)]


def get_request_id(
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> str:
    """获取请求追踪 ID

    用于全链路追踪，关联日志和监控。

    Args:
        x_request_id: X-Request-ID 请求头

    Returns:
        str: 请求 ID

    使用示例:
        ```python
        @router.post("/orders")
        async def create_order(
            request_id: str = Depends(get_request_id),
        ):
            logger.info("order_created", request_id=request_id)
            return {"request_id": request_id}
        ```
    """
    if x_request_id:
        return x_request_id
    # 生成默认请求 ID
    import uuid

    return f"req_{uuid.uuid4().hex[:12]}"


# 类型别名
RequestIdDep = Annotated[str, Depends(get_request_id)]


# ═══════════════════════════════════════════════════════════════════════════
# 业务依赖
# ═══════════════════════════════════════════════════════════════════════════


class QuotaManager:
    """配额管理器

    管理租户/用户的使用配额，防止资源滥用。

    功能：
    - 请求频率限制
    - Token 使用量限制
    - 并发请求数限制
    """

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def check_request_quota(
        self,
        tenant_id: str,
        user_id: str,
    ) -> bool:
        """检查请求配额

        实现两级限制：
        1. 租户级：每分钟请求数限制
        2. 用户级：每小时请求数限制

        Args:
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            bool: 是否有配额

        Raises:
            QuotaExceededError: 配额用尽
        """
        # 1. 检查租户级每分钟限制
        minute_key = f"quota:{tenant_id}:req:min"
        count = await self._redis.incr(minute_key)
        if count == 1:
            await self._redis.expire(minute_key, 60)

        if count > config.quota_tenant_requests_per_minute:
            logger.warning(
                "tenant_rate_limit_exceeded",
                tenant_id=tenant_id,
                count=count,
                limit=config.quota_tenant_requests_per_minute,
            )
            raise QuotaExceededError(
                f"租户请求频率超限（{config.quota_tenant_requests_per_minute}/分钟）"
            )

        # 2. 检查用户级每小时限制
        hour_key = f"quota:{tenant_id}:{user_id}:req:hour"
        count = await self._redis.incr(hour_key)
        if count == 1:
            await self._redis.expire(hour_key, 3600)

        if count > config.quota_user_requests_per_hour:
            logger.warning(
                "user_rate_limit_exceeded",
                tenant_id=tenant_id,
                user_id=user_id,
                count=count,
                limit=config.quota_user_requests_per_hour,
            )
            raise QuotaExceededError(
                f"用户请求频率超限（{config.quota_user_requests_per_hour}/小时）"
            )

        return True

    async def check_token_quota(
        self,
        tenant_id: str,
        tokens_requested: int,
    ) -> bool:
        """检查 Token 配额

        实现租户级每日 Token 配额限制。

        Args:
            tenant_id: 租户 ID
            tokens_requested: 请求的 Token 数

        Returns:
            bool: 是否有配额

        Raises:
            QuotaExceededError: 配额用尽
        """
        daily_key = f"quota:{tenant_id}:tokens:daily"
        used = await self._redis.incrby(daily_key, tokens_requested)

        # 首次设置时设置过期时间
        if used == tokens_requested:
            await self._redis.expire(daily_key, 86400)

        if used > config.quota_tenant_tokens_per_day:
            logger.warning(
                "token_quota_exceeded",
                tenant_id=tenant_id,
                used=used,
                limit=config.quota_tenant_tokens_per_day,
            )
            # 回滚计数
            await self._redis.incrby(daily_key, -tokens_requested)
            raise QuotaExceededError(
                f"租户 Token 配额用尽（{config.quota_tenant_tokens_per_day}/天）"
            )

        return True

    async def record_usage(
        self,
        tenant_id: str,
        user_id: str,
        tokens_used: int,
        request_id: str,
    ) -> None:
        """记录使用量

        将使用量记录到 Redis，用于计费和统计。

        Args:
            tenant_id: 租户 ID
            user_id: 用户 ID
            tokens_used: 使用的 Token 数
            request_id: 请求 ID
        """
        import time

        today = time.strftime("%Y-%m-%d")

        # 记录到每日统计
        daily_key = f"usage:{tenant_id}:{today}"
        await self._redis.incrby(f"{daily_key}:tokens", tokens_used)
        await self._redis.incr(f"{daily_key}:requests")

        # 记录用户级统计
        user_key = f"usage:{tenant_id}:{user_id}:{today}"
        await self._redis.incrby(f"{user_key}:tokens", tokens_used)
        await self._redis.incr(f"{user_key}:requests")

        logger.debug(
            "usage_recorded",
            tenant_id=tenant_id,
            user_id=user_id,
            tokens_used=tokens_used,
            request_id=request_id,
        )


async def get_quota_manager(
    redis_client: RedisDep,
) -> QuotaManager:
    """获取配额管理器

    Args:
        redis_client: Redis 客户端

    Returns:
        QuotaManager: 配额管理器实例

    使用示例:
        ```python
        @router.post("/chat")
        async def chat(
            message: str,
            quota: QuotaManager = Depends(get_quota_manager),
            tenant_id: str = Depends(get_current_tenant),
            user_id: str = Depends(get_current_user),
        ):
            if not await quota.check_request_quota(tenant_id, user_id):
                raise HTTPException(429, "Quota exceeded")
            # 处理请求...
        ```
    """
    return QuotaManager(redis_client)


# 类型别名
QuotaManagerDep = Annotated[QuotaManager, Depends(get_quota_manager)]


async def get_tool_registry() -> "ToolRegistry":
    """获取工具注册表

    Returns:
        ToolRegistry: 工具注册表实例

    使用示例:
        ```python
        @router.get("/tools")
        async def list_tools(
            registry: ToolRegistry = Depends(get_tool_registry),
        ):
            return {"tools": registry.list_all()}
        ```
    """
    from app.tools.registry import get_tool_registry as _get_tool_registry

    return _get_tool_registry()


# 类型别名
ToolRegistryDep = Annotated["ToolRegistry", Depends(get_tool_registry)]


async def get_prompt_loader() -> "PromptLoader":
    """获取 Prompt 加载器

    Returns:
        PromptLoader: Prompt 加载器实例

    使用示例:
        ```python
        @router.get("/prompts/{name}")
        async def get_prompt(
            name: str,
            loader: PromptLoader = Depends(get_prompt_loader),
        ):
            template = loader.load(name)
            return {"template": template.source}
        ```
    """
    from app.prompts.loader import get_prompt_loader as _get_prompt_loader

    return _get_prompt_loader()


# 类型别名
PromptLoaderDep = Annotated["PromptLoader", Depends(get_prompt_loader)]


# ═══════════════════════════════════════════════════════════════════════════
# 组合依赖（常用组合）
# ═══════════════════════════════════════════════════════════════════════════


class RequestContext:
    """请求上下文

    聚合常用请求信息，简化依赖注入。

    Attributes:
        request_id: 请求追踪 ID
        tenant_id: 租户 ID
        user_id: 用户 ID
    """

    def __init__(
        self,
        request_id: str,
        tenant_id: str,
        user_id: str,
    ):
        self.request_id = request_id
        self.tenant_id = tenant_id
        self.user_id = user_id

    def __repr__(self) -> str:
        return (
            f"RequestContext(request_id={self.request_id}, "
            f"tenant_id={self.tenant_id}, user_id={self.user_id})"
        )


def get_request_context(
    request_id: RequestIdDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> RequestContext:
    """获取请求上下文

    聚合请求 ID、租户 ID、用户 ID。

    Returns:
        RequestContext: 请求上下文对象

    使用示例:
        ```python
        @router.post("/chat")
        async def chat(
            message: str,
            ctx: RequestContext = Depends(get_request_context),
        ):
            logger.info(
                "chat_request",
                request_id=ctx.request_id,
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
            )
            # 处理请求...
        ```
    """
    return RequestContext(
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )


# 类型别名
RequestContextDep = Annotated[RequestContext, Depends(get_request_context)]
