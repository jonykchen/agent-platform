"""ToolBus gRPC 客户端

通过 gRPC 调用 ToolBus 服务执行工具。
"""

import json
import structlog

import grpc

from app.core.config import config

logger = structlog.get_logger()

# gRPC stub（延迟导入）
_stub = None
_channel = None


async def get_stub():
    """获取 gRPC stub（懒加载）"""
    global _stub, _channel

    if _stub is None:
        # 动态导入生成的 gRPC 代码
        try:
            from contracts.proto.toolbus import tool_bus_pb2, tool_bus_pb2_grpc

            _channel = grpc.aio.insecure_channel(config.tool_bus_grpc_addr)
            _stub = tool_bus_pb2_grpc.ToolBusServiceStub(_channel)
            logger.info("ToolBus gRPC client initialized", addr=config.tool_bus_grpc_addr)
        except ImportError:
            logger.warning("gRPC proto files not found, using mock client")
            _stub = "mock"

    return _stub


class ToolBusClient:
    """ToolBus gRPC 客户端"""

    def __init__(self, addr: str | None = None):
        self.addr = addr or config.tool_bus_grpc_addr
        self._stub = None

    async def _get_stub(self):
        if self._stub is None:
            self._stub = await get_stub()
        return self._stub

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        context: dict,
        timeout_ms: int = 15000,
    ) -> dict:
        """执行工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            context: 请求上下文 (request_id, tenant_id, user_id, session_id)
            timeout_ms: 超时时间（毫秒）

        Returns:
            工具执行结果
        """
        stub = await self._get_stub()

        if stub == "mock":
            return await self._mock_execute(tool_name, arguments, context)

        try:
            from contracts.proto.toolbus import tool_bus_pb2

            # 构建请求
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
                timeout_ms=timeout_ms,
                use_cache=True,
            )

            # 调用 gRPC
            response = await stub.ExecuteTool(request)

            # 解析响应
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

        except grpc.AioRpcError as e:
            logger.error("gRPC call failed", error=str(e), tool_name=tool_name)
            return {
                "call_id": "",
                "status": "failed",
                "error_code": "ERR_GRPC",
                "error_message": f"gRPC 调用失败: {e.code()}",
            }

    async def list_tools(
        self,
        context: dict,
        category: str | None = None,
    ) -> list[dict]:
        """查询工具列表"""
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

            response = await stub.ListTools(request)

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
        """Mock 工具执行（用于开发测试）"""
        import uuid

        call_id = f"call_{uuid.uuid4().hex[:8]}"

        # 模拟不同工具的响应
        if tool_name == "query_order_status":
            return {
                "call_id": call_id,
                "status": "success",
                "result_json": json.dumps({
                    "order_id": arguments.get("order_id", "unknown"),
                    "status": "已发货",
                    "tracking_number": "SF1234567890",
                }),
                "risk_level": "low",
                "duration_ms": 150,
            }

        if tool_name == "get_user_info":
            return {
                "call_id": call_id,
                "status": "success",
                "result_json": json.dumps({
                    "user_id": arguments.get("user_id", "unknown"),
                    "name": "张三",
                    "level": "gold",
                }),
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


# 全局客户端实例
_client = None


def get_tool_bus_client() -> ToolBusClient:
    """获取 ToolBus 客户端实例"""
    global _client
    if _client is None:
        _client = ToolBusClient()
    return _client