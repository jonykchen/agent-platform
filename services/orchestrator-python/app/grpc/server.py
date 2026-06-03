"""gRPC 服务器管理

实现生产级 gRPC 服务器，支持：
- 异步处理
- 健康检查
- 优雅关闭
- 追踪集成

【核心概念】gRPC Server 生命周期
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

gRPC 服务器启动流程：
1. 创建 Server 并配置选项（消息大小、Keepalive）
2. 注册 Servicer（业务逻辑）
3. 注册健康检查服务
4. 添加监听端口
5. 启动 Server（异步）
6. 等待请求

关闭流程：
1. 接收关闭信号（SIGTERM/SIGINT）
2. 停止接收新请求
3. 等待活跃请求完成（grace period）
4. 强制关闭剩余请求
5. 清理资源

【配置选项】
┌─────────────────────────────────────────────────────────────────────────┐
│ 选项                           │ 说明                                  │
├────────────────────────────────┼────────────────────────────────────────┤
│ max_receive_message_length     │ 最大接收消息大小（16MB）               │
│ max_send_message_length        │ 最大发送消息大小（16MB）               │
│ keepalive_time_ms              │ Keepalive 心跳间隔（30s）             │
│ keepalive_timeout_ms           │ Keepalive 超时（10s）                  │
│ keepalive_permit_without_calls │ 无调用时也发心跳                       │
└─────────────────────────────────────────────────────────────────────────┘

【参考】
- gRPC Python 异步: https://grpc.github.io/grpc/python/grpc_asyncio.html
- gRPC 最佳实践: https://grpc.io/docs/guides/
"""

import asyncio
import signal
from typing import Optional

import grpc
from grpc import aio
import structlog

from app.gen.gateway import orchestrator_pb2_grpc
from app.grpc.servicers.orchestrator_servicer import OrchestratorServiceServicer
from app.grpc.servicers.health_servicer import HealthServicer
from app.grpc.interceptors.tracing_interceptor import TracingInterceptor
from app.core.config import config

logger = structlog.get_logger()


class GrpcServer:
    """gRPC 服务器管理器

    生产级特性：
    1. 异步处理 - 支持 LangGraph 异步调用
    2. 健康检查 - 集成 gRPC Health Checking
    3. 优雅关闭 - 等待活跃请求完成
    4. 追踪集成 - OpenTelemetry 自动埋点

    使用方式：
    ```python
    # 启动
    grpc_server = GrpcServer(port=50051)
    await grpc_server.start()

    # 等待关闭信号
    await grpc_server.wait_for_termination()

    # 主动关闭
    await grpc_server.stop(grace_period=5)
    ```
    """

    def __init__(self, port: int = 50051):
        """初始化 gRPC 服务器

        Args:
            port: 监听端口
        """
        self.port = port
        self.server: Optional[aio.Server] = None
        self.health_servicer: Optional[HealthServicer] = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """启动 gRPC 服务器"""
        # 创建拦截器
        interceptors = [TracingInterceptor(service_name="orchestrator-python")]

        # 创建异步服务器
        self.server = aio.server(
            interceptors=interceptors,
            options=[
                # 消息大小限制
                ("grpc.max_receive_message_length", config.grpc_max_message_size),
                ("grpc.max_send_message_size", config.grpc_max_message_size),
                # Keepalive 配置
                ("grpc.keepalive_time_ms", config.grpc_keepalive_time_ms),
                ("grpc.keepalive_timeout_ms", config.grpc_keepalive_timeout_ms),
                ("grpc.keepalive_permit_without_calls", True),
                # HTTP/2 配置
                ("grpc.http2.max_pings_without_data", 0),
                ("grpc.http2.min_time_between_pings_ms", 10000),
                ("grpc.http2.min_ping_interval_without_data_ms", 5000),
            ],
        )

        # 注册 Orchestrator Servicer
        orchestrator_servicer = OrchestratorServiceServicer()
        orchestrator_pb2_grpc.add_OrchestratorServiceServicer_to_server(
            orchestrator_servicer, self.server
        )

        # 注册健康检查服务
        self.health_servicer = HealthServicer()
        from grpc.health.v1 import health_pb2_grpc
        health_pb2_grpc.add_HealthServicer_to_server(self.health_servicer, self.server)

        # 启动服务器
        listen_addr = f"[::]:{self.port}"
        self.server.add_insecure_port(listen_addr)

        await self.server.start()

        logger.info(
            "grpc_server_started",
            port=self.port,
            address=listen_addr,
            interceptors=len(interceptors),
        )

        # 注册信号处理（优雅关闭）
        self._register_signal_handlers()

    async def wait_for_termination(self) -> None:
        """等待服务器终止"""
        await self._shutdown_event.wait()

    async def stop(self, grace_period: int = 5) -> None:
        """优雅关闭服务器

        Args:
            grace_period: 等待活跃请求完成的秒数
        """
        if self.server is None:
            return

        logger.info(
            "grpc_server_shutting_down",
            grace_period=grace_period,
        )

        # 设置健康状态为 NOT_SERVING
        if self.health_servicer:
            self.health_servicer.set_status("", grpc.health.v1.health_pb2.HealthCheckResponse.NOT_SERVING)
            self.health_servicer.set_status(
                "gateway.OrchestratorService",
                grpc.health.v1.health_pb2.HealthCheckResponse.NOT_SERVING,
            )

        # 优雅关闭
        await self.server.stop(grace_period)

        logger.info("grpc_server_stopped")
        self._shutdown_event.set()

    def _register_signal_handlers(self) -> None:
        """注册信号处理器（用于优雅关闭）"""
        loop = asyncio.get_running_loop()

        def handle_signal(sig):
            logger.info("grpc_signal_received", signal=sig.name)
            asyncio.create_task(self.stop(grace_period=5))

        # 注册 SIGTERM 和 SIGINT 处理
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, handle_signal, sig)

    def set_health_status(self, service: str, status: int) -> None:
        """设置健康状态

        Args:
            service: 服务名（"" 表示全局）
            status: 状态码
        """
        if self.health_servicer:
            self.health_servicer.set_status(service, status)


# 全局 gRPC 服务器实例（用于生命周期管理）
_grpc_server: Optional[GrpcServer] = None


def get_grpc_server() -> Optional[GrpcServer]:
    """获取全局 gRPC 服务器实例"""
    return _grpc_server


async def start_grpc_server() -> GrpcServer:
    """启动 gRPC 服务器

    Returns:
        GrpcServer 实例
    """
    global _grpc_server

    if not config.grpc_enabled:
        logger.info("grpc_server_disabled")
        return None

    _grpc_server = GrpcServer(port=config.grpc_port)
    await _grpc_server.start()

    return _grpc_server


async def stop_grpc_server(grace_period: int = 5) -> None:
    """停止 gRPC 服务器

    Args:
        grace_period: 优雅关闭等待时间（秒）
    """
    global _grpc_server

    if _grpc_server:
        await _grpc_server.stop(grace_period)
        _grpc_server = None