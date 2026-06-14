"""测试 Tool Call 节点 - 工具执行"""

from unittest.mock import AsyncMock, patch

import pytest

from app.graph.nodes.tool_call import tool_call_node
from app.graph.state import create_initial_state


@pytest.fixture
def base_state():
    """创建基础 Mock 状态"""
    return create_initial_state(
        input="查询订单状态",
        session_id="sess_001",
        tenant_id="tenant_001",
        user_id="user_001",
        request_id="req_001",
        max_steps=10,
    )


def _make_cancel_patch():
    """统一创建 cancel_check mock"""
    return patch(
        "app.graph.nodes.cancel_check.check_cancel_flag",
        return_value=None,
    )


class TestToolCallNode:
    """Tool Call 节点测试"""

    @pytest.mark.asyncio
    async def test_should_return_final_answer_when_empty_tool_calls(self, base_state):
        """空工具调用列表返回 final_answer"""
        base_state["tool_calls"] = []

        with _make_cancel_patch():
            result = await tool_call_node(base_state)

        assert result["current_step"] == "final_answer"
        assert result["error"] == "没有工具调用"

    @pytest.mark.asyncio
    async def test_should_execute_tool_successfully(self, base_state):
        """正常工具执行成功（mock 模式）"""
        base_state["tool_calls"] = [
            {
                "tool_name": "query_order_status",
                "arguments": {"order_id": "ORD-12345"},
                "call_id": "call_001",
            },
        ]

        with _make_cancel_patch(), patch("app.graph.nodes.tool_call.record_tool_call"):
            result = await tool_call_node(base_state)

        assert result["current_step"] == "thinking"
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_should_execute_mock_tool(self, base_state):
        """Mock 模式执行（_tool_bus_client 为 None 时走 mock）"""
        base_state["tool_calls"] = [
            {
                "tool_name": "get_user_info",
                "arguments": {"user_id": "user_001"},
                "call_id": "call_002",
            },
        ]

        with _make_cancel_patch(), patch("app.graph.nodes.tool_call.record_tool_call"):
            result = await tool_call_node(base_state)

        assert result["current_step"] == "thinking"
        assert result["tool_results"][0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_should_return_approval_wait_when_approval_needed(self, base_state):
        """工具需要审批时返回 approval_wait"""
        base_state["tool_calls"] = [
            {
                "tool_name": "mock_write_operation",
                "arguments": {"amount": 15000, "operation": "refund"},
                "call_id": "call_003",
            },
        ]

        with _make_cancel_patch(), patch("app.graph.nodes.tool_call.record_tool_call"):
            result = await tool_call_node(base_state)

        assert result["current_step"] == "approval_wait"
        assert result["approval_id"] is not None
        assert result["approval_status"] == "pending"
        # 审批结果应已收集在 tool_results 中
        assert len(result["tool_results"]) == 1

    @pytest.mark.asyncio
    async def test_should_return_final_answer_when_tool_rejected(self, base_state):
        """工具被风控拒绝"""
        # 模拟 _execute_tool 返回 rejected 结果
        mock_execute_result = {
            "call_id": "call_004",
            "status": "rejected",
            "error_message": "操作被风控拒绝：高风险操作",
            "risk_level": "critical",
        }

        with (
            _make_cancel_patch(),
            patch(
                "app.graph.nodes.tool_call._execute_tool",
                return_value=mock_execute_result,
            ),
            patch("app.graph.nodes.tool_call.record_tool_call"),
        ):
            base_state["tool_calls"] = [
                {
                    "tool_name": "delete_record",
                    "arguments": {"id": "rec_001"},
                    "call_id": "call_004",
                },
            ]
            result = await tool_call_node(base_state)

        assert result["current_step"] == "final_answer"
        assert result["error_code"] == "ERR_TOOL_RISK_REJECTED"
        assert "风控拒绝" in result["error"]

    @pytest.mark.asyncio
    async def test_should_return_final_answer_when_all_tools_fail(self, base_state):
        """所有工具执行失败"""
        base_state["tool_calls"] = [
            {
                "tool_name": "nonexistent_tool",
                "arguments": {},
                "call_id": "call_005",
            },
        ]

        with _make_cancel_patch(), patch("app.graph.nodes.tool_call.record_tool_call"):
            result = await tool_call_node(base_state)

        # nonexistent_tool 在 mock_registry 中返回 failed
        assert result["current_step"] == "final_answer"
        assert result["error_code"] == "ERR_TOOL_EXECUTION_FAILED"
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_should_continue_thinking_when_partial_success(self, base_state):
        """部分工具成功时继续推理"""
        # 第一个工具成功，第二个失败
        mock_results = [
            {
                "call_id": "call_006",
                "status": "success",
                "result_json": '{"order_id": "ORD-001", "status": "已发货"}',
                "risk_level": "low",
            },
            {
                "call_id": "call_007",
                "status": "failed",
                "error_message": "工具不存在: bad_tool",
            },
        ]

        call_count = 0

        async def fake_execute(tool_name, arguments, state):
            nonlocal call_count
            result = mock_results[call_count]
            call_count += 1
            return result

        base_state["tool_calls"] = [
            {"tool_name": "query_order_status", "arguments": {"order_id": "ORD-001"}, "call_id": "call_006"},
            {"tool_name": "bad_tool", "arguments": {}, "call_id": "call_007"},
        ]

        with (
            _make_cancel_patch(),
            patch(
                "app.graph.nodes.tool_call._execute_tool",
                side_effect=fake_execute,
            ),
            patch("app.graph.nodes.tool_call.record_tool_call"),
        ):
            result = await tool_call_node(base_state)

        assert result["current_step"] == "thinking"
        assert len(result["tool_results"]) == 2

    @pytest.mark.asyncio
    async def test_should_return_cancelled_when_cancel_flag_set(self, base_state):
        """取消标志设置时返回取消状态"""
        base_state["tool_calls"] = [
            {"tool_name": "query_order_status", "arguments": {"order_id": "ORD-001"}, "call_id": "call_008"},
        ]

        cancel_result = {
            "current_step": "cancelled",
            "error": "用户取消了任务",
        }

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=cancel_result,
        ):
            result = await tool_call_node(base_state)

        assert result["current_step"] == "cancelled"
        assert result["error"] == "用户取消了任务"

    @pytest.mark.asyncio
    async def test_should_include_messages_in_result(self, base_state):
        """成功执行后应包含 messages 字段"""
        base_state["tool_calls"] = [
            {
                "tool_name": "query_order_status",
                "arguments": {"order_id": "ORD-12345"},
                "call_id": "call_009",
            },
        ]

        with _make_cancel_patch(), patch("app.graph.nodes.tool_call.record_tool_call"):
            result = await tool_call_node(base_state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "tool"

    @pytest.mark.asyncio
    async def test_should_execute_tool_via_grpc_client(self, base_state):
        """通过 gRPC 客户端执行工具"""
        import app.graph.nodes.tool_call as tool_call_module

        mock_client = AsyncMock()
        mock_client.execute_tool = AsyncMock(
            return_value={
                "call_id": "call_grpc_001",
                "status": "success",
                "result_json": '{"result": "ok"}',
                "risk_level": "low",
            }
        )

        base_state["tool_calls"] = [
            {
                "tool_name": "query_order_status",
                "arguments": {"order_id": "ORD-001"},
                "call_id": "call_grpc_001",
            },
        ]

        with (
            _make_cancel_patch(),
            patch.object(tool_call_module, "_tool_bus_client", mock_client),
            patch("app.graph.nodes.tool_call.record_tool_call"),
        ):
            result = await tool_call_node(base_state)

        assert result["current_step"] == "thinking"
        assert result["tool_results"][0]["status"] == "success"
