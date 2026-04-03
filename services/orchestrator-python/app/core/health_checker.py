"""健康检查器

检查各依赖服务的健康状态，支持三级健康检查。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
import structlog

from app.core.config import config

logger = structlog.get_logger()


class HealthStatus(str, Enum):
    """健康状态"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """组件健康状态"""

    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": round(self.latency_ms, 2),
            "details": self.details,
        }


class HealthChecker:
    """健康检查器

    检查 Redis、ModelGateway、ToolBus、Database 等依赖。
    """

    def __init__(
        self,
        redis_client=None,
        db_pool=None,
    ):
        self.redis_client = redis_client
        self.db_pool = db_pool
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        return self._http_client

    async def close(self):
        """关闭客户端"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def check_redis(self) -> ComponentHealth:
        """检查 Redis 连接"""
        start = time.monotonic()

        try:
            if self.redis_client is None:
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    message="Redis client not initialized",
                )

            # 执行 PING 命令
            await self.redis_client.ping()

            latency = (time.monotonic() - start) * 1000

            return ComponentHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Connected",
                latency_ms=latency,
            )

        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Connection failed: {str(e)[:50]}",
            )

    async def check_model_gateway(self) -> ComponentHealth:
        """检查 ModelGateway 服务"""
        start = time.monotonic()

        try:
            client = await self._get_http_client()

            # 调用健康检查端点
            response = await client.get(
                f"{config.model_gateway_url}/health",
                timeout=5.0,
            )

            latency = (time.monotonic() - start) * 1000

            if response.status_code == 200:
                return ComponentHealth(
                    name="model_gateway",
                    status=HealthStatus.HEALTHY,
                    message="Connected",
                    latency_ms=latency,
                )
            else:
                return ComponentHealth(
                    name="model_gateway",
                    status=HealthStatus.DEGRADED,
                    message=f"Unexpected status: {response.status_code}",
                    latency_ms=latency,
                )

        except httpx.TimeoutException:
            latency = (time.monotonic() - start) * 1000
            return ComponentHealth(
                name="model_gateway",
                status=HealthStatus.UNHEALTHY,
                message="Connection timeout",
                latency_ms=latency,
            )

        except Exception as e:
            logger.error("ModelGateway health check failed", error=str(e))
            return ComponentHealth(
                name="model_gateway",
                status=HealthStatus.UNHEALTHY,
                message=f"Connection failed: {str(e)[:50]}",
            )

    async def check_tool_bus(self) -> ComponentHealth:
        """检查 ToolBus gRPC 服务"""
        start = time.monotonic()

        try:
            import grpc
            from grpc.health.v1 import health_pb2, health_pb2_grpc

            channel = grpc.aio.insecure_channel(config.tool_bus_grpc_addr)
            stub = health_pb2_grpc.HealthStub(channel)

            # 调用 gRPC 健康检查
            request = health_pb2.HealthCheckRequest(service="toolbus.ToolBusService")
            response = await asyncio.wait_for(
                stub.Check(request),
                timeout=5.0,
            )

            latency = (time.monotonic() - start) * 1000
            await channel.close()

            if response.status == health_pb2.HealthCheckResponse.SERVING:
                return ComponentHealth(
                    name="tool_bus",
                    status=HealthStatus.HEALTHY,
                    message="Serving",
                    latency_ms=latency,
                )
            else:
                return ComponentHealth(
                    name="tool_bus",
                    status=HealthStatus.DEGRADED,
                    message=f"Status: {health_pb2.HealthCheckResponse.ServingStatus.Name(response.status)}",
                    latency_ms=latency,
                )

        except asyncio.TimeoutError:
            latency = (time.monotonic() - start) * 1000
            return ComponentHealth(
                name="tool_bus",
                status=HealthStatus.UNHEALTHY,
                message="Connection timeout",
                latency_ms=latency,
            )

        except ImportError:
            return ComponentHealth(
                name="tool_bus",
                status=HealthStatus.DEGRADED,
                message="gRPC health check not available",
            )

        except Exception as e:
            logger.error("ToolBus health check failed", error=str(e))
            return ComponentHealth(
                name="tool_bus",
                status=HealthStatus.UNHEALTHY,
                message=f"Connection failed: {str(e)[:50]}",
            )

    async def check_database(self) -> ComponentHealth:
        """检查数据库连接"""
        start = time.monotonic()

        try:
            if self.db_pool is None:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.DEGRADED,
                    message="Database pool not initialized",
                )

            # 执行简单查询
            async with self.db_pool.acquire() as conn:
                await conn.execute("SELECT 1")

            latency = (time.monotonic() - start) * 1000

            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Connected",
                latency_ms=latency,
            )

        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Connection failed: {str(e)[:50]}",
            )

    async def check_all(self) -> dict[str, Any]:
        """检查所有依赖"""
        start = time.monotonic()

        # 并行检查
        results = await asyncio.gather(
            self.check_redis(),
            self.check_model_gateway(),
            self.check_tool_bus(),
            self.check_database(),
            return_exceptions=True,
        )

        components = []
        for result in results:
            if isinstance(result, Exception):
                components.append(
                    ComponentHealth(
                        name="unknown",
                        status=HealthStatus.UNHEALTHY,
                        message=f"Check failed: {str(result)[:50]}",
                    )
                )
            else:
                components.append(result)

        # 计算整体状态
        overall_status = HealthStatus.HEALTHY
        for comp in components:
            if comp.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
                break
            elif comp.status == HealthStatus.DEGRADED:
                overall_status = HealthStatus.DEGRADED

        total_latency = (time.monotonic() - start) * 1000

        return {
            "status": overall_status.value,
            "total_latency_ms": round(total_latency, 2),
            "components": [c.to_dict() for c in components],
        }

    async def check_readiness(self) -> tuple[bool, dict[str, Any]]:
        """检查就绪状态（用于 Kubernetes readiness probe）

        Returns:
            (is_ready, details)
        """
        # 只检查关键依赖
        redis_health = await self.check_redis()
        model_health = await self.check_model_gateway()

        is_ready = (
            redis_health.status != HealthStatus.UNHEALTHY
            and model_health.status != HealthStatus.UNHEALTHY
        )

        details = {
            "redis": redis_health.status.value,
            "model_gateway": model_health.status.value,
        }

        return is_ready, details


# 全局健康检查器实例
_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """获取健康检查器实例"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def init_health_checker(redis_client=None, db_pool=None) -> HealthChecker:
    """初始化健康检查器"""
    global _health_checker
    _health_checker = HealthChecker(redis_client=redis_client, db_pool=db_pool)
    return _health_checker
