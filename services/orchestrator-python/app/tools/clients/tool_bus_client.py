"""ToolBus gRPC 客户端

通过 gRPC 调用 ToolBus 服务执行工具。
支持熔断器、重试、超时配置。

【核心概念】客户端在架构中的位置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│                          Agent 工具调用链                                    │
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │   Orchestrator   │                                                       │
│  │    (Python)       │                                                       │
│  │    Agent 编排     │                                                       │
│  └────────┬─────────┘                                                       │
│           │ gRPC (本客户端)                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐      gRPC/HTTP      ┌──────────────────┐             │
│  │    Tool Bus       │ ──────────────────► │   Governance     │             │
│  │    (Java)          │      审批请求       │    (Java)        │             │
│  │    工具执行中心    │                     │    风控审批       │             │
│  └────────┬─────────┘                      └──────────────────┘             │
│           │ HTTP                                                            │
│           ▼                                                                 │
│  ┌──────────────────┐                                                       │
│  │  外部工具服务     │                                                       │
│  │  (订单、用户等)   │                                                       │
│  └──────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

本客户端（ToolBusClient）位于 Orchestrator → Tool Bus 调用链：
- Agent 节点决定调用工具时，通过本客户端发送 gRPC 请求
- ToolBus 执行工具并返回结果，可能触发审批流程

【技术选型】gRPC vs HTTP 对比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 维度               │ gRPC (当前选择)             │ HTTP                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 协议               │ HTTP/2 + Protobuf           │ HTTP/1.1 + JSON             │
│ 性能               │ 高（二进制、多路复用）      │ 中等                        │
│ 类型安全           │ 强（Proto 定义）            │ 弱（运行时校验）            │
│ 双向流             │ 原生支持                    │ 需要额外实现                │
│ 调试难度           │ 较高（需要工具）            │ 低（可读文本）              │
│ 跨语言调用         │ 需要 Proto 定义             │ 简单（curl/Postman）        │
│ 适用场景           │ 内部高频调用                │ 外部 API                    │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【为什么 ToolBus 使用 gRPC？】
1. 内部服务调用，高频低延迟要求
2. Protobuf 强类型，避免接口不一致
3. 双向流支持，未来可扩展实时工具推送
4. 多路复用，批量工具调用时性能优势明显

【熔断器配置说明】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬───────────────┬─────────────────────────────────────────┐
│ 参数               │ 默认值        │ 说明                                    │
├────────────────────┼───────────────┼─────────────────────────────────────────┤
│ failure_threshold  │ 5             │ 连续失败 5 次后触发熔断                 │
│ recovery_timeout   │ 30s           │ 熔断后等待 30s 尝试恢复                 │
│ timeout_s          │ 15            │ 工具调用超时（S-AGENT-08）              │
│ retry_attempts     │ 3             │ 最大重试次数                            │
└────────────────────┴───────────────┴─────────────────────────────────────────┘

【降级策略】工具调用失败时的应对方案
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│                          工具调用降级流程                                    │
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │  Agent 请求工具  │                                                       │
│  │  query_order     │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐                                                       │
│  │  ToolBus 调用    │      成功      ┌──────────────────┐                   │
│  │                  │ ──────────► │  返回结果        │                   │
│  └────────┬─────────┘              └──────────────────┘                   │
│           │ 失败                                                            │
│           ▼                                                                 │
│  ┌──────────────────┐                                                       │
│  │  错误类型判断    │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│     ┌─────┴─────┬─────────────┬─────────────┐                              │
│     │           │             │             │                              │
│     ▼           ▼             ▼             ▼                              │
│  ┌────────┐ ┌────────┐ ┌────────────┐ ┌────────────┐                       │
│  │ 超时   │ │ 熔断   │ │ 服务不可用 │ │ 其他错误   │                       │
│  └────┬───┘ └────┬───┘ └─────┬──────┘ └─────┬──────┘                       │
│       │          │            │              │                             │
│       │          │            │              ▼                             │
│       │          │            │      ┌──────────────┐                      │
│       │          │            │      │ 返回错误信息 │                      │
│       │          │            │      │ 给 Agent     │                      │
│       │          │            │      └──────────────┘                      │
│       │          │            │                                              │
│       └──────────┴────────────┴───► 返回错误码 + 用户友好提示              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

【降级响应格式】
┌────────────────────┬─────────────────────────────────────────────────────────┐
│ 错误类型           │ 响应内容                                                │
├────────────────────┼─────────────────────────────────────────────────────────┤
│ ERR_TIMEOUT        │ "工具执行超时，请稍后重试"                               │
│ ERR_CIRCUIT_OPEN   │ "服务暂时不可用，请稍后重试"                             │
│ ERR_SERVICE_UNAVAIL│ "工具服务不可用"                                         │
│ ERR_AGENT_TOOL_NOT │ "工具不存在: {tool_name}"                                │
│ ERR_GRPC           │ "gRPC 调用失败: {code}"                                  │
│ ERR_UNKNOWN        │ "未知错误: {error}"                                      │
└────────────────────┴─────────────────────────────────────────────────────────┘

【与 ModelGatewayClient 的差异】
工具调用通常不可降级（需要真实数据），因此：
- 不提供自动降级到其他工具
- 错误直接返回给 Agent 处理
- Agent 可选择：重试、换工具、或告知用户

【Mock 模式使用场景】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────────────────────────────────┐
│ 场景               │ 说明                                                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│ 本地开发           │ 无需启动 ToolBus Java 服务，使用预设响应                 │
│ Agent 逻辑测试     │ 验证工具调用流程，不依赖外部系统                        │
│ CI/CD 流水线       │ 避免 Java 依赖，提高测试速度                            │
│ 原型验证           │ 快速验证 Agent 工具调用设计                             │
└────────────────────┴─────────────────────────────────────────────────────────┘

启用 Mock 模式：
```python
# 方式 1：gRPC proto 文件不存在时自动启用
# 当 contracts/proto/toolbus 目录不存在时

# 方式 2：手动创建 mock stub
stub = "mock"
client = ToolBusClient()
client._stub = stub
```

Mock 工具列表：
- query_order_status: 返回订单状态（已发货）
- get_user_info: 返回用户信息（张三，金牌会员）
- mock_write_operation: 需要审批的写操作

【gRPC 连接配置说明】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────────────────┬───────────────┬─────────────────────────────┐
│ 参数                           │ 默认值        │ 说明                        │
├────────────────────────────────┼───────────────┼─────────────────────────────┤
│ max_receive_message_length     │ 16MB          │ 最大接收消息（支持大结果）  │
│ max_send_message_length        │ 16MB          │ 最大发送消息                │
│ keepalive_time_ms              │ 30s           │ keepalive 心跳间隔          │
│ keepalive_timeout_ms           │ 10s           │ keepalive 超时时间          │
│ keepalive_permit_without_calls │ True          │ 无调用时也发送心跳          │
│ http2.max_pings_without_data   │ 0             │ 无限 PING                   │
│ http2.min_time_between_pings   │ 10s           │ PING 最小间隔               │
└────────────────────────────────┴───────────────┴─────────────────────────────┘

【最佳实践】gRPC 连接调优：
- keepalive：保持连接活跃，避免连接池失效
- message_length：工具返回可能较大，设置足够上限
- 连接复用：全局单例 stub，复用连接
"""

from __future__ import annotations

import json
import time
from typing import Any

import grpc
import structlog

from app.core.config import config
from app.core.resilience import (
    CircuitBreakerOpenError,
    tool_bus_circuit,
    tool_retry_policy,
)

logger = structlog.get_logger()

# gRPC stub（延迟导入）
_stub = None
_channel = None
MOCK_MODE_ACTIVE = False  # 生产环境健康检查用：标识是否处于 mock 模式


async def get_stub():
    """获取 gRPC stub（懒加载）

    【设计说明】
    延迟初始化的好处：
    1. Proto 文件不存在时不立即报错（支持 Mock 模式）
    2. 减少启动时依赖
    3. 支持运行时动态加载

    【错误处理】
    - ImportError: Proto 文件不存在
      - 生产/staging 环境：直接 raise RuntimeError，禁止静默降级
      - 其他环境：回退到 Mock 模式，设置 MOCK_MODE_ACTIVE 标志
    - 其他错误: 记录日志并抛出
    """
    global _stub, _channel, MOCK_MODE_ACTIVE

    if _stub is None:
        try:
            from contracts.proto.toolbus import tool_bus_pb2, tool_bus_pb2_grpc

            _channel = grpc.aio.insecure_channel(
                config.tool_bus_grpc_addr,
                options=[
                    ("grpc.max_receive_message_length", 16 * 1024 * 1024),
                    ("grpc.max_send_message_length", 16 * 1024 * 1024),
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 10000),
                    ("grpc.keepalive_permit_without_calls", True),
                    ("grpc.http2.max_pings_without_data", 0),
                    ("grpc.http2.min_time_between_pings_ms", 10000),
                ],
            )
            _stub = tool_bus_pb2_grpc.ToolBusServiceStub(_channel)
            MOCK_MODE_ACTIVE = False
            logger.info("ToolBus gRPC client initialized", addr=config.tool_bus_grpc_addr)
        except ImportError:
            if config.environment in ("prod", "production", "staging"):
                logger.error(
                    "gRPC proto files missing in production environment",
                    environment=config.environment,
                )
                raise RuntimeError(
                    "ToolBus gRPC proto files not found in production. "
                    "Ensure proto files are properly generated and packaged."
                )
            logger.warning("gRPC proto files not found, using mock client")
            _stub = "mock"
            MOCK_MODE_ACTIVE = True

    return _stub


class ToolBusClient:
    """ToolBus gRPC 客户端

    【核心职责】
    Orchestrator 与 ToolBus 之间的通信桥梁：
    - 发送工具执行请求到 ToolBus
    - 接收工具执行结果（含审批状态）
    - 提供工具列表查询
    - 记录调用统计

    【特性】
    - gRPC 连接池和 keepalive：保持连接活跃
    - 熔断器保护：防止故障传播
    - 重试策略：针对 TRANSIENT_FAILURE
    - 调用统计：用于监控和性能分析
    - Mock 模式：支持本地开发

    【使用示例】
    ```python
    # 获取全局客户端
    client = get_tool_bus_client()

    # 执行工具
    result = await client.execute_tool(
        tool_name="query_order_status",
        arguments={"order_id": "12345"},
        context={
            "request_id": "req_abc",
            "tenant_id": "tenant_001",
        },
    )

    # 检查审批状态
    if result.get("approval_id"):
        # 需要审批
        approval_id = result["approval_id"]
        # 等待审批...

    # 查询工具列表
    tools = await client.list_tools(
        context={"request_id": "...", "tenant_id": "..."}
    )
    ```

    【线程安全说明】
    - 客户端实例可安全在多个协程间共享
    - gRPC stub 内部处理并发
    - 调用统计使用 dict，仅在当前实例有效
    """

    def __init__(self, addr: str | None = None):
        """初始化客户端

        Args:
            addr: ToolBus gRPC 服务地址
                  - None: 从配置读取（config.tool_bus_grpc_addr）
                  - 其他: 自定义地址
        """
        self.addr = addr or config.tool_bus_grpc_addr
        self._stub = None
        self._call_stats: dict[str, dict[str, Any]] = {}

    async def _get_stub(self):
        """获取 gRPC stub（懒加载）"""
        if self._stub is None:
            self._stub = await get_stub()
        return self._stub

    async def close(self):
        """关闭连接

        【使用场景】
        - 应用关闭时优雅释放资源
        - 测试完成后清理连接
        """
        global _channel, _stub, MOCK_MODE_ACTIVE
        if _channel:
            await _channel.close()
            _channel = None
        _stub = None
        MOCK_MODE_ACTIVE = False

    @tool_bus_circuit
    @tool_retry_policy
    async def _do_execute_tool(
        self,
        stub,
        request,
    ) -> dict:
        """执行工具调用（带熔断器和重试）

        【执行流程】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  1. 熔断器检查                                                       │
        │     │                                                               │
        │     ├─ OPEN → 快速失败                                              │
        │                                                                     │
        │  2. 重试策略                                                        │
        │     │                                                               │
        │     ├─ 尝试 1 → 失败 → 等待                                         │
        │     │                                                               │
        │     └─ 尝试 2 → 成功/失败                                           │
        │                                                                     │
        │  3. 发送 gRPC 请求                                                  │
        │                                                                     │
        │  4. 返回响应                                                        │
        └─────────────────────────────────────────────────────────────────────┘

        Args:
            stub: gRPC stub 实例
            request: Protobuf 请求对象

        Returns:
            Protobuf 响应对象
        """
        response = await stub.ExecuteTool(
            request,
            timeout=config.tool_call_timeout_s,
        )
        return response

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        context: dict,
        timeout_ms: int | None = None,
    ) -> dict:
        """执行工具调用（核心方法）

        【功能说明】
        发送工具执行请求到 ToolBus，包含：
        - 工具名称和参数
        - 请求上下文（request_id, tenant_id 等）
        - 超时配置

        【执行流程】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  1. 检查 Mock 模式                                                 │
        │     │                                                               │
        │     └─ Mock → 返回预设响应                                          │
        │                                                                     │
        │  2. 构建 Protobuf 请求                                              │
        │                                                                     │
        │  3. 发送 gRPC 调用（带熔断器和重试）                                 │
        │                                                                     │
        │  4. 解析响应                                                        │
        │     │                                                               │
        │     ├─ 成功 → 返回结果                                              │
        │     │                                                               │
        │     ├─ 需要审批 → 返回 approval_id                                  │
        │     │                                                               │
        │     └─ 失败 → 返回错误信息                                          │
        │                                                                     │
        │  5. 记录统计                                                        │
        └─────────────────────────────────────────────────────────────────────┘

        Args:
            tool_name: 工具名称，遵循 verb_noun 命名
                       如：query_order_status, get_user_info
            arguments: 工具参数，JSON 序列化后发送
                      {"order_id": "12345", "user_id": "u001"}
            context: 请求上下文，用于追踪和鉴权
                     {
                         "request_id": "req_abc",      # 必填，链路追踪
                         "tenant_id": "tenant_001",    # 必填，租户隔离
                         "user_id": "user_123",       # 用户标识
                         "session_id": "sess_xyz",    # 会话标识
                         "run_id": "run_789",         # Agent 执行标识
                         "trace_id": "trace_123",     # OpenTelemetry 追踪
                     }
            timeout_ms: 超时时间（毫秒）
                       - None: 使用配置默认值（15s）
                       - 自定义: 根据工具特性设置

        Returns:
            工具执行结果：
            {
                "call_id": "call_abc123",          # 调用标识
                "status": "success/failed/pending", # 执行状态
                "result_json": "{...}",            # 工具返回结果（JSON）
                "approval_id": "apr_xxx",          # 审批 ID（如需审批）
                "approval_status": "pending",      # 审批状态
                "approval_reason": "高风险操作",    # 审批原因
                "risk_level": "high",              # 风险等级
                "risk_reason": "写操作",            # 风险原因
                "was_cached": false,               # 是否命中缓存
                "duration_ms": 150,                # 执行耗时
                "error_code": null,                # 错误码（失败时）
                "error_message": null,            # 错误信息（失败时）
            }

        【错误处理】
        ┌────────────────────┬─────────────────────────────────────────────────────┐
        │ gRPC 状态码        │ 响应内容                                            │
        ├────────────────────┼─────────────────────────────────────────────────────┤
        │ DEADLINE_EXCEEDED  │ ERR_TIMEOUT: "工具执行超时"                         │
        │ UNAVAILABLE        │ ERR_SERVICE_UNAVAILABLE: "工具服务不可用"           │
        │ 其他               │ ERR_GRPC: "gRPC 调用失败: {code}"                   │
        └────────────────────┴─────────────────────────────────────────────────────┘

        【最佳实践】
        - 调用前校验参数，避免无效请求
        - 检查 approval_id 判断是否需要等待审批
        - 记录 call_id 用于问题排查
        - 根据工具特性设置合理超时
        """
        stub = await self._get_stub()

        if stub == "mock":
            return await self._mock_execute(tool_name, arguments, context)

        start_time = time.monotonic()

        try:
            from contracts.proto.toolbus import tool_bus_pb2

            timeout_val = timeout_ms or config.tool_call_timeout_s * 1000

            request = tool_bus_pb2.ToolExecuteRequest(
                context=tool_bus_pb2.RequestContext(
                    request_id=context.get("request_id", ""),
                    tenant_id=context.get("tenant_id", ""),
                    user_id=context.get("user_id", ""),
                    trace_id=context.get("trace_id", ""),
                    run_id=context.get("run_id", ""),
                    session_id=context.get("session_id", ""),
                ),
                tool_name=tool_name,
                tool_version="latest",
                arguments_json=json.dumps(arguments),
                timeout_ms=timeout_val,
                use_cache=True,
            )

            response = await self._do_execute_tool(stub, request)
            duration = time.monotonic() - start_time

            self._update_stats(tool_name, success=True, duration=duration)

            return {
                "call_id": response.call_id,
                "status": response.status,
                "result_json": response.result_json,
                "approval_id": response.approval_id or None,
                "approval_status": response.approval_status or None,
                "approval_reason": response.approval_reason or None,
                "risk_level": response.risk_level,
                "risk_reason": response.risk_reason or None,
                "was_cached": response.was_cached,
                "duration_ms": response.duration_ms,
                "error_code": response.error.code if response.error else None,
                "error_message": response.error.message if response.error else None,
            }

        except CircuitBreakerOpenError as e:
            logger.warning(
                "ToolBus circuit breaker open",
                tool_name=tool_name,
                circuit=e.circuit_name,
            )
            self._update_stats(tool_name, success=False)
            return {
                "call_id": "",
                "status": "failed",
                "error_code": "ERR_CIRCUIT_OPEN",
                "error_message": "服务暂时不可用，请稍后重试",
            }

        except grpc.AioRpcError as e:
            logger.error(
                "gRPC call failed",
                tool_name=tool_name,
                code=str(e.code()),
                error=str(e),
            )
            self._update_stats(tool_name, success=False)

            # 区分错误类型
            if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                return {
                    "call_id": "",
                    "status": "failed",
                    "error_code": "ERR_TIMEOUT",
                    "error_message": "工具执行超时",
                }

            if e.code() == grpc.StatusCode.UNAVAILABLE:
                return {
                    "call_id": "",
                    "status": "failed",
                    "error_code": "ERR_SERVICE_UNAVAILABLE",
                    "error_message": "工具服务不可用",
                }

            return {
                "call_id": "",
                "status": "failed",
                "error_code": "ERR_GRPC",
                "error_message": f"gRPC 调用失败: {e.code()}",
            }

        except Exception as e:
            logger.error("Unexpected error in tool execution", error=str(e))
            self._update_stats(tool_name, success=False)
            return {
                "call_id": "",
                "status": "failed",
                "error_code": "ERR_UNKNOWN",
                "error_message": str(e),
            }

    @tool_bus_circuit
    async def list_tools(
        self,
        context: dict,
        category: str | None = None,
    ) -> list[dict]:
        """查询工具列表

        【功能说明】
        获取租户可用的工具列表，用于：
        - 构建工具定义（传递给模型）
        - 前端工具选择器
        - 动态工具发现

        Args:
            context: 请求上下文（request_id, tenant_id 必填）
            category: 工具分类过滤
                     - None: 所有工具
                     - "query": 查询类工具
                     - "write": 写入类工具

        Returns:
            工具列表：
            [
                {
                    "name": "query_order_status",
                    "version": "1.0",
                    "category": "query",
                    "description": "查询订单状态",
                    "risk_level": "low",
                    "requires_approval": false
                },
                ...
            ]

        【使用场景】
        - Agent 启动时加载工具定义
        - 动态更新工具列表
        - 权限校验前检查工具是否注册
        """
        stub = await self._get_stub()

        if stub == "mock":
            return self._mock_list_tools()

        try:
            from contracts.proto.toolbus import tool_bus_pb2

            request = tool_bus_pb2.ListToolsRequest(
                context=tool_bus_pb2.RequestContext(
                    request_id=context.get("request_id", ""),
                    tenant_id=context.get("tenant_id", ""),
                    user_id=context.get("user_id", ""),
                ),
                category=category or "",
                page_size=100,
            )

            response = await stub.ListTools(
                request,
                timeout=10.0,
            )

            return [
                {
                    "name": tool.name,
                    "version": tool.version,
                    "category": tool.category,
                    "description": tool.description,
                    "risk_level": tool.risk_level,
                    "requires_approval": tool.requires_approval,
                }
                for tool in response.tools
            ]

        except Exception as e:
            logger.error("List tools failed", error=str(e))
            return []

    async def _mock_execute(self, tool_name: str, arguments: dict, context: dict) -> dict:
        """Mock 工具执行（用于开发测试）

        【设计说明】
        提供预设的工具响应，用于：
        1. 本地开发无需启动 Java 服务
        2. 单元测试隔离外部依赖
        3. 快速原型验证

        【扩展方式】
        添加新的 Mock 工具：
        ```python
        if tool_name == "new_tool":
            return {
                "call_id": call_id,
                "status": "success",
                "result_json": json.dumps({...}),
                "risk_level": "low",
                "duration_ms": 100,
            }
        ```
        """
        import uuid

        call_id = f"call_{uuid.uuid4().hex[:8]}"

        if tool_name == "query_order_status":
            return {
                "call_id": call_id,
                "status": "success",
                "result_json": json.dumps(
                    {
                        "order_id": arguments.get("order_id", "unknown"),
                        "status": "已发货",
                        "tracking_number": "SF1234567890",
                    }
                ),
                "risk_level": "low",
                "duration_ms": 150,
            }

        if tool_name == "get_user_info":
            return {
                "call_id": call_id,
                "status": "success",
                "result_json": json.dumps(
                    {
                        "user_id": arguments.get("user_id", "unknown"),
                        "name": "张三",
                        "level": "gold",
                    }
                ),
                "risk_level": "low",
                "duration_ms": 100,
            }

        return {
            "call_id": call_id,
            "status": "failed",
            "error_code": "ERR_AGENT_TOOL_NOT_FOUND",
            "error_message": f"工具不存在: {tool_name}",
        }

    def _mock_list_tools(self) -> list[dict]:
        """Mock 工具列表"""
        return [
            {
                "name": "query_order_status",
                "version": "1.0",
                "category": "query",
                "description": "查询订单状态",
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "name": "get_user_info",
                "version": "1.0",
                "category": "query",
                "description": "获取用户信息",
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "name": "mock_write_operation",
                "version": "1.0",
                "category": "write",
                "description": "模拟写操作",
                "risk_level": "high",
                "requires_approval": True,
            },
        ]

    def _update_stats(self, tool_name: str, success: bool, duration: float = 0.0):
        """更新调用统计

        【统计指标】
        - total: 总调用次数
        - success: 成功次数
        - failure: 失败次数
        - total_duration: 总耗时（成功调用）

        【使用场景】
        - 监控面板展示
        - 性能分析
        - SLA 计算
        """
        if tool_name not in self._call_stats:
            self._call_stats[tool_name] = {
                "total": 0,
                "success": 0,
                "failure": 0,
                "total_duration": 0.0,
            }

        stats = self._call_stats[tool_name]
        stats["total"] += 1
        if success:
            stats["success"] += 1
            stats["total_duration"] += duration
        else:
            stats["failure"] += 1

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """获取调用统计

        Returns:
            按工具分组的调用统计：
            {
                "query_order_status": {
                    "total": 100,
                    "success": 95,
                    "failure": 5,
                    "total_duration": 12.5
                },
                ...
            }

        【使用场景】
        - 健康检查端点
        - 监控指标导出
        - 性能分析报告
        """
        return self._call_stats.copy()


# 全局客户端实例
_client = None


def get_tool_bus_client() -> ToolBusClient:
    """获取 ToolBus 客户端实例（单例模式）

    【设计说明】
    使用全局单例的好处：
    1. gRPC 连接复用，减少资源消耗
    2. 统一的熔断器状态
    3. 统一的调用统计

    【线程安全】
    单例在首次调用时创建，之后复用。
    在异步环境中，多个协程共享同一个实例是安全的。

    Returns:
        ToolBusClient 实例
    """
    global _client
    if _client is None:
        _client = ToolBusClient()
    return _client
