"""Model Gateway Service 主入口"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import chat, models
from app.core.config import config
from app.core.logging import setup_logging

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging(config.environment, config.debug)

    logger.info("Model Gateway starting", environment=config.environment, version="1.0.0")

    # TODO: 初始化 Redis 连接
    # TODO: 初始化提供商连接池

    yield

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
