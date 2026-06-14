"""测试 Approval Wait 节点 - 审批等待"""

import pytest

from app.graph.nodes.approval_wait import (
    _generate_approval_id,
    approval_wait_node,
    should_interrupt_for_approval,
)
from app.graph.state import create_initial_state


@pytest.fixture
def base_state():
    """创建基础 Mock 状态"""
    return create_initial_state(
        input="执行退款操作",
        session_id="sess_001",
        tenant_id="tenant_001",
        user_id="user_001",
        request_id="req_001",
        max_steps=10,
    )


class TestApprovalWaitNode:
    """Approval Wait 节点测试"""

    @pytest.mark.asyncio
    async def test_should_continue_tool_call_when_approved(self, base_state):
        """审批通过后继续执行"""
        base_state["approval_status"] = "approved"
        base_state["approval_id"] = "approval_abc123"

        result = await approval_wait_node(base_state)

        assert result["current_step"] == "tool_call"
        assert result["approval_status"] == "approved"

    @pytest.mark.asyncio
    async def test_should_return_final_answer_when_rejected(self, base_state):
        """审批被拒绝"""
        base_state["approval_status"] = "rejected"
        base_state["approval_id"] = "approval_abc123"

        result = await approval_wait_node(base_state)

        assert result["current_step"] == "final_answer"
        assert result["approval_status"] == "rejected"
        assert result["error"] == "操作被审批拒绝"
        assert result["error_code"] == "ERR_APPROVAL_REJECTED"

    @pytest.mark.asyncio
    async def test_should_wait_when_pending_and_has_approval_id(self, base_state):
        """审批待定且有 approval_id 时进入等待"""
        base_state["approval_status"] = "pending"
        base_state["approval_id"] = "approval_abc123"

        result = await approval_wait_node(base_state)

        assert result["current_step"] == "approval_wait"
        assert result["approval_id"] == "approval_abc123"
        assert result["approval_status"] == "pending"

    @pytest.mark.asyncio
    async def test_should_generate_approval_id_when_missing(self, base_state):
        """无 approval_id 时自动生成"""
        # approval_status 不是 approved 也不是 rejected，且无 approval_id
        base_state["approval_status"] = "pending"
        base_state["approval_id"] = None

        result = await approval_wait_node(base_state)

        assert result["current_step"] == "approval_wait"
        assert result["approval_id"] is not None
        assert result["approval_id"].startswith("approval_")

    @pytest.mark.asyncio
    async def test_should_wait_when_no_approval_status_and_no_id(self, base_state):
        """无 approval_id 且无审批状态时直接进入等待并生成 ID"""
        base_state["approval_id"] = None
        # approval_status 默认为 None

        result = await approval_wait_node(base_state)

        assert result["current_step"] == "approval_wait"
        assert result["approval_status"] == "pending"
        assert result["approval_id"] is not None


class TestShouldInterruptForApproval:
    """should_interrupt_for_approval 单元测试"""

    def test_should_interrupt_when_pending(self):
        """审批状态为 pending 时需要中断"""
        state = {"approval_status": "pending"}
        assert should_interrupt_for_approval(state) is True

    def test_should_interrupt_when_no_status(self):
        """无审批状态时需要中断"""
        state = {}
        assert should_interrupt_for_approval(state) is True

    def test_should_not_interrupt_when_approved(self):
        """审批通过时不需要中断"""
        state = {"approval_status": "approved"}
        assert should_interrupt_for_approval(state) is False

    def test_should_not_interrupt_when_rejected(self):
        """审批拒绝时不需要中断"""
        state = {"approval_status": "rejected"}
        assert should_interrupt_for_approval(state) is False


class TestGenerateApprovalId:
    """_generate_approval_id 单元测试"""

    def test_should_generate_id_with_prefix(self):
        """生成的 ID 应以 approval_ 前缀开头"""
        approval_id = _generate_approval_id()
        assert approval_id.startswith("approval_")

    def test_should_generate_unique_ids(self):
        """每次生成的 ID 应唯一"""
        id1 = _generate_approval_id()
        id2 = _generate_approval_id()
        assert id1 != id2
