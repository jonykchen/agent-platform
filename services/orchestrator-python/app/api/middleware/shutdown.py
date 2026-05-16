"""Shutdown Middleware - 优雅关闭中间件

在服务关闭期间拒绝新请求，返回 503 Service Unavailable。

【工作流程】
┌─────────────────────────────────────────────────────────────────────────────┐
│                      请求处理流程                                            │
│                                                                             │
│  请求到达                                                                    │
│     │                                                                       │
│     ▼                                                                       │
│  检查是否正在关闭                                                            │
│     │                                                                       │
│     ├─── 是 ───► 返回 503 Service Unavailable                              │
│     │              └── {"error": "ERR_SHUTTING_DOWN", ...}                 │
│     │                                                                       │
│     └─── 否 ───► increment() 增加请求计数                                   │
│                     │                                                       │
│                     ▼                                                       │
│                  处理请求                                                   │
│                     │                                                       │
│                     ▼                                                       │
│                  decrement() 减少请求计数                                   │
│                     │                                                       │
│                     ▼                                                       │
│                  返回响应                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

【使用场景】
- Kubernetes Pod 滚动更新时，确保进行中请求完成后再退出
- 避免请求中断导致的业务问题
- 配合健康检查端点实现零停机部署
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import structlog

from app.api.middleware.request_context import get_request_id
from app.core.shutdown import get_shutdown_manager

logger = structlog.get_logger()


class ShutdownMiddleware(BaseHTTPMiddleware):
    """优雅关闭中间件

    在请求开始时检查服务状态：
    - 如果正在关闭，返回 503 Service Unavailable
    - 如果正常运行，增加请求计数并继续处理

    注意：此中间件应该在其他业务中间件之前添加，
    以确保能够正确追踪所有请求。
    """

    async def dispatch(self, request: Request, call_next):
        shutdown_manager = get_shutdown_manager()

        # 检查是否正在关闭
        if shutdown_manager.is_shutting_down():
            logger.warning(
                "Request rejected during shutdown",
                path=request.url.path,
                method=request.method,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": "ERR_SHUTTING_DOWN",
                    "message": "Service is shutting down",
                    "user_message": "服务正在关闭，请稍后重试",
                    "request_id": get_request_id(),
                },
            )

        # 增加请求计数
        try:
            await shutdown_manager.increment()
        except RuntimeError:
            # 刚好在 increment 时开始关闭
            return JSONResponse(
                status_code=503,
                content={
                    "error": "ERR_SHUTTING_DOWN",
                    "message": "Service is shutting down",
                    "user_message": "服务正在关闭，请稍后重试",
                    "request_id": get_request_id(),
                },
            )

        try:
            # 处理请求
            response = await call_next(request)
            return response
        finally:
            # 无论成功或失败，都减少计数
            await shutdown_manager.decrement()
