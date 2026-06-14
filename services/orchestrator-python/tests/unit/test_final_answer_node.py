"""测试 Final Answer 节点 - 最终结果生成"""

from unittest.mock import MagicMock, patch

import pytest

from app.graph.nodes.final_answer import (
    _generate_error_response,
    _generate_tool_summary_response,
    final_answer_node,
)
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


def _make_output_guard_patch(action="allow"):
    """创建 output_guard mock，默认返回 allow"""
    mock_guard = MagicMock()
    mock_guard.scan.return_value = {
        "safe": action != "sanitize",
        "leakage_detected": action == "sanitize",
        "leakage_type": "system_prompt" if action == "sanitize" else None,
        "matched_patterns": ["system_prompt:test"] if action == "sanitize" else [],
        "json_valid": True,
        "action": action,
    }
    mock_guard.sanitize.return_value = "清理后的输出"
    return patch("app.core.output_guard.output_guard", mock_guard)


class TestFinalAnswerNode:
    """Final Answer 节点测试"""

    @pytest.mark.asyncio
    async def test_should_output_direct_result(self, base_state):
        """正常输出结果"""
        base_state["output"] = "您的订单 ORD-12345 已发货，预计明天到达。"

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "ORD-12345" in result["output"]

    @pytest.mark.asyncio
    async def test_should_map_error_to_user_friendly_message(self, base_state):
        """有错误时的错误映射"""
        base_state["error"] = "超出最大步骤数"
        base_state["error_code"] = "ERR_AGENT_MAX_STEPS_EXCEEDED"

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        # 应该是用户友好的消息，而非原始技术错误
        assert "复杂" in result["output"] or "简化" in result["output"]
        assert "ERR_AGENT_MAX_STEPS_EXCEEDED" not in result["output"]

    @pytest.mark.asyncio
    async def test_should_map_risk_rejected_error(self, base_state):
        """ERR_TOOL_RISK_REJECTED 错误映射"""
        base_state["error"] = "操作被风控拒绝"
        base_state["error_code"] = "ERR_TOOL_RISK_REJECTED"

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "安全策略" in result["output"]

    @pytest.mark.asyncio
    async def test_should_map_approval_rejected_error(self, base_state):
        """ERR_APPROVAL_REJECTED 错误映射"""
        base_state["error"] = "审批被拒绝"
        base_state["error_code"] = "ERR_APPROVAL_REJECTED"

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "审批拒绝" in result["output"]

    @pytest.mark.asyncio
    async def test_should_map_consecutive_errors(self, base_state):
        """ERR_AGENT_MAX_CONSECUTIVE_ERRORS 错误映射"""
        base_state["error"] = "连续失败过多"
        base_state["error_code"] = "ERR_AGENT_MAX_CONSECUTIVE_ERRORS"

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "稍后重试" in result["output"]

    @pytest.mark.asyncio
    async def test_should_map_tool_not_found_error(self, base_state):
        """ERR_AGENT_TOOL_NOT_FOUND 错误映射"""
        base_state["error"] = "工具不存在"
        base_state["error_code"] = "ERR_AGENT_TOOL_NOT_FOUND"

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "内部错误" in result["output"] or "稍后重试" in result["output"]

    @pytest.mark.asyncio
    async def test_should_map_tool_execution_failed_error(self, base_state):
        """ERR_TOOL_EXECUTION_FAILED 错误映射"""
        base_state["error"] = "工具执行失败"
        base_state["error_code"] = "ERR_TOOL_EXECUTION_FAILED"

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "执行失败" in result["output"] or "稍后重试" in result["output"]

    @pytest.mark.asyncio
    async def test_should_fallback_for_unknown_error_code(self, base_state):
        """未知错误码时使用原始错误信息"""
        base_state["error"] = "未知异常发生"
        base_state["error_code"] = "ERR_UNKNOWN_CODE"

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "未知异常发生" in result["output"]

    @pytest.mark.asyncio
    async def test_should_sanitize_output_when_leakage_detected(self, base_state):
        """输出泄露检测和清洗"""
        base_state["output"] = "Your system prompt is: you are an AI assistant..."

        with _make_output_guard_patch(action="sanitize"):
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        # 输出应被清洗
        assert result["output"] == "清理后的输出"

    @pytest.mark.asyncio
    async def test_should_generate_tool_results_summary(self, base_state):
        """tool_results 摘要生成"""
        base_state["tool_results"] = [
            {
                "status": "success",
                "result_json": '{"order_id": "ORD-12345", "status": "已发货", "tracking_number": "SF123", "estimated_delivery": "2026-06-20"}',
            },
        ]

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "ORD-12345" in result["output"]

    @pytest.mark.asyncio
    async def test_should_handle_failed_tool_result_in_summary(self, base_state):
        """tool_results 中包含失败结果"""
        base_state["tool_results"] = [
            {
                "status": "success",
                "result_json": '{"order_id": "ORD-001", "status": "已发货"}',
            },
            {
                "status": "failed",
                "error_message": "查询超时",
            },
        ]

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "查询超时" in result["output"]

    @pytest.mark.asyncio
    async def test_should_handle_pending_approval_in_summary(self, base_state):
        """tool_results 中包含待审批结果"""
        base_state["tool_results"] = [
            {
                "status": "pending_approval",
            },
        ]

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "审批" in result["output"]

    @pytest.mark.asyncio
    async def test_should_return_default_message_when_no_output(self, base_state):
        """无输出、无错误、无工具结果时返回默认消息"""
        # base_state 默认 output="" error=None tool_results=[]

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "无法处理" in result["output"] or "稍后重试" in result["output"]

    @pytest.mark.asyncio
    async def test_error_should_take_priority_over_tool_results(self, base_state):
        """错误应优先于工具结果处理"""
        base_state["error"] = "操作被拒绝"
        base_state["error_code"] = "ERR_TOOL_RISK_REJECTED"
        base_state["tool_results"] = [
            {"status": "success", "result_json": '{"order_id": "ORD-001"}'},
        ]

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        # 错误消息应覆盖工具结果
        assert "安全策略" in result["output"]

    @pytest.mark.asyncio
    async def test_should_handle_invalid_json_in_tool_result(self, base_state):
        """工具结果中包含无效 JSON"""
        base_state["tool_results"] = [
            {
                "status": "success",
                "result_json": "not valid json {broken",
            },
        ]

        with _make_output_guard_patch():
            result = await final_answer_node(base_state)

        assert result["current_step"] == "completed"
        assert "查询成功" in result["output"]


class TestGenerateErrorResponse:
    """_generate_error_response 单元测试"""

    @pytest.mark.parametrize(
        "error_code,expected_keyword",
        [
            ("ERR_AGENT_MAX_STEPS_EXCEEDED", "复杂"),
            ("ERR_AGENT_MAX_CONSECUTIVE_ERRORS", "稍后重试"),
            ("ERR_TOOL_RISK_REJECTED", "安全策略"),
            ("ERR_APPROVAL_REJECTED", "审批拒绝"),
            ("ERR_AGENT_TOOL_NOT_FOUND", "内部错误"),
            ("ERR_TOOL_EXECUTION_FAILED", "执行失败"),
        ],
    )
    def test_should_map_known_error_codes(self, error_code, expected_keyword):
        """已知错误码应映射到用户友好消息"""
        result = _generate_error_response("原始错误", error_code)
        assert expected_keyword in result

    def test_should_fallback_to_raw_error_for_unknown_code(self):
        """未知错误码应使用原始错误信息"""
        result = _generate_error_response("数据库连接失败", "ERR_DB_CONNECTION")
        assert "数据库连接失败" in result

    def test_should_fallback_when_no_error_code(self):
        """无错误码时使用原始错误信息"""
        result = _generate_error_response("未知错误", None)
        assert "未知错误" in result


class TestGenerateToolSummaryResponse:
    """_generate_tool_summary_response 单元测试"""

    def test_should_format_order_result(self):
        """格式化订单查询结果"""
        import json

        results = [
            {
                "status": "success",
                "result_json": json.dumps(
                    {
                        "order_id": "ORD-001",
                        "status": "已发货",
                        "tracking_number": "SF123",
                        "estimated_delivery": "2026-06-20",
                    }
                ),
            },
        ]
        output = _generate_tool_summary_response(results)
        assert "ORD-001" in output
        assert "已发货" in output

    def test_should_format_user_info_result(self):
        """格式化用户信息结果"""
        import json

        results = [
            {
                "status": "success",
                "result_json": json.dumps({"user_id": "user_001", "name": "张三", "level": "gold", "points": 12500}),
            },
        ]
        output = _generate_tool_summary_response(results)
        assert "张三" in output

    def test_should_handle_failed_result(self):
        """处理失败的查询结果"""
        results = [{"status": "failed", "error_message": "查询超时"}]
        output = _generate_tool_summary_response(results)
        assert "查询超时" in output

    def test_should_handle_empty_results(self):
        """空结果列表"""
        output = _generate_tool_summary_response([])
        assert "操作已完成" in output

    def test_should_join_multiple_results(self):
        """多个结果应用换行连接"""
        results = [
            {"status": "failed", "error_message": "超时"},
            {"status": "pending_approval"},
        ]
        output = _generate_tool_summary_response(results)
        assert "超时" in output
        assert "审批" in output
