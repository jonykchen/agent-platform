"""最终回答节点 - 生成并返回最终结果

核心职责：
1. 汇总执行过程中的所有结果
2. 处理错误情况，生成用户友好的消息
3. 格式化工具调用结果
4. S-AGENT-04/05: 输出泄露检测

结果生成优先级：
┌─────────────────────────────────────────┐
│            输入状态检查                  │
│               │                         │
│               ▼                         │
│        ┌─────────────┐                  │
│        │ 有错误？    │                   │
│        └─────────────┘                  │
│           │       │                     │
│          Yes      No                    │
│           │       │                     │
│           ▼       ▼                     │
│     错误消息   ┌─────────────┐          │
│               │ 有工具结果？│            │
│               └─────────────┘          │
│                  │       │              │
│                 Yes      No             │
│                  │       │              │
│                  ▼       ▼              │
│            工具结果摘要  直接输出        │
│                                     │
│               ▼                         │
│        输出泄露检测 (S-AGENT-04/05)     │
│               │                         │
│               ▼                         │
│          用户友好响应                   │
└─────────────────────────────────────────┘

错误码映射：
- ERR_AGENT_MAX_STEPS_EXCEEDED: 任务复杂超时
- ERR_TOOL_RISK_REJECTED: 安全策略阻止
- ERR_APPROVAL_REJECTED: 审批拒绝
- ERR_AGENT_TOOL_NOT_FOUND: 系统错误
- ERR_TOOL_EXECUTION_FAILED: 执行失败
- ERR_AGENT_MAX_CONSECUTIVE_ERRORS: 连续失败过多 (S-AGENT-11)

输出字段：
- output: 最终用户响应文本
- current_step: "completed" 标记完成
"""

import json
import structlog

from app.graph.state import AgentState

logger = structlog.get_logger()


async def final_answer_node(state: AgentState) -> dict:
    """最终回答节点

    汇总执行结果，生成最终响应：
    1. 处理工具结果
    2. 处理错误情况
    3. 生成用户友好的回复
    4. S-AGENT-04/05: 输出泄露检测

    输入状态：
    - error: 错误信息（如有）
    - error_code: 错误码（如有）
    - tool_results: 工具执行结果列表
    - output: 直接输出（如有）

    输出状态：
    - output: 最终用户响应（已进行泄露检测）
    - current_step: "completed" 标记完成

    Returns:
        更新状态字典
    """
    import time

    start_time = time.time()
    request_id = state["request_id"]
    step_count = state.get("step_count", 0)

    logger.info(
        "node_started",
        node="final_answer",
        step_count=step_count,
        has_error=bool(state.get("error")),
        has_tool_results=bool(state.get("tool_results")),
        request_id=request_id,
    )

    # 检查是否有错误 - 错误优先处理
    error = state.get("error")
    error_code = state.get("error_code")

    if error:
        output = _generate_error_response(error, error_code)
        # S-AGENT-04/05: 输出泄露检测
        output = _sanitize_output(output, request_id)
        duration_ms = int((time.time() - start_time) * 1000)

        logger.warning(
            "node_completed",
            node="final_answer",
            status="error",
            error_code=error_code,
            error_preview=error[:50],
            output_preview=output[:100],
            duration_ms=duration_ms,
            request_id=request_id,
        )

        return {
            "current_step": "completed",
            "output": output,
        }

    # 检查是否有工具结果 - 汇总工具调用结果
    tool_results = state.get("tool_results", [])
    if tool_results:
        output = _generate_tool_summary_response(tool_results)
        # S-AGENT-04/05: 输出泄露检测
        output = _sanitize_output(output, request_id)
        duration_ms = int((time.time() - start_time) * 1000)

        success_count = sum(1 for r in tool_results if r.get("status") == "success")
        failed_count = len(tool_results) - success_count

        logger.info(
            "node_completed",
            node="final_answer",
            status="tool_summary",
            tool_count=len(tool_results),
            success_count=success_count,
            failed_count=failed_count,
            output_preview=output[:100],
            duration_ms=duration_ms,
            request_id=request_id,
        )

        return {
            "current_step": "completed",
            "output": output,
        }

    # 检查是否有直接输出 - 使用已有输出
    direct_output = state.get("output")
    if direct_output:
        # S-AGENT-04/05: 输出泄露检测
        output = _sanitize_output(direct_output, request_id)
        duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "node_completed",
            node="final_answer",
            status="direct_output",
            output_preview=output[:100],
            duration_ms=duration_ms,
            request_id=request_id,
        )

        return {
            "current_step": "completed",
            "output": output,
        }

    # 默认响应 - 无法处理的情况
    output = "抱歉，我无法处理您的请求。请稍后重试或联系客服。"
    duration_ms = int((time.time() - start_time) * 1000)

    logger.warning(
        "node_completed",
        node="final_answer",
        status="default",
        output=output,
        duration_ms=duration_ms,
        request_id=request_id,
    )

    return {
        "current_step": "completed",
        "output": output,
    }


def _sanitize_output(output: str, request_id: str) -> str:
    """S-AGENT-04/05: 输出泄露检测与清理"""
    from app.core.output_guard import output_guard

    scan_result = output_guard.scan(output, {"request_id": request_id})

    if scan_result["action"] == "sanitize":
        sanitized = output_guard.sanitize(output, {"request_id": request_id})
        logger.warning(
            "output_sanitized",
            leakage_type=scan_result["leakage_type"],
            matched_patterns=scan_result["matched_patterns"],
            request_id=request_id,
        )
        return sanitized

    return output


def _generate_error_response(error: str, error_code: str | None) -> str:
    """生成错误响应"""

    # 用户友好的错误消息映射
    user_messages = {
        "ERR_AGENT_MAX_STEPS_EXCEEDED": "抱歉，这个任务比较复杂，处理时间较长。请尝试简化您的请求，或联系客服获取帮助。",
        "ERR_AGENT_MAX_CONSECUTIVE_ERRORS": "抱歉，系统暂时无法处理您的请求，请稍后重试。",
        "ERR_TOOL_RISK_REJECTED": "抱歉，该操作被安全策略阻止。如需执行此操作，请联系管理员申请权限。",
        "ERR_APPROVAL_REJECTED": "您的申请已被审批拒绝。如有疑问，请联系审批人了解详情。",
        "ERR_AGENT_TOOL_NOT_FOUND": "系统内部错误，无法完成您的请求。请稍后重试。",
        "ERR_TOOL_EXECUTION_FAILED": "操作执行失败，请稍后重试。如果问题持续，请联系客服。",
    }

    if error_code and error_code in user_messages:
        return user_messages[error_code]

    return f"抱歉，处理过程中出现问题：{error}"


def _generate_tool_summary_response(tool_results: list[dict]) -> str:
    """从工具结果生成响应"""

    parts = []

    for result in tool_results:
        status = result.get("status")

        if status == "success":
            result_json = result.get("result_json", "{}")
            try:
                data = json.loads(result_json)
                summary = _format_result_summary(data)
                parts.append(summary)
            except json.JSONDecodeError:
                parts.append(f"查询成功，结果: {result_json[:100]}")

        elif status == "failed":
            error_msg = result.get("error_message", "未知错误")
            parts.append(f"查询失败: {error_msg}")

        elif status == "pending_approval":
            parts.append("您的请求已提交审批，审批通过后将自动执行。")

    if not parts:
        return "操作已完成。"

    return "\n\n".join(parts)


def _format_result_summary(data: dict) -> str:
    """格式化结果摘要"""

    # 订单查询
    if "order_id" in data and "status" in data:
        return f"""📦 **订单信息**

订单号: {data.get('order_id')}
状态: {data.get('status', '未知')}
物流单号: {data.get('tracking_number', '暂无')}
预计送达: {data.get('estimated_delivery', '未知')}"""

    # 用户信息
    if "user_id" in data and "name" in data:
        return f"""👤 **用户信息**

用户: {data.get('name')}
等级: {data.get('level', '普通会员')}
积分: {data.get('points', 0)}"""

    # 通用格式化
    lines = []
    for key, value in data.items():
        if key in ["id", "created_at", "updated_at"]:
            continue
        lines.append(f"{key}: {value}")

    if lines:
        return "\n".join(lines)

    return json.dumps(data, ensure_ascii=False)