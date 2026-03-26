"""Model Gateway Service 主入口"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.v1 import chat, models
from app.core.config import config
from app.core.logging import setup_logging
from app.router.model_router import get_model_router

logger = structlog.get_logger()

# 全局组件
redis_client: Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global redis_client

    setup_logging(config.environment, config.debug)

    logger.info(
        "Model Gateway starting",
        environment=config.environment,
        version="1.0.0",
    )

    # 1. 初始化 Redis 连接（用于缓存和策略存储）
    redis_client = Redis.from_url(config.redis_url)
    logger.info("Redis connected")

    # 2. 初始化提供商并注册到路由器
    model_router = get_model_router()

    # 注册 Qwen 提供商（主力模型）
    if config.qwen_api_key:
        from app.providers.qwen import QwenProvider
        qwen_provider = QwenProvider(
            api_key=config.qwen_api_key,
            base_url=config.qwen_base_url,
        )
        model_router.register_provider("qwen", qwen_provider)
        logger.info("Qwen provider registered")

    # 注册其他提供商（可扩展）
    # if config.glm_api_key:
    #     from app.providers.glm import GLMProvider
    #     glm_provider = GLMProvider(...)
    #     model_router.register_provider("glm", glm_provider)

    logger.info(
        "Model Gateway initialized",
        providers=model_router.list_available_models(),
    )

    yield

    # Shutdown: 释放资源
    if redis_client:
        await redis_client.close()

    logger.info("Model Gateway shutting down")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="Model Gateway",
        description="模型统一网关服务",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(models.router, prefix="/v1", tags=["models"])
    app.include_router(chat.router, prefix="/v1", tags=["chat"])

    return app


app = create_app()
