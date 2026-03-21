"""工具调用节点 - 执行工具调用"""

import json
import structlog

from app.graph.state import AgentState

logger = structlog.get_logger()

# 工具客户端（将在后续实现中注入）
_tool_bus_client = None


def set_tool_bus_client(client):
    """设置 ToolBus 客户端"""
    global _tool_bus_client
    _tool_bus_client = client


async def tool_call_node(state: AgentState) -> dict:
    """工具调用节点

    执行工具调用：
    1. 验证工具参数
    2. 调用 ToolBus
    3. 处理结果

    Returns:
        更新状态字典，包含：
        - tool_results: 工具调用结果
        - risk_level: 风险等级（如有）
        - approval_id: 审批 ID（如需要）
        - error: 错误信息（如有）
    """
    logger.info(
        "tool_call_node started",
        request_id=state["request_id"],
        tool_calls=state.get("tool_calls", []),
    )

    tool_calls = state.get("tool_calls", [])
    if not tool_calls:
        return {
            "current_step": "final_answer",
            "error": "没有工具调用",
        }

    tool_results = []
    errors = []

    for tool_call in tool_calls:
        tool_name = tool_call.get("tool_name")
        arguments = tool_call.get("arguments", {})

        logger.info(
            "Executing tool",
            tool_name=tool_name,
            arguments=arguments,
        )

        try:
            result = await _execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                state=state,
            )

            tool_results.append(result)

            # 检查是否需要审批
            if result.get("status") == "pending_approval":
                return {
                    "current_step": "approval_wait",
                    "tool_results": tool_results,
                    "approval_id": result.get("approval_id"),
                    "approval_status": "pending",
                }

            # 检查风控拒绝
            if result.get("status") == "rejected":
                return {
                    "current_step": "final_answer",
                    "tool_results": tool_results,
                    "error": result.get("error_message", "操作被风控拒绝"),
                    "error_code": "ERR_TOOL_RISK_REJECTED",
                }

        except Exception as e:
            logger.error("Tool execution failed", tool_name=tool_name, error=str(e))
            errors.append({
                "tool_name": tool_name,
                "error": str(e),
            })
            tool_results.append({
                "call_id": tool_call.get("call_id"),
                "status": "failed",
                "error_message": str(e),
            })

    # 根据结果决定下一步
    if errors and len(errors) == len(tool_calls):
        # 所有工具都失败
        return {
            "current_step": "final_answer",
            "tool_results": tool_results,
            "error": f"所有工具调用失败: {errors[0]['error']}",
            "error_code": "ERR_TOOL_EXECUTION_FAILED",
        }

    # 有成功的结果，继续推理
    return {
        "current_step": "thinking",
        "tool_results": tool_results,
        "messages": [{"role": "tool", "content": json.dumps(tool_results)}],
    }


async def _execute_tool(tool_name: str, arguments: dict, state: AgentState) -> dict:
    """执行单个工具调用"""

    if _tool_bus_client:
        # 使用真实 gRPC 客户端
        return await _tool_bus_client.execute_tool(
            tool_name=tool_name,
            arguments=arguments,
            context={
                "request_id": state["request_id"],
                "tenant_id": state["tenant_id"],
                "user_id": state["user_id"],
                "session_id": state["session_id"],
            },
        )

    # Mock 实现
    return await _mock_execute_tool(tool_name, arguments)


async def _mock_execute_tool(tool_name: str, arguments: dict) -> dict:
    """Mock 工具执行"""

    import uuid

    call_id = f"call_{uuid.uuid4().hex[:8]}"

    # 模拟查询类工具
    if tool_name == "query_order_status":
        return {
            "call_id": call_id,
            "status": "success",
            "result_json": json.dumps({
                "order_id": arguments.get("order_id", "unknown"),
                "status": "已发货",
                "tracking_number": "SF1234567890",
                "estimated_delivery": "2026-05-15",
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
                "points": 12500,
            }),
            "risk_level": "low",
            "duration_ms": 100,
        }

    # 模拟写操作（高风险）
    if tool_name == "mock_write_operation":
        amount = arguments.get("amount", 0)
        if amount > 10000:
            return {
                "call_id": call_id,
                "status": "pending_approval",
                "approval_id": f"approval_{uuid.uuid4().hex[:8]}",
                "approval_reason": f"金额 {amount} 超过阈值 10000，需要审批",
                "risk_level": "high",
            }
        return {
            "call_id": call_id,
            "status": "success",
            "result_json": json.dumps({
                "operation": arguments.get("operation"),
                "status": "mock_success",
            }),
            "risk_level": "medium",
        }

    # 未知的工具
    return {
        "call_id": call_id,
        "status": "failed",
        "error_code": "ERR_AGENT_TOOL_NOT_FOUND",
        "error_message": f"工具不存在: {tool_name}",
    }