"""审批等待节点 - 等待人工审批"""

import structlog

from app.graph.state import AgentState

logger = structlog.get_logger()


async def approval_wait_node(state: AgentState) -> dict:
    """审批等待节点

    当操作需要审批时：
    1. 创建审批任务
    2. 暂停执行 (LangGraph interrupt)
    3. 等待 Kafka 回调恢复

    注意：此节点使用 LangGraph 的 interrupt_before 机制，
    实际不会执行此函数，而是在进入此节点前暂停。

    Returns:
        更新状态字典，包含：
        - approval_id: 审批任务 ID
        - approval_status: 审批状态
        - current_step: 当前步骤
    """
    logger.info(
        "approval_wait_node started",
        request_id=state["request_id"],
        approval_id=state.get("approval_id"),
    )

    # 检查审批状态
    approval_status = state.get("approval_status")

    if approval_status == "approved":
        # 审批通过，继续执行
        logger.info("Approval approved, resuming execution")
        return {
            "current_step": "tool_call",
            "approval_status": "approved",
        }

    if approval_status == "rejected":
        # 审批拒绝，终止
        logger.info("Approval rejected, terminating")
        return {
            "current_step": "final_answer",
            "approval_status": "rejected",
            "error": "操作被审批拒绝",
            "error_code": "ERR_APPROVAL_REJECTED",
        }

    # 等待审批（这会被 interrupt_before 阻断）
    approval_id = state.get("approval_id") or _generate_approval_id()

    logger.info(
        "Waiting for approval",
        approval_id=approval_id,
    )

    return {
        "current_step": "approval_wait",
        "approval_id": approval_id,
        "approval_status": "pending",
        # 此状态会被持久化到 Checkpoint，等待 Kafka 回调恢复
    }


def _generate_approval_id() -> str:
    """生成审批 ID"""
    import uuid
    return f"approval_{uuid.uuid4().hex[:8]}"


def should_interrupt_for_approval(state: AgentState) -> bool:
    """判断是否需要中断等待审批

    用于 LangGraph 的 interrupt_before 条件判断。
    """
    return state.get("approval_status") != "approved" and state.get("approval_status") != "rejected"