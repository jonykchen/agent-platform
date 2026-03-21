"""测试 Agent 状态定义"""

import pytest

from app.graph.state import AgentState, create_initial_state


def test_create_initial_state():
    """测试创建初始状态"""
    state = create_initial_state(
        input="你好",
        session_id="session-001",
        tenant_id="tenant-001",
        user_id="user-001",
        request_id="req-001",
    )

    assert state["input"] == "你好"
    assert state["session_id"] == "session-001"
    assert state["tenant_id"] == "tenant-001"
    assert state["user_id"] == "user-001"
    assert state["request_id"] == "req-001"
    assert state["messages"] == []
    assert state["step_count"] == 0
    assert state["max_steps"] == 10
    assert state["risk_level"] == "low"
    assert state["error"] is None


def test_create_initial_state_custom_max_steps():
    """测试自定义最大步骤数"""
    state = create_initial_state(
        input="测试",
        session_id="session-002",
        tenant_id="tenant-001",
        user_id="user-001",
        request_id="req-002",
        max_steps=5,
    )

    assert state["max_steps"] == 5


def test_state_is_typed_dict():
    """测试状态是 TypedDict"""
    # AgentState 应该可以作为字典使用
    state = create_initial_state(
        input="测试",
        session_id="session-003",
        tenant_id="tenant-001",
        user_id="user-001",
        request_id="req-003",
    )

    # 可以修改状态
    state["step_count"] = 1
    state["current_step"] = "thinking"
    state["risk_level"] = "medium"

    assert state["step_count"] == 1
    assert state["current_step"] == "thinking"
    assert state["risk_level"] == "medium"


def test_state_with_messages():
    """测试状态包含消息"""
    state = create_initial_state(
        input="你好",
        session_id="session-004",
        tenant_id="tenant-001",
        user_id="user-001",
        request_id="req-004",
    )

    # 添加消息
    state["messages"].append({"role": "user", "content": "你好"})
    state["messages"].append({"role": "assistant", "content": "你好！有什么可以帮助你的？"})

    assert len(state["messages"]) == 2
    assert state["messages"][0]["role"] == "user"
    assert state["messages"][1]["role"] == "assistant"


def test_state_with_tool_calls():
    """测试状态包含工具调用"""
    state = create_initial_state(
        input="查询订单",
        session_id="session-005",
        tenant_id="tenant-001",
        user_id="user-001",
        request_id="req-005",
    )

    # 添加工具调用
    state["tool_calls"].append({
        "id": "call-001",
        "name": "query_order_status",
        "arguments": {"order_id": "ORD123"},
    })

    state["tool_results"].append({
        "tool_call_id": "call-001",
        "content": "订单状态: 已发货",
    })

    assert len(state["tool_calls"]) == 1
    assert len(state["tool_results"]) == 1
    assert state["tool_calls"][0]["name"] == "query_order_status"


def test_state_error_handling():
    """测试状态错误处理"""
    state = create_initial_state(
        input="测试",
        session_id="session-006",
        tenant_id="tenant-001",
        user_id="user-001",
        request_id="req-006",
    )

    # 设置错误状态
    state["error"] = "工具执行失败"
    state["error_code"] = "ERR_TOOL_EXECUTION_FAILED"

    assert state["error"] == "工具执行失败"
    assert state["error_code"] == "ERR_TOOL_EXECUTION_FAILED"
