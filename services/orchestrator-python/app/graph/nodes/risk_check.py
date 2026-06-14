"""风控检查节点 - 评估操作风险

核心职责：
1. 分析工具调用的风险等级
2. 判断是否需要人工审批
3. 评估敏感操作的安全性

风险评估规则：
┌─────────────────────────────────────────┐
│           工具调用输入                   │
│               │                         │
│               ▼                         │
│        ┌─────────────┐                  │
│        │ 工具类型判断 │                   │
│        └─────────────┘                  │
│               │                         │
│    ┌──────────┼──────────┐              │
│    │          │          │              │
│ [查询类]   [写操作]   [高风险]           │
│    │          │          │              │
│    ▼          ▼          ▼              │
│   low      medium    critical           │
│    │          │          │              │
│    │    ┌─────┴─────┐    │              │
│    │    │           │    │              │
│    │ [金额<阈值] [金额>阈值]              │
│    │    │           │    │              │
│    │  medium   high + 审批              │
│    │          │          │              │
│    └──────────┴──────────┘              │
│               │                         │
│               ▼                         │
│        输出风险等级                      │
└─────────────────────────────────────────┘

风险等级定义：
- low: 只读查询，无副作用
- medium: 写操作，金额较小或无敏感字段
- high: 写操作 + 大金额或敏感字段，需审批
- critical: 高风险关键词（delete/payment/transfer），必须审批

敏感字段：
- password: 密码
- credit_card: 信用卡号
- ssn: 社会安全号
- id_card: 身份证号

金额阈值：10000 元

【技术选型】风险评估阈值选择依据
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 阈值策略           │ 适用场景                    │ 优缺点                      │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 固定阈值 10000     │ • 标准化审批流程            │ 优点：简单一致              │
│ (当前选择)         │ • 普通客服场景              │ 缺点：无法适应特殊业务      │
│                    │                             │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 租户级可配置阈值   │ • 多租户 SaaS               │ 优点：灵活适配              │
│                    │ • VIP 客户特殊待遇          │ 缺点：配置复杂，需校验      │
│                    │                             │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 动态风险评估       │ • 复杂金融场景              │ 优点：最智能                │
│ (LLM 评估风险)     │ • 需考虑上下文              │ 缺点：增加调用成本          │
│                    │                             │ • 可能引入不确定性          │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择固定阈值 10000 的原因】
1. 客服场景金额分布：90% 操作 < 1000，10000 已覆盖大部分异常
2. 审批效率：阈值过低会增加审批负担，影响用户体验
3. 安全与效率平衡：10000 是行业标准阈值参考值
"""

import time

import structlog

from app.graph.state import AgentState

logger = structlog.get_logger()


async def risk_check_node(state: AgentState) -> dict:
    """风控检查节点

    在执行高风险操作前进行风险评估：
    1. 检查工具类型和参数
    2. 评估风险等级
    3. 决定是否需要审批

    输入状态：
    - tool_calls: 待执行的工具调用列表

    输出状态：
    - risk_level: 最高风险等级
    - risk_reason: 风险原因描述
    - current_step: 下一步类型 (tool_call/approval_wait)

    Returns:
        更新状态字典
    """

    start_time = time.monotonic()
    request_id = state["request_id"]
    tool_calls = state.get("tool_calls", [])

    # 检查取消标志
    from app.graph.nodes.cancel_check import check_cancel_flag

    cancel_result = await check_cancel_flag(state)
    if cancel_result:
        return cancel_result

    logger.info(
        "node_started",
        node="risk_check",
        tool_count=len(tool_calls),
        tools=[t.get("tool_name") for t in tool_calls],
        request_id=request_id,
    )

    # 空检查 - 无工具调用直接放行
    if not tool_calls:
        logger.info(
            "node_completed",
            node="risk_check",
            decision="tool_call",
            reason="no_tools",
            risk_level="low",
            duration_ms=int((time.monotonic() - start_time) * 1000),
            request_id=request_id,
        )
        return {
            "current_step": "tool_call",
            "risk_level": "low",
        }

    # 遍历所有工具调用，评估风险
    max_risk_level = "low"
    risk_reasons = []
    requires_approval = False

    for i, tool_call in enumerate(tool_calls):
        tool_name = tool_call.get("tool_name")
        arguments = tool_call.get("arguments", {})

        # 单个工具风险评估
        assessment = _assess_risk(tool_name, arguments)

        logger.debug(
            "tool_risk_assessed",
            tool_index=i,
            tool_name=tool_name,
            risk_level=assessment["risk_level"],
            requires_approval=assessment.get("requires_approval", False),
            request_id=request_id,
        )

        # 更新最高风险等级
        if _is_higher_risk(assessment["risk_level"], max_risk_level):
            max_risk_level = assessment["risk_level"]

        # 收集风险原因
        if assessment.get("reason"):
            risk_reasons.append(assessment["reason"])

        # 标记是否需要审批
        if assessment.get("requires_approval"):
            requires_approval = True

    duration_ms = int((time.monotonic() - start_time) * 1000)

    # 根据风险等级决定下一步
    if requires_approval:
        logger.warning(
            "node_completed",
            node="risk_check",
            decision="approval_wait",
            risk_level=max_risk_level,
            risk_reasons=risk_reasons,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return {
            "current_step": "approval_wait",
            "risk_level": max_risk_level,
            "risk_reason": "; ".join(risk_reasons) if risk_reasons else None,
        }

    # 风险可控，继续执行
    logger.info(
        "node_completed",
        node="risk_check",
        decision="tool_call",
        risk_level=max_risk_level,
        duration_ms=duration_ms,
        request_id=request_id,
    )
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
