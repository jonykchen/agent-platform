"""LangGraph Agent 图构建器

实现 ReAct 模式的 Agent 状态机：
- thinking -> tool_call / final_answer
- tool_call -> risk_check
- risk_check -> approval_wait / tool_execute
- approval_wait -> tool_execute (审批通过后恢复)
- final_answer -> END
"""

import structlog
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import AgentState
from app.graph.nodes import (
    thinking_node,
    tool_call_node,
    risk_check_node,
    approval_wait_node,
    final_answer_node,
)

logger = structlog.get_logger()


def build_agent_graph():
    """构建 Agent 状态图

    Returns:
        Compiled LangGraph with checkpointing and interrupt support
    """
    # 创建状态图
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("thinking", thinking_node)
    graph.add_node("risk_check", risk_check_node)
    graph.add_node("tool_call", tool_call_node)
    graph.add_node("approval_wait", approval_wait_node)
    graph.add_node("final_answer", final_answer_node)

    # 设置入口点
    graph.set_entry_point("thinking")

    # 添加条件边 - thinking 后的路由
    graph.add_conditional_edges(
        "thinking",
        route_after_thinking,
        {
            "tool_call": "tool_call",
            "risk_check": "risk_check",
            "final_answer": "final_answer",
            "max_steps_exceeded": "final_answer",
            "error": "final_answer",
        },
    )

    # 添加条件边 - risk_check 后的路由
    graph.add_conditional_edges(
        "risk_check",
        route_after_risk_check,
        {
            "approval_wait": "approval_wait",
            "tool_call": "tool_call",
            "final_answer": "final_answer",
        },
    )

    # 添加条件边 - tool_call 后的路由
    graph.add_conditional_edges(
        "tool_call",
        route_after_tool_call,
        {
            "thinking": "thinking",
            "approval_wait": "approval_wait",
            "final_answer": "final_answer",
        },
    )

    # 添加条件边 - approval_wait 后的路由
    graph.add_conditional_edges(
        "approval_wait",
        route_after_approval,
        {
            "tool_call": "tool_call",
            "final_answer": "final_answer",
        },
    )

    # 设置终点
    graph.set_finish_point("final_answer")

    # 编译图，启用 checkpoint 和 interrupt
    # interrupt_before 用于审批等待时暂停执行
    return graph.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["approval_wait"],
    )


def route_after_thinking(state: AgentState) -> str:
    """思考后的路由决策"""
    current_step = state.get("current_step", "")

    # 错误处理
    if state.get("error"):
        return "error"

    # 超过最大步骤
    if state.get("step_count", 0) >= state.get("max_steps", 10):
        return "max_steps_exceeded"

    # 根据下一步骤路由
    if current_step == "tool_call":
        # 需要工具调用，先进入风控检查
        return "risk_check"

    if current_step == "rag_retrieve":
        # 需要 RAG 检索（暂不实现）
        return "final_answer"

    if current_step == "final_answer":
        return "final_answer"

    # 默认返回最终答案
    return "final_answer"


def route_after_risk_check(state: AgentState) -> str:
    """风控检查后的路由决策"""
    current_step = state.get("current_step", "")
    risk_level = state.get("risk_level", "low")

    # 需要审批
    if current_step == "approval_wait":
        return "approval_wait"

    # 风控拒绝
    if state.get("error_code") == "ERR_TOOL_RISK_REJECTED":
        return "final_answer"

    # 继续执行工具
    return "tool_call"


def route_after_tool_call(state: AgentState) -> str:
    """工具调用后的路由决策"""
    # 需要审批等待
    if state.get("current_step") == "approval_wait":
        return "approval_wait"

    # 工具全部失败
    tool_results = state.get("tool_results", [])
    all_failed = all(r.get("status") == "failed" for r in tool_results)
    if all_failed and tool_results:
        return "final_answer"

    # 继续推理
    return "thinking"


def route_after_approval(state: AgentState) -> str:
    """审批后的路由决策"""
    approval_status = state.get("approval_status")

    if approval_status == "approved":
        return "tool_call"

    if approval_status == "rejected":
        return "final_answer"

    # 等待审批（会被 interrupt 阻断）
    return "final_answer"


# 全局图实例（懒加载）
_graph_instance = None


def get_agent_graph():
    """获取 Agent 图实例（单例）"""
    global _graph_instance
    if _graph_instance is None:
        logger.info("Building agent graph")
        _graph_instance = build_agent_graph()
    return _graph_instance


class MemorySaver:
    """内存 Checkpoint 存储器

    用于开发测试，生产环境应使用 Redis。
    """

    def __init__(self):
        self._storage = {}

    def get(self, config):
        thread_id = config["configurable"]["thread_id"]
        return self._storage.get(thread_id)

    def put(self, config, checkpoint):
        thread_id = config["configurable"]["thread_id"]
        self._storage[thread_id] = checkpoint

    def list(self, config):
        thread_id = config["configurable"].get("thread_id")
        if thread_id:
            if thread_id in self._storage:
                yield self._storage[thread_id]
        else:
            yield from self._storage.values()
