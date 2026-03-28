"""速率限制中间件

基于租户配额的速率限制，防止资源滥用。
"""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

import structlog

from app.core.exceptions import RateLimitedError
from app.core.quota_manager import TenantQuotaManager, get_quota_manager

logger = structlog.get_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件

    功能：
    1. 检查租户每日 token 配额
    2. 检查请求频率限制（可选）
    3. 返回 429 状态码和 Retry-After 头

    配额检查：
    - 默认每个请求消耗 1 token（粗略估算）
    - 实际 token 消耗在 LangGraph 执行时精确计算
    """

    # 排除的路径（健康检查、metrics 等）
    EXCLUDED_PATHS = [
        "/health",
        "/ready",
        "/metrics",
        "/docs",
        "/openapi.json",
    ]

    # 高消耗操作的路径（消耗更多 token）
    HIGH_COST_PATHS = [
        "/api/v1/chat",
        "/api/v1/agent",
    ]

    def __init__(self, app, quota_manager: TenantQuotaManager | None = None):
        super().__init__(app)
        self.quota_manager = quota_manager or get_quota_manager()

    async def dispatch(self, request: Request, call_next) -> Response:
        # 排除健康检查等路径
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)

        # 获取租户 ID
        tenant_id = request.headers.get("X-Tenant-ID", "")
        if not tenant_id:
            # 无租户 ID 的请求直接放行（由认证层处理）
            return await call_next(request)

        # 计算消耗（高消耗操作预扣更多）
        tokens_cost = 100 if any(request.url.path.startswith(path) for path in self.HIGH_COST_PATHS) else 1

        # 检查配额
        result = await self.quota_manager.check_quota(tenant_id, tokens_cost)

        if not result["allowed"]:
            logger.warning(
                "Rate limit exceeded",
                tenant_id=tenant_id,
                remaining=result["remaining"],
                path=request.url.path,
            )

            # 返回 429 状态码
            retry_after = 60  # 60 秒后重试
            raise RateLimitedError(retry_after=retry_after)

        # 执行请求
        response = await call_next(request)

        # 响应头添加配额信息
        response.headers["X-RateLimit-Remaining"] = str(result["remaining"])

        return response


# 全局配额管理器实例
_quota_manager: TenantQuotaManager | None = None


def get_quota_manager() -> TenantQuotaManager:
    """获取配额管理器实例"""
    global _quota_manager
    if _quota_manager is None:
        from app.main import get_redis
        redis = get_redis()
        _quota_manager = TenantQuotaManager(redis)
    return _quota_manager


def init_quota_manager(redis) -> TenantQuotaManager:
    """初始化配额管理器"""
    global _quota_manager
    _quota_manager = TenantQuotaManager(redis)
    return _quota_manager