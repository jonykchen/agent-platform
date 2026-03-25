"""Health API - 三级健康检查

支持 Kubernetes 探针和运维监控。

/health/live  - Liveness（进程存活）
/health/ready - Readiness（关键依赖可用）
/health/deep  - Deep（详细依赖状态）
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.core.health_checker import get_health_checker, HealthStatus

router = APIRouter()


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    service: str
    version: str
    timestamp: int


class DeepHealthResponse(BaseModel):
    """详细健康检查响应"""

    status: str
    service: str
    version: str
    timestamp: int
    total_latency_ms: float
    components: list[dict]


class ReadinessResponse(BaseModel):
    """就绪检查响应"""

    ready: bool
    service: str
    version: str
    timestamp: int
    components: dict[str, str]


@router.get("/health/live", response_model=HealthResponse)
async def liveness():
    """存活检查 - Kubernetes liveness probe

    只检查进程是否存活，不检查依赖。
    """
    return HealthResponse(
        status="UP",
        service="orchestrator-python",
        version="1.0.0",
        timestamp=int(1000 * time.time()),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(response: Response):
    """就绪检查 - Kubernetes readiness probe

    检查关键依赖（Redis、ModelGateway）是否可用。
    如果不可用，返回 503 状态码。
    """
    checker = get_health_checker()
    is_ready, details = await checker.check_readiness()

    if not is_ready:
        response.status_code = 503

    return ReadinessResponse(
        ready=is_ready,
        service="orchestrator-python",
        version="1.0.0",
        timestamp=int(1000 * time.time()),
        components=details,
    )


@router.get("/health/deep", response_model=DeepHealthResponse)
async def deep_health(response: Response):
    """深度健康检查

    检查所有依赖的详细状态。
    如果有 unhealthy 组件，返回 503 状态码。
    """
    checker = get_health_checker()
    result = await checker.check_all()

    if result["status"] == HealthStatus.UNHEALTHY.value:
        response.status_code = 503

    return DeepHealthResponse(
        status=result["status"],
        service="orchestrator-python",
        version="1.0.0",
        timestamp=int(1000 * time.time()),
        total_latency_ms=result["total_latency_ms"],
        components=result["components"],
    )


# 兼容旧端点
@router.get("/health", response_model=HealthResponse)
async def health():
    """健康检查（兼容旧端点）"""
    return HealthResponse(
        status="UP",
        service="orchestrator-python",
        version="1.0.0",
        timestamp=int(1000 * time.time()),
    )


@router.get("/ready", response_model=HealthResponse)
async def ready():
    """就绪检查（兼容旧端点）"""
    return HealthResponse(
        status="READY",
        service="orchestrator-python",
        version="1.0.0",
        timestamp=int(1000 * time.time()),
    )