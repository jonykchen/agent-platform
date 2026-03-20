"""LangGraph 状态机定义"""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Agent 状态

    使用 LangGraph 的状态管理，支持消息累积。
    """

    # 对话历史（自动累积）
    messages: Annotated[list, add_messages]

    # 当前输入
    input: str

    # 会话信息
    session_id: str
    tenant_id: str
    user_id: str
    request_id: str

    # 执行状态
    step_count: int
    max_steps: int

    # 当前步骤类型
    current_step: str

    # 工具调用信息
    tool_calls: list[dict]
    tool_results: list[dict]

    # RAG 检索结果
    retrieved_docs: list[dict]

    # 风险检查结果
    risk_level: str
    risk_reason: str | None

    # 审批信息
    approval_id: str | None
    approval_status: str | None

    # 最终输出
    output: str

    # 错误信息
    error: str | None
    error_code: str | None

    # 元数据
    metadata: dict


def create_initial_state(
    input: str,
    session_id: str,
    tenant_id: str,
    user_id: str,
    request_id: str,
    max_steps: int = 10,
) -> AgentState:
    """创建初始状态"""
    return AgentState(
        messages=[],
        input=input,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        request_id=request_id,
        step_count=0,
        max_steps=max_steps,
        current_step="",
        tool_calls=[],
        tool_results=[],
        retrieved_docs=[],
        risk_level="low",
        risk_reason=None,
        approval_id=None,
        approval_status=None,
        output="",
        error=None,
        error_code=None,
        metadata={},
    )