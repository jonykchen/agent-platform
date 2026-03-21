"""审批等待节点 - 等待人工审批

核心职责：
1. 创建审批任务
2. 通过 LangGraph interrupt 暂停执行
3. 等待审批结果回调恢复执行

审批流程：
┌─────────────────────────────────────────────────────────┐
│                   高风险操作触发审批                      │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 创建审批任务    │                     │
│                  │ approval_id     │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 保存 Checkpoint │                     │
│                  │ 到 Redis        │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ interrupt 暂停  │                     │
│                  │ Agent 执行      │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           │ ◄─── 审批系统处理中         │
│                           │                             │
│            ┌──────────────┼──────────────┐             │
│            │              │              │             │
│        [approved]     [rejected]     [timeout]          │
│            │              │              │             │
│            ▼              ▼              ▼              │
│      继续执行工具    终止执行      终止执行              │
│        tool_call    final_answer  final_answer          │
│                                                         │
│  恢复方式：                                              │
│  1. POST /chat/resume API 手动恢复                      │
│  2. Kafka 回调自动恢复 (ApprovalCallbackHandler)         │
└─────────────────────────────────────────────────────────┘

LangGraph interrupt 机制：
- interrupt_before=["approval_wait"]: 进入节点前暂停
- graph.invoke(state): 从 Checkpoint 恢复执行
- 状态持久化到 Redis，支持跨进程恢复

输出字段：
- approval_id: 审批任务唯一标识
- approval_status: pending/approved/rejected
- current_step: 下一步类型
"""

import structlog

from app.graph.state import AgentState

logger = structlog.get_logger()


async def approval_wait_node(state: AgentState) -> dict:
    """审批等待节点

    当操作需要审批时：
    1. 创建审批任务
    2. 暂停执行 (LangGraph interrupt)
    3. 等待 Kafka 回调恢复

    输入状态：
    - approval_id: 审批任务 ID（可能已由 tool_call 生成）
    - approval_status: 当前审批状态

    输出状态：
    - approval_id: 审批任务 ID
    - approval_status: pending/approved/rejected
    - current_step: 下一步类型

    注意：
    此节点使用 LangGraph 的 interrupt_before 机制，
    实际不会执行此函数，而是在进入此节点前暂停。
    恢复执行时才会调用此函数。

    Returns:
        更新状态字典
    """
    import time

    start_time = time.time()
    request_id = state["request_id"]
    approval_id = state.get("approval_id")

    logger.info(
        "node_started",
        node="approval_wait",
        approval_id=approval_id,
        request_id=request_id,
    )

    # 检查审批状态
    approval_status = state.get("approval_status")

    # 审批通过 - 继续执行工具
    if approval_status == "approved":
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "node_completed",
            node="approval_wait",
            decision="tool_call",
            approval_id=approval_id,
            approval_status="approved",
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return {
            "current_step": "tool_call",
            "approval_status": "approved",
        }

    # 审批拒绝 - 终止执行
    if approval_status == "rejected":
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning(
            "node_completed",
            node="approval_wait",
            decision="final_answer",
            approval_id=approval_id,
            approval_status="rejected",
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return {
            "current_step": "final_answer",
            "approval_status": "rejected",
            "error": "操作被审批拒绝",
            "error_code": "ERR_APPROVAL_REJECTED",
        }

    # 等待审批 - interrupt 状态
    # 正常情况下不会执行到这里，因为 interrupt_before 会先暂停
    if not approval_id:
        approval_id = _generate_approval_id()

    duration_ms = int((time.time() - start_time) * 1000)

    logger.warning(
        "node_completed",
        node="approval_wait",
        decision="waiting",
        approval_id=approval_id,
        approval_status="pending",
        duration_ms=duration_ms,
        request_id=request_id,
        note="Waiting for approval, state persisted to checkpoint",
    )

    return {
        "current_step": "approval_wait",
        "approval_id": approval_id,
        "approval_status": "pending",
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