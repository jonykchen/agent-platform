"""健康检查路由

提供三类探针端点，供负载均衡 / 编排平台探测：
- /health/live  存活探针：进程是否存活（不依赖外部资源，永远快速返回）
- /health/ready 就绪探针：关键依赖（数据库）是否可用，不可用则摘流
- /health       兼容端点：等价于 ready，便于简单探测

与平台其他服务（orchestrator）保持一致的探针语义。
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Response, status

from app.indexers.vector_indexer import get_vector_indexer

logger = structlog.get_logger()

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict:
    """存活探针：仅表示进程存活，不探测外部依赖。"""
    return {"status": "alive", "service": "knowledge"}


async def _check_database() -> bool:
    """检测数据库连接池是否可用（执行轻量 SELECT 1）。"""
    try:
        indexer = get_vector_indexer()
        pool = await indexer._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:  # noqa: BLE001 - 健康检查需吞掉所有异常并转为不就绪
        logger.warning("health_db_check_failed", error=str(e))
        return False


@router.get("/health/ready")
async def readiness(response: Response) -> dict:
    """就绪探针：数据库不可用时返回 503，触发摘流。"""
    db_ok = await _check_database()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "checks": {"database": "down"}}
    return {"status": "ready", "checks": {"database": "up"}}


@router.get("/health")
async def health(response: Response) -> dict:
    """兼容端点：等价于就绪探针。"""
    return await readiness(response)
