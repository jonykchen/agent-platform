"""gRPC 健康检查服务

实现 gRPC 标准健康检查协议，供 Kubernetes 探测使用。

【核心概念】gRPC Health Checking
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

gRPC 健康检查使用标准协议：
- 服务名: "" 表示全局健康状态
- 状态: UNKNOWN / SERVING / NOT_SERVING / SERVICE_UNKNOWN

Kubernetes 可以配置：
- startupProbe: 启动探测
- readinessProbe: 就绪探测
- livenessProbe: 存活探测

【健康状态映射】
┌─────────────────────────────────────────────────────────────────────────┐
│ 内部状态         │ gRPC Health Status │ 说明                          │
├───────────────────┼────────────────────┼────────────────────────────────┤
│ HEALTHY          │ SERVING            │ 正常服务                       │
│ DEGRADED         │ SERVING            │ 降级服务（部分功能受限）        │
│ UNHEALTHY        │ NOT_SERVING        │ 不提供服务                     │
└─────────────────────────────────────────────────────────────────────────┘

【参考】
- gRPC Health Checking: https://grpc.io/blog/grpc-health-check/
- proto 定义: grpc.health.v1.health.proto
"""

from typing import Dict

from grpc.health.v1 import health_pb2, health_pb2_grpc
from grpc import aio

import structlog

logger = structlog.get_logger()


class HealthServicer(health_pb2_grpc.HealthServicer):
    """健康检查服务实现

    支持的服务状态：
    - UNKNOWN: 未知
    - SERVING: 正常服务
    - NOT_SERVING: 不提供服务
    - SERVICE_UNKNOWN: 服务未知

    使用方式：
    ```python
    from grpc.health.v1 import health_pb2_grpc
    health_servicer = HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    ```
    """

    def __init__(self):
        # 初始化服务状态
        # "" 表示全局健康状态
        self._status: Dict[str, int] = {
            "": health_pb2.HealthCheckResponse.SERVING,
            "gateway.OrchestratorService": health_pb2.HealthCheckResponse.SERVING,
        }

    async def Check(
        self,
        request: health_pb2.HealthCheckRequest,
        context: aio.ServicerContext,
    ) -> health_pb2.HealthCheckResponse:
        """检查服务健康状态

        Args:
            request: 健康检查请求，包含服务名
            context: gRPC 上下文

        Returns:
            HealthCheckResponse 包含状态码
        """
        service = request.service or ""  # 空字符串表示全局状态
        status = self._status.get(service, health_pb2.HealthCheckResponse.SERVICE_UNKNOWN)

        logger.debug(
            "grpc_health_check",
            service=service,
            status=self._status_to_string(status),
        )

        return health_pb2.HealthCheckResponse(status=status)

    async def Watch(
        self,
        request: health_pb2.HealthCheckRequest,
        context: aio.ServicerContext,
    ):
        """监控服务健康状态（流式）

        暂未实现完整的服务端流式监控。
        返回 NOT_SERVING 表示不支持。
        """
        yield health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.NOT_SERVING
        )

    def set_status(self, service: str, status: int) -> None:
        """设置服务状态

        用于外部组件（如健康检查器）更新服务状态。

        Args:
            service: 服务名（"" 表示全局）
            status: 状态码
        """
        self._status[service] = status
        logger.info(
            "grpc_health_status_changed",
            service=service,
            status=self._status_to_string(status),
        )

    def get_status(self, service: str = "") -> int:
        """获取服务状态

        Args:
            service: 服务名

        Returns:
            状态码
        """
        return self._status.get(service, health_pb2.HealthCheckResponse.SERVICE_UNKNOWN)

    @staticmethod
    def _status_to_string(status: int) -> str:
        """状态码转字符串

        Args:
            status: 状态码

        Returns:
            状态名称
        """
        return {
            health_pb2.HealthCheckResponse.UNKNOWN: "UNKNOWN",
            health_pb2.HealthCheckResponse.SERVING: "SERVING",
            health_pb2.HealthCheckResponse.NOT_SERVING: "NOT_SERVING",
            health_pb2.HealthCheckResponse.SERVICE_UNKNOWN: "SERVICE_UNKNOWN",
        }.get(status, "UNKNOWN")
