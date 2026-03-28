"""Orchestrator Service 主入口

【核心概念】FastAPI 应用生命周期
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FastAPI 采用 ASGI 异步网关接口，应用有三个阶段：
1. 启动（startup）：初始化资源（数据库、Redis、gRPC 客户端）
2. 运行（runtime）：处理请求
3. 关闭（shutdown）：释放资源

【技术选型】为什么选择 FastAPI？
┌─────────────────────────────────────────────────────────────────────────┐
│  框架          │  优点                    │  缺点                  │
├────────────────┼──────────────────────────┼────────────────────────┤
│  Flask         │  成熟稳定、生态丰富       │  同步阻塞、性能受限    │
│  Django        │  全功能框架              │  重、学习曲线陡峭      │
│  ✓ FastAPI     │  异步高性能、自动文档     │  相对年轻              │
│  Starlette     │  轻量异步                │  功能较少              │
└─────────────────────────────────────────────────────────────────────────┘

FastAPI 的优势：
- 异步原生：与 LangGraph、httpx 完美配合
- 自动文档：OpenAPI/Swagger 自动生成
- 类型提示：Pydantic 模型 + IDE 支持
- 性能优秀：接近 Go/Java 水平

【中间件顺序】重要！执行顺序从下到上
┌─────────────────────────────────────────────────────────────────────────┐
│  请求流 → CORS → Metrics → ErrorHandler → RequestContext → 路由处理器  │
│                                                                         │
│  注册顺序（代码中）：                                                    │
│  1. CORSMiddleware（最后添加，最先执行）                                 │
│  2. RequestMetricsMiddleware                                            │
│  3. ErrorHandlerMiddleware                                              │
│  4. RequestContextMiddleware（最先添加，最后执行）                       │
└─────────────────────────────────────────────────────────────────────────┘

【依赖注入模式】
使用全局变量 + getter 函数而非类单例的原因：
- 简单直接，易于测试时 mock
- FastAPI 的 Depends() 支持 getter 函数
- 避免复杂的依赖注入框架

【参考】
- FastAPI 生命周期: https://fastapi.tiangolo.com/advanced/events/
- ASGI 规范: https://asgi.readthedocs.io/
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from redis.asyncio import Redis

from app.api.v1 import chat, health
from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.api.middleware.request_context import RequestContextMiddleware
from app.api.middleware.rate_limit_middleware import RateLimitMiddleware
from app.api.middleware.tracing_middleware import TracingMiddleware
from app.core.config import config
from app.core.feature_flags import FeatureFlagClient
from app.core.health_checker import init_health_checker
from app.core.logging import setup_logging
from app.core.metrics import RequestMetricsMiddleware
from app.core.step_buffer import StepBuffer

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════════════════
# 全局组件 - 生命周期管理
# ═══════════════════════════════════════════════════════════════════════════

# 使用模块级变量而非类单例的原因：
# - 简单直接，无需引入额外依赖
# - 测试时可直接替换模块变量
# - FastAPI lifespan 天然支持这种模式

redis_client: Redis | None = None
feature_flags: FeatureFlagClient | None = None
step_buffer: StepBuffer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    【ASGI 生命周期事件】
    使用 async context manager 管理资源：
    - yield 前：startup 事件，初始化资源
    - yield 后：shutdown 事件，释放资源

    这比 @app.on_event("startup") 更现代，推荐使用。

    初始化顺序很重要：
    1. 日志系统（最先，后续日志才能正常输出）
    2. Redis（Feature Flag、缓存、健康检查依赖）
    3. 健康检查器（K8s 探测依赖）
    4. 缓存管理器（工具调用依赖）
    5. 数据库连接池（工具、会话依赖）
    6. gRPC 客户端（ToolBus 依赖）
    """
    global redis_client, feature_flags, step_buffer

    # ─────────────────────────────────────────────────────────────────────
    # Startup: 初始化资源
    # ─────────────────────────────────────────────────────────────────────

    # 1. 日志初始化（必须最先）
    setup_logging(config.environment, config.debug)

    # 1.5 初始化追踪系统
    from app.core.tracing import setup_tracing
    setup_tracing("orchestrator-python")

    logger.info(
        "Orchestrator starting",
        environment=config.environment,
        version="1.0.0",
    )

    # 2. Redis 连接（Feature Flag、缓存、健康检查依赖）
    redis_client = Redis.from_url(config.redis_url)
    feature_flags = FeatureFlagClient(redis_client)
    logger.info("Redis connected")

    # 3. 健康检查器（K8s 探测依赖）
    # 用于监控各服务状态：数据库、Redis、gRPC 等
    init_health_checker(redis_client=redis_client)
    logger.info("Health checker initialized")

    # 4. 缓存管理器（工具 Schema、模型列表缓存）
    # 多级缓存：本地内存 + Redis
    from app.core.cache import init_cache_manager
    init_cache_manager(redis_client)
    logger.info("Cache manager initialized")

    # 5. Step 缓冲区（用于批量和异步持久化）
    # step_buffer = StepBuffer(db_pool)
    # await step_buffer.start()

    # 6. 数据库连接池（使用 asyncpg）
    from app.infrastructure.database import init_database_pool
    await init_database_pool()
    logger.info("Database pool initialized")

    # 7. gRPC 客户端（连接 ToolBus）
    from app.infrastructure.grpc_client import init_grpc_client
    await init_grpc_client()
    logger.info("gRPC client initialized")

    # ─────────────────────────────────────────────────────────────────────
    # Runtime: 处理请求
    # ─────────────────────────────────────────────────────────────────────
    yield

    # ─────────────────────────────────────────────────────────────────────
    # Shutdown: 释放资源
    # ─────────────────────────────────────────────────────────────────────

    # 释放顺序与初始化相反
    if step_buffer:
        await step_buffer.stop()

    from app.infrastructure.grpc_client import close_grpc_client
    from app.infrastructure.database import close_database_pool

    await close_grpc_client()
    await close_database_pool()

    if redis_client:
        await redis_client.close()

    logger.info("Orchestrator shutting down")


def create_app() -> FastAPI:
    """创建 FastAPI 应用

    【工厂函数模式】
    使用工厂函数而非全局 app 对象的原因：
    - 测试时可以创建多个独立实例
    - 支持多环境配置（dev/test/prod 不同 app）
    - 延迟初始化，避免导入时副作用

    Returns:
        配置好的 FastAPI 应用实例
    """
    app = FastAPI(
        title="Agent Orchestrator",
        description="Agent 编排引擎",
        version="1.0.0",
        lifespan=lifespan,  # 使用新的生命周期管理方式
    )

    # ─────────────────────────────────────────────────────────────────────
    # 中间件注册（注意顺序！后添加的先执行）
    # ─────────────────────────────────────────────────────────────────────

    # CORS 中间件 - 处理跨域请求
    # 生产环境应该限制 allow_origins 为具体域名
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应改为具体域名列表
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 自定义中间件（顺序重要：后添加的先执行）
    app.add_middleware(ErrorHandlerMiddleware)  # 统一异常响应格式
    app.add_middleware(TracingMiddleware)  # 追踪信息注入
    app.add_middleware(RateLimitMiddleware)  # 速率限制
    app.add_middleware(RequestMetricsMiddleware)  # Prometheus 指标采集
    app.add_middleware(RequestContextMiddleware)  # 提取 request_id、tenant_id

    # ─────────────────────────────────────────────────────────────────────
    # 路由注册
    # ─────────────────────────────────────────────────────────────────────

    # 健康检查路由（无前缀，便于 K8s 探测）
    app.include_router(health.router, tags=["health"])

    # API v1 路由
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])

    # ─────────────────────────────────────────────────────────────────────
    # Prometheus Metrics 端点
    # ─────────────────────────────────────────────────────────────────────

    # /metrics 端点供 Prometheus 拉取指标
    # 指标包括：请求计数、延迟分布、错误率等
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    return app


# ═══════════════════════════════════════════════════════════════════════════
# 应用实例 - 模块导入时创建
# ═══════════════════════════════════════════════════════════════════════════

app = create_app()


# ═══════════════════════════════════════════════════════════════════════════
# 依赖注入 Getter - 供 FastAPI Depends 使用
# ═══════════════════════════════════════════════════════════════════════════

def get_feature_flags() -> FeatureFlagClient:
    """获取 Feature Flag 客户端

    【依赖注入模式】
    配合 FastAPI Depends 使用：

        @router.get("/feature")
        async def check_feature(ff: FeatureFlagClient = Depends(get_feature_flags)):
            return {"enabled": ff.is_enabled("new_ui")}

    抛出 RuntimeError 而非返回 None 的原因：
    - 明确表示编程错误（未正确初始化）
    - 避免空指针异常传播
    """
    if feature_flags is None:
        raise RuntimeError("Feature flags not initialized")
    return feature_flags


def get_step_buffer() -> StepBuffer:
    """获取 Step 缓冲区"""
    if step_buffer is None:
        raise RuntimeError("Step buffer not initialized")
    return step_buffer


def get_redis() -> Redis:
    """获取 Redis 客户端"""
    if redis_client is None:
        raise RuntimeError("Redis not initialized")
    return redis_client
