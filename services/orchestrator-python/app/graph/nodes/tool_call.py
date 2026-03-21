"""工具调用节点 - 执行工具调用

核心职责：
1. 执行 thinking 节点生成的工具调用
2. 收集工具执行结果
3. 处理审批需求（高风险操作）
4. 处理执行失败

工具调用流程：
┌─────────────────────────────────────────┐
│        tool_calls (from thinking)       │
│               │                         │
│               ▼                         │
│        ┌─────────────┐                  │
│        │ 参数验证    │                   │
│        └─────────────┘                  │
│               │                         │
│               ▼                         │
│  ┌───────────────────────────┐         │
│  │  调用 ToolBus gRPC 服务    │          │
│  └───────────────────────────┘         │
│               │                         │
│    ┌──────────┼──────────┐              │
│    │          │          │              │
│ [success] [pending] [failed]            │
│    │          │          │              │
│    ▼          ▼          ▼              │
│ 结果收集   审批等待   错误记录           │
│    │          │          │              │
│    └──────────┴──► thinking             │
│              或 final_answer            │
└─────────────────────────────────────────┘

工具结果状态：
- success: 成功执行，返回 result_json
- pending_approval: 需要审批，返回 approval_id
- rejected: 风控直接拒绝
- failed: 执行失败，返回 error_message

输出字段：
- tool_results: 工具执行结果列表
- current_step: 下一步类型
- approval_id: 审批 ID（如需要）
- error: 错误信息（如有）
"""

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

    输入状态：
    - tool_calls: 待执行的工具调用列表
    - request_id: 请求追踪 ID
    - tenant_id: 租户 ID
    - user_id: 用户 ID
    - session_id: 会话 ID

    输出状态：
    - tool_results: 工具执行结果
    - risk_level: 风险等级（如有）
    - approval_id: 审批 ID（如需要）
    - current_step: 下一步类型
    - error: 错误信息（如有）

    Returns:
        更新状态字典
    """
    import time

    start_time = time.time()
    request_id = state["request_id"]
    tool_calls = state.get("tool_calls", [])

    logger.info(
        "node_started",
        node="tool_call",
        tool_count=len(tool_calls),
        tools=[t.get("tool_name") for t in tool_calls],
        request_id=request_id,
    )

    # 空检查 - 防止无工具调用
    if not tool_calls:
        logger.warning(
            "no_tool_calls",
            request_id=request_id,
        )
        return {
            "current_step": "final_answer",
            "error": "没有工具调用",
        }

    tool_results = []
    errors = []
    approval_needed = None

    # 执行所有工具调用
    for i, tool_call in enumerate(tool_calls):
        tool_name = tool_call.get("tool_name")
        arguments = tool_call.get("arguments", {})
        call_id = tool_call.get("call_id", f"call_{i}")

        logger.debug(
            "tool_executing",
            tool_index=i,
            tool_name=tool_name,
            call_id=call_id,
            arguments_preview=str(arguments)[:100],
            request_id=request_id,
        )

        tool_start = time.time()

        try:
            # 执行单个工具
            result = await _execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                state=state,
            )
            tool_duration_ms = int((time.time() - tool_start) * 1000)

            # 记录执行结果
            result["duration_ms"] = tool_duration_ms
            tool_results.append(result)

            logger.info(
                "tool_completed",
                tool_name=tool_name,
                status=result.get("status"),
                duration_ms=tool_duration_ms,
                risk_level=result.get("risk_level"),
                request_id=request_id,
            )

            # 检查是否需要审批 - 高风险操作暂停
            if result.get("status") == "pending_approval":
                approval_needed = result.get("approval_id")
                logger.warning(
                    "approval_required",
                    tool_name=tool_name,
                    approval_id=approval_needed,
                    approval_reason=result.get("approval_reason"),
                    request_id=request_id,
                )

                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "node_completed",
                    node="tool_call",
                    decision="approval_wait",
                    approval_id=approval_needed,
                    duration_ms=duration_ms,
                    request_id=request_id,
                )

                return {
                    "current_step": "approval_wait",
                    "tool_results": tool_results,
                    "approval_id": approval_needed,
                    "approval_status": "pending",
                }

            # 检查风控拒绝 - 安全策略阻止
            if result.get("status") == "rejected":
                duration_ms = int((time.time() - start_time) * 1000)
                logger.warning(
                    "tool_rejected",
                    tool_name=tool_name,
                    error_message=result.get("error_message"),
                    duration_ms=duration_ms,
                    request_id=request_id,
                )

                logger.info(
                    "node_completed",
                    node="tool_call",
                    decision="final_answer",
                    reason="tool_rejected",
                    duration_ms=duration_ms,
                    request_id=request_id,
                )

                return {
                    "current_step": "final_answer",
                    "tool_results": tool_results,
                    "error": result.get("error_message", "操作被风控拒绝"),
                    "error_code": "ERR_TOOL_RISK_REJECTED",
                }

        except Exception as e:
            # 工具执行失败 - 记录错误继续尝试其他工具
            tool_duration_ms = int((time.time() - tool_start) * 1000)
            logger.error(
                "tool_failed",
                tool_name=tool_name,
                error=str(e),
                duration_ms=tool_duration_ms,
                request_id=request_id,
            )

            errors.append({
                "tool_name": tool_name,
                "error": str(e),
            })
            tool_results.append({
                "call_id": call_id,
                "status": "failed",
                "error_message": str(e),
                "duration_ms": tool_duration_ms,
            })

    # 分析整体执行结果
    duration_ms = int((time.time() - start_time) * 1000)
    success_count = sum(1 for r in tool_results if r.get("status") == "success")
    failed_count = len(tool_results) - success_count

    # 所有工具都失败 - 无法继续
    if failed_count == len(tool_results):
        error_summary = errors[0]["error"] if errors else "未知错误"
        logger.error(
            "all_tools_failed",
            failed_count=failed_count,
            errors=[e["error"][:50] for e in errors],
            request_id=request_id,
        )

        logger.info(
            "node_completed",
            node="tool_call",
            decision="final_answer",
            reason="all_failed",
            failed_count=failed_count,
            duration_ms=duration_ms,
            request_id=request_id,
        )

        return {
            "current_step": "final_answer",
            "tool_results": tool_results,
            "error": f"所有工具调用失败: {error_summary}",
            "error_code": "ERR_TOOL_EXECUTION_FAILED",
        }

    # 有成功结果 - 继续推理循环
    logger.info(
        "node_completed",
        node="tool_call",
        decision="thinking",
        success_count=success_count,
        failed_count=failed_count,
        duration_ms=duration_ms,
        request_id=request_id,
    )

    return {
        "current_step": "thinking",
        "tool_results": tool_results,
        "messages": [{"role": "tool", "content": json.dumps(tool_results)}],
    }


async def _execute_tool(tool_name: str, arguments: dict, state: AgentState) -> dict:
    """执行单个工具调用

    优先使用 gRPC 客户端调用 ToolBus 服务，
    如果客户端未注入则使用 Mock 实现。

    Args:
        tool_name: 工具名称
        arguments: 工具参数
        state: 当前 Agent 状态

    Returns:
        工具执行结果字典：
        - call_id: 调用 ID
        - status: success/pending_approval/rejected/failed
        - result_json: 结果 JSON（成功时）
        - error_message: 错误信息（失败时）
        - approval_id: 审批 ID（需要审批时）
        - risk_level: 风险等级
    """

    if _tool_bus_client:
        # 真实 gRPC 调用
        logger.debug(
            "calling_toolbus",
            tool_name=tool_name,
            request_id=state["request_id"],
        )
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

    # Mock 实现 - 开发测试用
    logger.debug(
        "using_mock_tool",
        tool_name=tool_name,
        request_id=state["request_id"],
    )
    return await _mock_execute_tool(tool_name, arguments)


async def _mock_execute_tool(tool_name: str, arguments: dict) -> dict:
    """Mock 工具执行 - 开发测试用

    模拟常见工具的执行结果：
    - query_order_status: 查询订单状态
    - get_user_info: 查询用户信息
    - mock_write_operation: 写操作（模拟审批流程）

    Args:
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        Mock 执行结果
    """

    import uuid

    call_id = f"call_{uuid.uuid4().hex[:8]}"

    # 查询订单状态 - 低风险查询
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
        }

    # 查询用户信息 - 低风险查询
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
        }

    # 写操作 - 模拟审批流程
    # 金额超过阈值时触发审批需求
    if tool_name == "mock_write_operation":
        amount = arguments.get("amount", 0)
        threshold = 10000  # 审批阈值

        if amount > threshold:
            # 大额操作需要审批
            approval_id = f"approval_{uuid.uuid4().hex[:8]}"
            return {
                "call_id": call_id,
                "status": "pending_approval",
                "approval_id": approval_id,
                "approval_reason": f"金额 {amount} 超过阈值 {threshold}，需要审批",
                "risk_level": "high",
            }

        # 小额操作直接执行
        return {
            "call_id": call_id,
            "status": "success",
            "result_json": json.dumps({
                "operation": arguments.get("operation"),
                "status": "mock_success",
            }),
            "risk_level": "medium",
        }

    # 未知的工具 - 返回失败
    return {
        "call_id": call_id,
        "status": "failed",
        "error_code": "ERR_AGENT_TOOL_NOT_FOUND",
        "error_message": f"工具不存在: {tool_name}",
    }