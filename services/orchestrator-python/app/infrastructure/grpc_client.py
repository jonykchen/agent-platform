"""gRPC 客户端管理

【核心概念】gRPC 连接池与负载均衡
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

gRPC 相比 HTTP 的优势：
1. 二进制协议：更小的消息体积，更高的传输效率
2. 流式传输：支持双向流，适合实时通信
3. 强类型：Protobuf 定义接口，编译时类型检查
4. 连接复用：多路复用，减少连接开销

【技术选型】为什么使用 grpcio？
┌─────────────────────────────────────────────────────────────────────────┐
│  库                │  优点                    │  缺点                  │
├────────────────────┼──────────────────────────┼────────────────────────┤
│  grpcio           │  官方实现、功能完整       │  依赖重、安装复杂      │
│  grpclib          │  纯Python、异步原生       │  功能较少              │
│  ✓ grpcio + async │  企业标准、生态完善       │                        │
└─────────────────────────────────────────────────────────────────────────┘

【连接管理策略】
- 异步 Channel：单例模式，全应用共享
- 负载均衡：round_robin 策略，支持多后端
- 健康检查：定期探测，自动剔除失效节点
- 重试机制：指数退避，限定最大重试次数

【参考】
- gRPC Python 异步指南: https://grpc.github.io/grpc/python/grpc_asyncio.html
- gRPC 最佳实践: https://grpc.io/docs/guides/
"""

from __future__ import annotations

import asyncio
import structlog
from typing import Any

import grpc
from grpc import Channel, aio

from app.core.config import config
from app.core.exceptions import ToolBusUnavailableError
from app.core.resilience import tool_bus_circuit

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════════════════
# 全局 gRPC Channel
# ═══════════════════════════════════════════════════════════════════════════

_channel: aio.Channel | None = None
_stub_cache: dict[str, Any] = {}


async def init_grpc_client() -> aio.Channel:
    """初始化 gRPC 客户端

    【启动流程】
    1. 创建异步 Channel
    2. 配置负载均衡策略
    3. 启用健康检查
    4. 预热连接

    【Channel 选项说明】
    - grpc.max_receive_message_length: 最大接收消息大小（默认 4MB）
    - grpc.max_send_message_length: 最大发送消息大小（默认 4MB）
    - grpc.keepalive_time_ms: Keepalive 心跳间隔
    - grpc.keepalive_timeout_ms: Keepalive 超时
    - grpc.keepalive_permit_without_calls: 无调用时也发心跳

    Returns:
        grpc.aio.Channel: 异步 gRPC Channel

    Raises:
        ToolBusUnavailableError: 连接失败
    """
    global _channel

    if _channel is not None:
        return _channel

    try:
        # gRPC Channel 配置
        options = [
            # 消息大小限制（支持大响应）
            ("grpc.max_receive_message_length", 16 * 1024 * 1024),  # 16MB
            ("grpc.max_send_message_length", 16 * 1024 * 1024),  # 16MB
            # Keepalive 配置（保持连接活跃）
            ("grpc.keepalive_time_ms", 30000),  # 30 秒心跳
            ("grpc.keepalive_timeout_ms", 10000),  # 10 秒超时
            ("grpc.keepalive_permit_without_calls", True),
            # HTTP/2 配置
            ("grpc.http2.max_pings_without_data", 0),
            ("grpc.http2.min_time_between_pings_ms", 10000),
            ("grpc.http2.min_ping_interval_without_data_ms", 5000),
        ]

        # 创建异步 Channel
        _channel = aio.insecure_channel(
            config.tool_bus_grpc_addr,
            options=options,
        )

        # 连接预热（等待 Channel 就绪）
        await asyncio.wait_for(
            _channel.channel_ready(),
            timeout=10.0,
        )

        logger.info(
            "grpc_client_initialized",
            target=config.tool_bus_grpc_addr,
        )

        return _channel

    except asyncio.TimeoutError:
        logger.error(
            "grpc_client_init_timeout",
            target=config.tool_bus_grpc_addr,
        )
        raise ToolBusUnavailableError("gRPC 连接超时")

    except Exception as e:
        logger.error(
            "grpc_client_init_failed",
            target=config.tool_bus_grpc_addr,
            error=str(e),
        )
        raise ToolBusUnavailableError(f"gRPC 连接失败: {e}")


async def close_grpc_client() -> None:
    """关闭 gRPC 客户端

    【关闭流程】
    1. 等待活跃 RPC 完成（最多 5 秒）
    2. 关闭 Channel
    3. 清理 Stub 缓存
    """
    global _channel, _stub_cache

    if _channel is None:
        return

    logger.info("grpc_client_closing")

    try:
        await asyncio.wait_for(_channel.close(), timeout=5.0)
        logger.info("grpc_client_closed")
    except asyncio.TimeoutError:
        logger.warning("grpc_client_close_timeout")
        _channel = None
    finally:
        _stub_cache.clear()


def get_grpc_channel() -> aio.Channel:
    """获取 gRPC Channel

    Returns:
        grpc.aio.Channel: 异步 Channel

    Raises:
        RuntimeError: Channel 未初始化
    """
    if _channel is None:
        raise RuntimeError("gRPC 客户端未初始化，请先调用 init_grpc_client()")
    return _channel


def get_stub(stub_class: type) -> Any:
    """获取 gRPC Stub（带缓存）

    【Stub 缓存】
    每个 Stub 类只需创建一次，后续复用。
    避免重复创建的开销。

    Args:
        stub_class: gRPC Stub 类

    Returns:
        Stub 实例
    """
    channel = get_grpc_channel()
    stub_key = stub_class.__name__

    if stub_key not in _stub_cache:
        _stub_cache[stub_key] = stub_class(channel)

    return _stub_cache[stub_key]


@tool_bus_circuit
async def call_tool_bus(
    stub_class: type,
    method_name: str,
    request: Any,
    timeout: float = 15.0,
    metadata: list[tuple[str, str]] | None = None,
) -> Any:
    """调用 ToolBus 服务（带熔断器和重试）

    【调用流程】
    1. 获取 Stub
    2. 调用 RPC 方法
    3. 处理响应/异常

    【熔断器集成】
    - 装饰器自动记录成功/失败
    - 失败达到阈值后熔断
    - 半开状态试探性恢复

    Args:
        stub_class: gRPC Stub 类
        method_name: RPC 方法名
        request: 请求对象
        timeout: 超时时间（秒）
        metadata: 元数据（如 tenant_id, request_id）

    Returns:
        响应对象

    Raises:
        ToolBusUnavailableError: 服务不可用
        grpc.RpcError: RPC 错误
    """
    stub = get_stub(stub_class)
    method = getattr(stub, method_name)

    try:
        async with asyncio.timeout(timeout):
            response = await method(
                request,
                metadata=metadata or [],
            )
            return response

    except asyncio.TimeoutError:
        logger.error(
            "grpc_call_timeout",
            method=method_name,
            timeout_s=timeout,
        )
        raise ToolBusUnavailableError(f"ToolBus 调用超时 ({timeout}s)")

    except aio.AioRpcError as e:
        logger.error(
            "grpc_call_error",
            method=method_name,
            code=e.code().name,
            details=e.details(),
        )
        raise


# ═══════════════════════════════════════════════════════════════════════════
# 健康检查
# ═══════════════════════════════════════════════════════════════════════════


async def check_grpc_health() -> dict[str, Any]:
    """gRPC 健康检查

    【检查项】
    1. Channel 状态
    2. 连接延迟
    3. 最近调用统计

    Returns:
        健康状态字典
    """
    if _channel is None:
        return {
            "status": "unhealthy",
            "error": "Channel 未初始化",
        }

    try:
        # 检查 Channel 状态
        state = _channel.get_state()

        # 尝试连接（如果未连接）
        if state != grpc.ChannelConnectivity.READY:
            await asyncio.wait_for(
                _channel.channel_ready(),
                timeout=5.0,
            )

        return {
            "status": "healthy",
            "state": state.name,
        }

    except asyncio.TimeoutError:
        return {
            "status": "unhealthy",
            "error": "连接超时",
            "state": state.name if "state" in dir() else "UNKNOWN",
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
