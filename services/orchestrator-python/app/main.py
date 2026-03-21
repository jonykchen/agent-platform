"""Orchestrator Service 主入口"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.v1 import chat, health
from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.api.middleware.request_context import RequestContextMiddleware
from app.core.config import config
from app.core.feature_flags import FeatureFlagClient
from app.core.logging import setup_logging
from app.core.step_buffer import StepBuffer

logger = structlog.get_logger()

# 全局组件
redis_client: Redis | None = None
feature_flags: FeatureFlagClient | None = None
step_buffer: StepBuffer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global redis_client, feature_flags, step_buffer

    setup_logging(config.environment, config.debug)

    logger.info(
        "Orchestrator starting",
        environment=config.environment,
        version="1.0.0",
    )

    # 初始化 Redis 连接
    redis_client = Redis.from_url(config.redis_url)
    feature_flags = FeatureFlagClient(redis_client)
    logger.info("Redis connected")

    # 初始化 Step 缓冲区（需要在实际使用时传入 db_pool）
    # step_buffer = StepBuffer(db_pool)
    # await step_buffer.start()

    # TODO: 初始化数据库连接池
    # TODO: 初始化 gRPC 客户端

    yield

    # 清理资源
    if step_buffer:
        await step_buffer.stop()
    if redis_client:
        await redis_client.close()

    logger.info("Orchestrator shutting down")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="Agent Orchestrator",
        description="Agent 编排引擎",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 自定义中间件
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RequestContextMiddleware)

    # 注册路由
    app.include_router(health.router, tags=["health"])
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])

    return app


app = create_app()


def get_feature_flags() -> FeatureFlagClient:
    """获取 Feature Flag 客户端"""
    if feature_flags is None:
        raise RuntimeError("Feature flags not initialized")
    return feature_flags


def get_step_buffer() -> StepBuffer:
    """获取 Step 缓冲区"""
    if step_buffer is None:
        raise RuntimeError("Step buffer not initialized")
    return step_buffer
