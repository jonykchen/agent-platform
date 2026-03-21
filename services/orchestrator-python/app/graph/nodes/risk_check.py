"""风控检查节点 - 评估操作风险"""

import structlog

from app.graph.state import AgentState

logger = structlog.get_logger()


async def risk_check_node(state: AgentState) -> dict:
    """风控检查节点

    在执行高风险操作前进行风险评估：
    1. 检查工具类型和参数
    2. 评估风险等级
    3. 决定是否需要审批

    Returns:
        更新状态字典，包含：
        - risk_level: 风险等级 (low/medium/high/critical)
        - risk_reason: 风险原因
        - requires_approval: 是否需要审批
    """
    logger.info(
        "risk_check_node started",
        request_id=state["request_id"],
    )

    tool_calls = state.get("tool_calls", [])
    if not tool_calls:
        return {
            "current_step": "tool_call",
            "risk_level": "low",
        }

    # 评估最高风险
    max_risk_level = "low"
    risk_reasons = []
    requires_approval = False

    for tool_call in tool_calls:
        tool_name = tool_call.get("tool_name")
        arguments = tool_call.get("arguments", {})

        assessment = _assess_risk(tool_name, arguments)

        if _is_higher_risk(assessment["risk_level"], max_risk_level):
            max_risk_level = assessment["risk_level"]

        if assessment.get("reason"):
            risk_reasons.append(assessment["reason"])

        if assessment.get("requires_approval"):
            requires_approval = True

    logger.info(
        "risk_check completed",
        risk_level=max_risk_level,
        requires_approval=requires_approval,
    )

    # 根据风险决定下一步
    if requires_approval:
        return {
            "current_step": "approval_wait",
            "risk_level": max_risk_level,
            "risk_reason": "; ".join(risk_reasons) if risk_reasons else None,
        }

    # 风险可控，继续执行工具
    return {
        "current_step": "tool_call",
        "risk_level": max_risk_level,
        "risk_reason": None,
    }


def _assess_risk(tool_name: str, arguments: dict) -> dict:
    """评估单个工具的风险"""

    # 写操作工具
    write_tools = [
        "mock_write_operation",
        "create_order",
        "update_user",
        "delete_record",
        "process_payment",
    ]

    # 高风险关键词
    high_risk_keywords = ["delete", "remove", "payment", "transfer", "withdraw"]

    # 金额阈值
    amount_threshold = 10000

    # 判断工具类型
    if any(kw in tool_name for kw in high_risk_keywords):
        return {
            "risk_level": "critical",
            "requires_approval": True,
            "reason": f"高风险工具: {tool_name}",
        }

    if tool_name in write_tools:
        # 检查金额
        amount = arguments.get("amount", 0)
        if isinstance(amount, (int, float)) and amount > amount_threshold:
            return {
                "risk_level": "high",
                "requires_approval": True,
                "reason": f"金额 {amount} 超过阈值 {amount_threshold}",
            }

        # 检查敏感字段
        sensitive_fields = ["password", "credit_card", "ssn", "id_card"]
        for field in sensitive_fields:
            if field in arguments:
                return {
                    "risk_level": "high",
                    "requires_approval": True,
                    "reason": f"涉及敏感字段: {field}",
                }

        return {
            "risk_level": "medium",
            "requires_approval": False,
            "reason": None,
        }

    # 查询类工具
    return {
        "risk_level": "low",
        "requires_approval": False,
        "reason": None,
    }


def _is_higher_risk(level1: str, level2: str) -> bool:
    """比较风险等级"""
    risk_order = ["low", "medium", "high", "critical"]
    return risk_order.index(level1) > risk_order.index(level2)