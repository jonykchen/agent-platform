"""测试 Risk Check 节点 - 风控风险评估"""

from unittest.mock import patch

import pytest

from app.graph.nodes.risk_check import _assess_risk, _is_higher_risk, risk_check_node
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


class TestRiskCheckNode:
    """Risk Check 节点测试"""

    @pytest.mark.asyncio
    async def test_should_pass_through_when_no_tool_calls(self, base_state):
        """无工具调用时直接放行"""
        base_state["tool_calls"] = []

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["current_step"] == "tool_call"
        assert result["risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_should_return_low_risk_for_query_tools(self, base_state):
        """查询类工具返回 low risk"""
        base_state["tool_calls"] = [
            {"tool_name": "query_order_status", "arguments": {"order_id": "ORD-001"}},
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["current_step"] == "tool_call"
        assert result["risk_level"] == "low"
        assert result["risk_reason"] is None

    @pytest.mark.asyncio
    async def test_should_return_medium_risk_for_write_tools(self, base_state):
        """写操作工具返回 medium risk"""
        base_state["tool_calls"] = [
            {
                "tool_name": "mock_write_operation",
                "arguments": {"operation": "update"},
            },
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["current_step"] == "tool_call"
        assert result["risk_level"] == "medium"
        assert result["risk_reason"] is None

    @pytest.mark.asyncio
    async def test_should_return_critical_for_high_risk_keywords(self, base_state):
        """高风险关键词（delete/payment/transfer）返回 critical + 需要审批"""
        # delete
        base_state["tool_calls"] = [
            {"tool_name": "delete_record", "arguments": {"id": "rec_001"}},
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["current_step"] == "approval_wait"
        assert result["risk_level"] == "critical"

    @pytest.mark.asyncio
    async def test_should_return_critical_for_payment_keyword(self, base_state):
        """payment 关键词返回 critical"""
        base_state["tool_calls"] = [
            {"tool_name": "process_payment", "arguments": {"amount": 100}},
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["current_step"] == "approval_wait"
        assert result["risk_level"] == "critical"

    @pytest.mark.asyncio
    async def test_should_return_critical_for_transfer_keyword(self, base_state):
        """transfer 关键词返回 critical"""
        base_state["tool_calls"] = [
            {"tool_name": "bank_transfer", "arguments": {"to": "acct_001"}},
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["current_step"] == "approval_wait"
        assert result["risk_level"] == "critical"

    @pytest.mark.asyncio
    async def test_should_return_high_when_amount_exceeds_threshold(self, base_state):
        """金额超过阈值（10000）返回 high + 需要审批"""
        base_state["tool_calls"] = [
            {
                "tool_name": "mock_write_operation",
                "arguments": {"amount": 15000, "operation": "refund"},
            },
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["current_step"] == "approval_wait"
        assert result["risk_level"] == "high"
        assert "15000" in result["risk_reason"]

    @pytest.mark.asyncio
    async def test_should_return_high_for_sensitive_fields(self, base_state):
        """敏感字段（password/credit_card 等）返回 high + 需要审批"""
        base_state["tool_calls"] = [
            {
                "tool_name": "mock_write_operation",
                "arguments": {"password": "secret123"},
            },
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["current_step"] == "approval_wait"
        assert result["risk_level"] == "high"
        assert "password" in result["risk_reason"]

    @pytest.mark.asyncio
    async def test_should_return_high_for_credit_card_field(self, base_state):
        """credit_card 敏感字段返回 high"""
        base_state["tool_calls"] = [
            {
                "tool_name": "mock_write_operation",
                "arguments": {"credit_card": "4111111111111111"},
            },
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["risk_level"] == "high"
        assert "credit_card" in result["risk_reason"]

    @pytest.mark.asyncio
    async def test_should_return_high_for_ssn_field(self, base_state):
        """ssn 敏感字段返回 high"""
        base_state["tool_calls"] = [
            {
                "tool_name": "mock_write_operation",
                "arguments": {"ssn": "123-45-6789"},
            },
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["risk_level"] == "high"
        assert "ssn" in result["risk_reason"]

    @pytest.mark.asyncio
    async def test_should_return_high_for_id_card_field(self, base_state):
        """id_card 敏感字段返回 high"""
        base_state["tool_calls"] = [
            {
                "tool_name": "mock_write_operation",
                "arguments": {"id_card": "110101199001011234"},
            },
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        assert result["risk_level"] == "high"
        assert "id_card" in result["risk_reason"]

    @pytest.mark.asyncio
    async def test_should_pick_highest_risk_from_multiple_tools(self, base_state):
        """多个工具调用时取最高风险等级"""
        base_state["tool_calls"] = [
            {"tool_name": "query_order_status", "arguments": {"order_id": "ORD-001"}},
            {
                "tool_name": "mock_write_operation",
                "arguments": {"operation": "update"},
            },
            {"tool_name": "delete_record", "arguments": {"id": "rec_001"}},
        ]

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=None,
        ):
            result = await risk_check_node(base_state)

        # critical from delete_record 是最高风险
        assert result["risk_level"] == "critical"
        assert result["current_step"] == "approval_wait"

    @pytest.mark.asyncio
    async def test_should_return_cancelled_when_cancel_flag_set(self, base_state):
        """取消标志设置时返回取消状态"""
        base_state["tool_calls"] = [
            {"tool_name": "query_order_status", "arguments": {"order_id": "ORD-001"}},
        ]

        cancel_result = {
            "current_step": "cancelled",
            "error": "用户取消了任务",
        }

        with patch(
            "app.graph.nodes.cancel_check.check_cancel_flag",
            return_value=cancel_result,
        ):
            result = await risk_check_node(base_state)

        assert result["current_step"] == "cancelled"
        assert result["error"] == "用户取消了任务"


class TestAssessRisk:
    """_assess_risk 单元测试"""

    @pytest.mark.parametrize(
        "tool_name,expected_level,expected_approval",
        [
            ("query_order_status", "low", False),
            ("get_user_info", "low", False),
            ("mock_write_operation", "medium", False),
            ("create_order", "medium", False),
            ("update_user", "medium", False),
            ("delete_record", "critical", True),
            ("process_payment", "critical", True),
        ],
    )
    def test_should_classify_tool_risk_correctly(self, tool_name, expected_level, expected_approval):
        """验证各工具类型的风险分类"""
        result = _assess_risk(tool_name, {})
        assert result["risk_level"] == expected_level
        assert result["requires_approval"] == expected_approval

    @pytest.mark.parametrize(
        "keyword",
        ["delete", "remove", "payment", "transfer", "withdraw"],
    )
    def test_should_detect_high_risk_keywords(self, keyword):
        """高风险关键词检测"""
        tool_name = f"tool_{keyword}_data"
        result = _assess_risk(tool_name, {})
        assert result["risk_level"] == "critical"
        assert result["requires_approval"] is True

    def test_should_detect_amount_exceeding_threshold(self):
        """金额超过阈值检测"""
        result = _assess_risk("mock_write_operation", {"amount": 20000})
        assert result["risk_level"] == "high"
        assert result["requires_approval"] is True
        assert "20000" in result["reason"]

    def test_should_pass_amount_below_threshold(self):
        """金额未超过阈值不触发审批"""
        result = _assess_risk("mock_write_operation", {"amount": 5000})
        assert result["risk_level"] == "medium"
        assert result["requires_approval"] is False

    @pytest.mark.parametrize(
        "field",
        ["password", "credit_card", "ssn", "id_card"],
    )
    def test_should_detect_sensitive_fields(self, field):
        """敏感字段检测"""
        result = _assess_risk("mock_write_operation", {field: "some_value"})
        assert result["risk_level"] == "high"
        assert result["requires_approval"] is True
        assert field in result["reason"]

    def test_amount_string_type_should_not_trigger_high_risk(self):
        """金额为字符串类型时不应触发高金额风险"""
        result = _assess_risk("mock_write_operation", {"amount": "99999"})
        assert result["risk_level"] == "medium"
        assert result["requires_approval"] is False


class TestIsHigherRisk:
    """_is_higher_risk 单元测试"""

    @pytest.mark.parametrize(
        "level1,level2,expected",
        [
            ("low", "low", False),
            ("medium", "low", True),
            ("high", "medium", True),
            ("critical", "high", True),
            ("critical", "low", True),
            ("low", "critical", False),
            ("medium", "high", False),
        ],
    )
    def test_should_compare_risk_levels_correctly(self, level1, level2, expected):
        """验证风险等级比较逻辑"""
        assert _is_higher_risk(level1, level2) is expected
