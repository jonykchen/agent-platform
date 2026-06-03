"""gRPC 服务端模块

提供 Orchestrator gRPC 服务端实现，供 Gateway Java 调用。

关键组件：
- server: gRPC 服务器管理
- servicers: 服务实现（OrchestratorServicer, HealthServicer）
- interceptors: 拦截器（追踪、日志）
- utils: 工具函数（错误映射、上下文提取）
"""

from app.grpc.server import GrpcServer

__all__ = ["GrpcServer"]
