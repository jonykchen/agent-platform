"""Mock 工具注册表

集中管理 Mock 工具的 Schema 定义和执行逻辑，
作为 tool_bus_client.py 和 graph/nodes/tool_call.py 的单一来源。

【设计说明】
┌──────────────────────────────────────────────────────────┐
│                   mock_registry.py                        │
│              （Mock Schema + 响应 单一来源）               │
│                    │           │                          │
│          ┌─────────┘           └──────────┐              │
│          ▼                                ▼              │
│  tool_bus_client.py              tool_call.py            │
│  (_mock_execute → import)        (_mock_execute_tool)    │
│  (_mock_list_tools → import)     (_get_tool_schema)      │
│                                                          │
│  thinking.py                                             │
│  (_get_available_tools → import)                         │
└──────────────────────────────────────────────────────────┘

【扩展方式】
添加新的 Mock 工具只需修改本文件：
1. 在 MOCK_TOOL_SCHEMAS 中添加 JSON Schema
2. 在 MOCK_TOOL_DEFINITIONS 中添加 OpenAI function 定义
3. 在 execute_mock_tool() 中添加执行逻辑
"""

from __future__ import annotations

import json
import uuid

# ═══════════════════════════════════════════════════════════════════════════════
# JSON Schema 定义（用于 tool_call 参数校验）
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_TOOL_SCHEMAS: dict[str, dict] = {
    "query_order_status": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "订单编号",
                "pattern": r"^ORD-[\w-]+$",
            },
        },
        "required": ["order_id"],
    },
    "get_user_info": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "用户唯一标识",
                "minLength": 1,
                "maxLength": 64,
            },
        },
        "required": ["user_id"],
    },
    "create_payment": {
        "type": "object",
        "properties": {
            "amount": {
                "type": "number",
                "description": "支付金额（元）",
                "minimum": 0.01,
                "maximum": 1000000,
            },
            "user_id": {
                "type": "string",
                "description": "用户唯一标识",
            },
        },
        "required": ["amount", "user_id"],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# OpenAI Function Calling 格式定义（用于 thinking 节点工具声明）
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_order_status",
            "description": "查询订单状态，包括物流信息和预计到达时间",
            "parameters": MOCK_TOOL_SCHEMAS["query_order_status"],
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_info",
            "description": "获取用户基本信息，包括姓名、联系方式、账户余额",
            "parameters": MOCK_TOOL_SCHEMAS["get_user_info"],
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_payment",
            "description": "创建支付订单",
            "parameters": MOCK_TOOL_SCHEMAS["create_payment"],
        },
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# Mock 工具列表（用于 ToolBus list_tools）
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_TOOL_LIST: list[dict] = [
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

# ═══════════════════════════════════════════════════════════════════════════════
# Mock 工具执行
# ═══════════════════════════════════════════════════════════════════════════════


async def execute_mock_tool(tool_name: str, arguments: dict) -> dict:
    """执行 Mock 工具

    提供预设的工具响应，用于：
    1. 本地开发无需启动 Java 服务
    2. 单元测试隔离外部依赖
    3. 快速原型验证

    Args:
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        Mock 执行结果字典
    """
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
                    "estimated_delivery": "2026-05-15",
                }
            ),
            "risk_level": "low",
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
                    "points": 12500,
                }
            ),
            "risk_level": "low",
        }

    if tool_name == "mock_write_operation":
        amount = arguments.get("amount", 0)
        threshold = 10000

        if amount > threshold:
            approval_id = f"approval_{uuid.uuid4().hex[:8]}"
            return {
                "call_id": call_id,
                "status": "pending_approval",
                "approval_id": approval_id,
                "approval_reason": f"金额 {amount} 超过阈值 {threshold}，需要审批",
                "risk_level": "high",
            }

        return {
            "call_id": call_id,
            "status": "success",
            "result_json": json.dumps(
                {
                    "operation": arguments.get("operation"),
                    "status": "mock_success",
                }
            ),
            "risk_level": "medium",
        }

    # 未知的工具 - 返回失败
    return {
        "call_id": call_id,
        "status": "failed",
        "error_code": "ERR_AGENT_TOOL_NOT_FOUND",
        "error_message": f"工具不存在: {tool_name}",
    }
