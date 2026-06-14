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

【技术选型】工具参数校验策略
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 校验位置           │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Orchestrator 校验  │ • 最早拦截，减少无效调用    │ • 需维护 Schema 同步        │
│ (当前选择)         │ • 防止恶意参数穿透          │ • Schema 变更需双端更新     │
│                    │ • S-AGENT-06 合规           │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ ToolBus 校验       │ • Schema 集中管理           │ • 恶意参数已穿透到服务层    │
│                    │ • 工具定义一致               │ • 网络开销已发生            │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 双端校验           │ • 最安全                    │ • 重复校验，性能开销        │
│                    │                             │ • 维护成本高                │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择 Orchestrator 校验的原因】
1. S-AGENT-06 要求工具调用必须经过鉴权链，校验是鉴权的第一步
2. 减少无效 gRPC 调用，降低网络开销
3. 早期拦截恶意输入，防止攻击穿透到 ToolBus
"""

import json
import time

import structlog

from app.core.metrics import record_tool_call
from app.core.resilience import (
    CircuitBreakerOpenError,
    tool_bus_circuit,
    tool_retry_policy,
    with_retry_and_circuit,
)
from app.graph.state import AgentState

logger = structlog.get_logger()

# ToolBus gRPC 调用的容错包装：复用全局熔断器 + 重试策略（与 ModelGateway 同模式）。
# 先重试瞬态故障（网络抖动），连续失败累计触发熔断后快速失败，避免 ToolBus 宕机时
# 每次工具调用都白白等待 gRPC 超时拖垮 Agent。装饰器顺序：熔断（外）→ 重试（内）。
_resilient_toolbus_call = with_retry_and_circuit(tool_bus_circuit, tool_retry_policy)

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

    start_time = time.monotonic()
    request_id = state["request_id"]
    tenant_id = state.get("tenant_id", "unknown")
    tool_calls = state.get("tool_calls", [])

    # 检查取消标志
    from app.graph.nodes.cancel_check import check_cancel_flag

    cancel_result = await check_cancel_flag(state)
    if cancel_result:
        return cancel_result

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

        tool_start = time.monotonic()

        try:
            # 执行单个工具
            result = await _execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                state=state,
            )
            tool_duration_ms = int((time.monotonic() - tool_start) * 1000)

            # 记录执行结果
            result["duration_ms"] = tool_duration_ms
            tool_results.append(result)

            # 记录工具调用指标：供 tool_call_total / tool_call_latency_seconds 告警与看板使用
            record_tool_call(
                tool_name=tool_name or "unknown",
                tenant_id=tenant_id,
                status=str(result.get("status", "unknown")),
                latency=tool_duration_ms / 1000.0,
            )

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

                duration_ms = int((time.monotonic() - start_time) * 1000)
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
                duration_ms = int((time.monotonic() - start_time) * 1000)
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
            tool_duration_ms = int((time.monotonic() - tool_start) * 1000)
            record_tool_call(
                tool_name=tool_name or "unknown",
                tenant_id=tenant_id,
                status="failed",
                latency=tool_duration_ms / 1000.0,
            )
            logger.error(
                "tool_failed",
                tool_name=tool_name,
                error=str(e),
                duration_ms=tool_duration_ms,
                request_id=request_id,
            )

            errors.append(
                {
                    "tool_name": tool_name,
                    "error": str(e),
                }
            )
            tool_results.append(
                {
                    "call_id": call_id,
                    "status": "failed",
                    "error_message": str(e),
                    "duration_ms": tool_duration_ms,
                }
            )

    # 分析整体执行结果
    duration_ms = int((time.monotonic() - start_time) * 1000)
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

    【S-AGENT-06】集成参数校验，防止恶意输入

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

    # 【S-AGENT-06】参数校验
    validation_result = _validate_tool_arguments(tool_name, arguments)
    if not validation_result["valid"]:
        logger.warning(
            "tool_arguments_validation_failed",
            tool_name=tool_name,
            errors=validation_result["errors"],
            request_id=state["request_id"],
        )
        return {
            "call_id": "",
            "status": "failed",
            "error_code": "ERR_TOOL_VALIDATION_FAILED",
            "error_message": f"参数校验失败: {', '.join(validation_result['errors'])}",
        }

    if _tool_bus_client:
        # 真实 gRPC 调用（经熔断器 + 重试包裹）
        logger.debug(
            "calling_toolbus",
            tool_name=tool_name,
            request_id=state["request_id"],
        )

        @_resilient_toolbus_call
        async def _call_toolbus() -> dict:
            return await _tool_bus_client.execute_tool(
                tool_name=tool_name,
                arguments=validation_result["data"],  # 使用校验后的数据（可能填充了 defaults）
                context={
                    "request_id": state["request_id"],
                    "tenant_id": state["tenant_id"],
                    "user_id": state["user_id"],
                    "session_id": state["session_id"],
                },
            )

        try:
            return await _call_toolbus()
        except CircuitBreakerOpenError as e:
            # 熔断器打开：ToolBus 持续不可用，快速失败而非继续等待 gRPC 超时。
            # 返回 failed 结果交由上层 tool_call_node 统一处理（不抛异常打断其他工具）。
            logger.warning(
                "toolbus_circuit_open",
                tool_name=tool_name,
                circuit=e.circuit_name,
                request_id=state["request_id"],
                hint="ToolBus 连续失败已熔断，快速失败本次调用",
            )
            return {
                "call_id": "",
                "status": "failed",
                "error_code": "ERR_TOOL_EXECUTION_FAILED",
                "error_message": f"工具服务暂不可用（熔断器已打开）: {tool_name}",
            }

    # Mock 实现 - 开发测试用
    logger.debug(
        "using_mock_tool",
        tool_name=tool_name,
        request_id=state["request_id"],
    )
    return await _mock_execute_tool(tool_name, arguments)


def _get_tool_schema(tool_name: str) -> dict | None:
    """获取工具的参数 Schema

    从共享 mock_registry 获取 JSON Schema。

    Args:
        tool_name: 工具名称

    Returns:
        JSON Schema 字典，未找到返回 None
    """
    from app.tools.mock_registry import MOCK_TOOL_SCHEMAS

    return MOCK_TOOL_SCHEMAS.get(tool_name)


async def _mock_execute_tool(tool_name: str, arguments: dict) -> dict:
    """Mock 工具执行 - 委托给共享 mock_registry

    Args:
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        Mock 执行结果
    """
    from app.tools.mock_registry import execute_mock_tool

    return await execute_mock_tool(tool_name, arguments)


def _validate_tool_arguments(tool_name: str, arguments: dict) -> dict:
    """校验工具参数

    【S-AGENT-06】工具调用鉴权链的一部分

    Args:
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        {"valid": bool, "errors": list, "data": dict}
    """
    from app.tools.validators.json_schema_validator import validate_tool_arguments

    # 获取工具的 JSON Schema
    tool_schema = _get_tool_schema(tool_name)
    if not tool_schema:
        # 未找到 Schema，允许通过（开发阶段）
        logger.debug("tool_schema_not_found", tool_name=tool_name)
        return {"valid": True, "errors": [], "data": arguments}

    result = validate_tool_arguments(tool_name, arguments, tool_schema)
    return result.to_dict()
