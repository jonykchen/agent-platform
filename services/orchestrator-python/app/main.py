"""Orchestrator Service 主入口"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import chat, health
from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.api.middleware.request_context import RequestContextMiddleware
from app.core.config import config
from app.core.logging import setup_logging

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging(config.environment, config.debug)

    logger.info(
        "Orchestrator starting",
        environment=config.environment,
        version="1.0.0",
    )

    # TODO: 初始化数据库连接池
    # TODO: 初始化 Redis 连接
    # TODO: 初始化 gRPC 客户端

    yield

    # 清理资源
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
