"""LangGraph Agent 图构建器

实现 ReAct 模式的 Agent 状态机：

┌─────────────────────────────────────────────────────────────────────────────┐
│                           Agent 执行流程图                                   │
│                                                                             │
│   START                                                                     │
│     │                                                                       │
│     ▼                                                                       │
│  ┌──────────┐                                                               │
│  │ thinking │ ─────────────────────────────────────────┐                     │
│  └──────────┘                                          │                     │
│     │                                                  │                     │
│     ├──[error]─────────────────────────────────────────┼──► final_answer     │
│     ├──[max_steps_exceeded]────────────────────────────┼──► final_answer     │
│     ├──[final_answer]──────────────────────────────────┴──► final_answer     │
│     └──[tool_call]──► ┌────────────┐                                        │
│                        │ risk_check │                                        │
│                        └────────────┘                                        │
│                             │                                               │
│     ┌───────────────────────┼───────────────────────┐                       │
│     │                       │                       │                        │
│  [rejected]              [approved]           [approval_wait]                │
│     │                       │                       │                        │
│     ▼                       ▼                       ▼                        │
│  final_answer          ┌──────────┐         ┌──────────────┐                │
│                        │tool_call │         │approval_wait │◄── interrupt    │
│                        └──────────┘         └──────────────┘   (暂停执行)    │
│                             │                       │                        │
│                             │         ┌─────────────┴─────────────┐          │
│                             │         │  Kafka 回调恢复执行        │          │
│                             │         │  approved → tool_call      │          │
│                             │         │  rejected → final_answer   │          │
│                             ▼         └───────────────────────────┘          │
│                        ┌──────────┐                                          │
│                        │ thinking │ ◄── 循环继续推理                         │
│                        └──────────┘                                          │
│                             │                                               │
│                             ▼                                               │
│                        final_answer ─────► END                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

关键概念：
- ReAct 模式：Reasoning（推理）+ Acting（行动）循环
- interrupt_before：在 approval_wait 节点前暂停，等待人工审批
- Checkpoint：状态持久化，用于恢复中断的执行

节点职责：
- thinking：模型推理，分析用户意图，决定下一步行动
- tool_call：执行工具调用，获取外部数据或执行操作
- risk_check：评估操作风险，决定是否需要审批
- approval_wait：等待人工审批（使用 interrupt 机制暂停）
- final_answer：汇总结果，生成用户友好的响应
"""

import asyncio

import structlog
from langgraph.graph import StateGraph, END

from app.core.config import config
from app.core.constants import (
    MAX_CONCURRENT_MODEL_CALLS,
    MAX_CONCURRENT_TOOL_CALLS,
)
from app.graph.state import AgentState
from app.graph.nodes import (
    thinking_node,
    tool_call_node,
    risk_check_node,
    approval_wait_node,
    final_answer_node,
)

logger = structlog.get_logger()

# 【P2-配置统一化】全局并发限制信号量（动态初始化）
_model_semaphore: asyncio.Semaphore | None = None
_tool_semaphore: asyncio.Semaphore | None = None


def _get_model_semaphore() -> asyncio.Semaphore:
    """获取模型调用信号量（从配置读取）"""
    global _model_semaphore
    if _model_semaphore is None:
        limit = getattr(config, "max_concurrent_model_calls", MAX_CONCURRENT_MODEL_CALLS)
        _model_semaphore = asyncio.Semaphore(limit)
        logger.info("model_semaphore_initialized", limit=limit)
    return _model_semaphore


def _get_tool_semaphore() -> asyncio.Semaphore:
    """获取工具调用信号量（从配置读取）"""
    global _tool_semaphore
    if _tool_semaphore is None:
        limit = getattr(config, "max_concurrent_tool_calls", MAX_CONCURRENT_TOOL_CALLS)
        _tool_semaphore = asyncio.Semaphore(limit)
        logger.info("tool_semaphore_initialized", limit=limit)
    return _tool_semaphore


async def _thinking_with_limit(state: AgentState) -> dict:
    """带并发限制的思考节点"""
    async with _get_model_semaphore():
        return await thinking_node(state)


async def _tool_call_with_limit(state: AgentState) -> dict:
    """带并发限制的工具调用节点"""
    async with _get_tool_semaphore():
        return await tool_call_node(state)


def build_agent_graph():
    """构建 Agent 状态图

    创建 LangGraph 状态机，包含：
    - 5 个节点：thinking, risk_check, tool_call, approval_wait, final_answer
    - 4 个条件路由：route_after_thinking, route_after_risk_check, route_after_tool_call, route_after_approval
    - interrupt_before=["approval_wait"] 审批暂停机制
    - MemorySaver checkpoint 持久化

    Returns:
        Compiled LangGraph with checkpointing and interrupt support
    """
    logger.info("Building agent graph")

    # 创建状态图
    graph = StateGraph(AgentState)

    # 添加节点 - 每个节点负责特定的处理逻辑
    # thinking: 模型推理，决定下一步行动（带并发限制）
    # risk_check: 风险评估，判断是否需要审批
    # tool_call: 执行工具调用（带并发限制）
    # approval_wait: 等待人工审批（interrupt 点）
    # final_answer: 汇总结果，生成最终响应
    graph.add_node("thinking", _thinking_with_limit)
    graph.add_node("risk_check", risk_check_node)
    graph.add_node("tool_call", _tool_call_with_limit)
    graph.add_node("approval_wait", approval_wait_node)
    graph.add_node("final_answer", final_answer_node)

    # 设置入口点 - 所有请求从 thinking 开始
    graph.set_entry_point("thinking")

    # 条件边 - thinking 后的路由
    # 根据推理结果决定：工具调用（需风控）或直接回答
    graph.add_conditional_edges(
        "thinking",
        route_after_thinking,
        {
            "tool_call": "risk_check",  # 注意：tool_call 先进入 risk_check
            "risk_check": "risk_check",
            "final_answer": "final_answer",
            "max_steps_exceeded": "final_answer",
            "max_consecutive_errors": "final_answer",  # S-AGENT-11 连续失败终止
            "error": "final_answer",
        },
    )

    # 条件边 - risk_check 后的路由
    # 根据风险等级决定：继续执行、等待审批、或拒绝
    graph.add_conditional_edges(
        "risk_check",
        route_after_risk_check,
        {
            "approval_wait": "approval_wait",
            "tool_call": "tool_call",
            "final_answer": "final_answer",
        },
    )

    # 条件边 - tool_call 后的路由
    # 根据工具结果决定：继续推理、等待审批、或结束
    graph.add_conditional_edges(
        "tool_call",
        route_after_tool_call,
        {
            "thinking": "thinking",
            "approval_wait": "approval_wait",
            "final_answer": "final_answer",
        },
    )

    # 条件边 - approval_wait 后的路由
    # 根据审批结果决定：继续执行或拒绝
    graph.add_conditional_edges(
        "approval_wait",
        route_after_approval,
        {
            "tool_call": "tool_call",
            "final_answer": "final_answer",
        },
    )

    # 设置终点 - final_answer 是唯一的结束节点
    graph.set_finish_point("final_answer")

    # 编译图
    # - checkpointer: 状态持久化，用于恢复中断的执行
    # - interrupt_before: 在 approval_wait 节点前暂停，等待审批
    # 生产环境使用 Redis，开发环境使用 MemorySaver
    from app.core.config import config

    if hasattr(config, "environment") and config.environment == "production":
        from app.graph.checkpointer import RedisSaver
        checkpointer = RedisSaver(
            redis_url=config.redis_url if hasattr(config, "redis_url") else "redis://localhost:6379",
        )
        logger.info("Using Redis checkpointer for production")
    else:
        checkpointer = MemorySaver()
        logger.info("Using MemorySaver for development")

    compiled_graph = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["approval_wait"],
    )

    logger.info(
        "Agent graph built",
        nodes=["thinking", "risk_check", "tool_call", "approval_wait", "final_answer"],
        entry_point="thinking",
        finish_point="final_answer",
        interrupt_before=["approval_wait"],
    )

    return compiled_graph


def route_after_thinking(state: AgentState) -> str:
    """思考后的路由决策

    决策优先级：
    1. 错误处理 - 有错误直接结束
    2. 步骤限制 - 超过最大步骤直接结束
    3. 连续失败限制 - 连续失败 ≥ 3 次终止（S-AGENT-11）
    4. 工具调用 - 需要工具时进入风控检查
    5. RAG 检索 - 需要知识检索（暂未实现）
    6. 直接回答 - 默认路径

    Returns:
        目标节点名称: error | max_steps_exceeded | max_consecutive_errors | risk_check | final_answer
    """
    current_step = state.get("current_step", "")
    step_count = state.get("step_count", 0)
    max_steps = state.get("max_steps", 10)
    consecutive_errors = state.get("consecutive_errors", 0)
    max_consecutive_errors = state.get("max_consecutive_errors", 3)

    # 错误处理 - 优先级最高
    if state.get("error"):
        logger.warning(
            "route_decision",
            from_node="thinking",
            to_node="final_answer",
            reason="error",
            error=state["error"][:100],
            request_id=state.get("request_id"),
        )
        return "error"

    # 超过最大步骤 - 防止无限循环
    if step_count >= max_steps:
        logger.warning(
            "route_decision",
            from_node="thinking",
            to_node="final_answer",
            reason="max_steps_exceeded",
            step_count=step_count,
            max_steps=max_steps,
            request_id=state.get("request_id"),
        )
        return "max_steps_exceeded"

    # 连续失败限制 - S-AGENT-11
    if consecutive_errors >= max_consecutive_errors:
        logger.error(
            "route_decision",
            from_node="thinking",
            to_node="final_answer",
            reason="max_consecutive_errors",
            consecutive_errors=consecutive_errors,
            max_consecutive_errors=max_consecutive_errors,
            request_id=state.get("request_id"),
        )
        return "max_consecutive_errors"

    # 工具调用 - 进入风控检查（安全检查在工具执行前）
    if current_step == "tool_call":
        tool_calls = state.get("tool_calls", [])
        tool_names = [t.get("tool_name") for t in tool_calls]
        logger.info(
            "route_decision",
            from_node="thinking",
            to_node="risk_check",
            reason="tool_call_required",
            tools=tool_names,
            step_count=step_count,
            request_id=state.get("request_id"),
        )
        return "risk_check"

    # RAG 检索（暂不实现，直接返回）
    if current_step == "rag_retrieve":
        logger.info(
            "route_decision",
            from_node="thinking",
            to_node="final_answer",
            reason="rag_not_implemented",
            request_id=state.get("request_id"),
        )
        return "final_answer"

    # 直接回答 - 默认路径
    logger.info(
        "route_decision",
        from_node="thinking",
        to_node="final_answer",
        reason="direct_answer",
        current_step=current_step,
        step_count=step_count,
        request_id=state.get("request_id"),
    )
    return "final_answer"


def route_after_risk_check(state: AgentState) -> str:
    """风控检查后的路由决策

    根据风险评估结果决定下一步：
    - approval_wait: 需要人工审批（高风险操作）
    - final_answer: 风控拒绝执行
    - tool_call: 风险可控，继续执行

    风险等级：
    - low: 查询类操作，直接执行
    - medium: 写操作但金额较小，直接执行
    - high: 敏感操作或较大金额，需要审批
    - critical: 高风险关键词（delete/payment/transfer），必须审批
    """
    current_step = state.get("current_step", "")
    risk_level = state.get("risk_level", "low")
    risk_reason = state.get("risk_reason")
    tool_calls = state.get("tool_calls", [])
    tool_names = [t.get("tool_name") for t in tool_calls]

    # 需要审批 - 高风险操作
    if current_step == "approval_wait":
        logger.warning(
            "route_decision",
            from_node="risk_check",
            to_node="approval_wait",
            reason="approval_required",
            risk_level=risk_level,
            risk_reason=risk_reason,
            tools=tool_names,
            request_id=state.get("request_id"),
        )
        return "approval_wait"

    # 风控拒绝 - 触发安全策略
    if state.get("error_code") == "ERR_TOOL_RISK_REJECTED":
        logger.warning(
            "route_decision",
            from_node="risk_check",
            to_node="final_answer",
            reason="risk_rejected",
            risk_level=risk_level,
            risk_reason=risk_reason,
            request_id=state.get("request_id"),
        )
        return "final_answer"

    # 继续执行 - 风险可控
    logger.info(
        "route_decision",
        from_node="risk_check",
        to_node="tool_call",
        reason="risk_acceptable",
        risk_level=risk_level,
        tools=tool_names,
        request_id=state.get("request_id"),
    )
    return "tool_call"


def route_after_tool_call(state: AgentState) -> str:
    """工具调用后的路由决策

    工具执行结果决定下一步：
    - approval_wait: 工具返回需要审批（如大额交易）
    - final_answer: 所有工具都失败，无法继续
    - thinking: 有成功结果，继续推理下一步

    工具结果状态：
    - success: 成功执行，继续推理
    - pending_approval: 等待审批（金额超阈值等）
    - rejected: 风控直接拒绝
    - failed: 执行失败（网络错误、参数错误等）
    """
    current_step = state.get("current_step", "")
    tool_results = state.get("tool_results", [])
    request_id = state.get("request_id")

    # 需要审批等待 - 工具判断需要人工确认
    if current_step == "approval_wait":
        approval_id = state.get("approval_id")
        logger.warning(
            "route_decision",
            from_node="tool_call",
            to_node="approval_wait",
            reason="tool_requires_approval",
            approval_id=approval_id,
            request_id=request_id,
        )
        return "approval_wait"

    # 检查工具执行结果
    if tool_results:
        success_count = sum(1 for r in tool_results if r.get("status") == "success")
        failed_count = sum(1 for r in tool_results if r.get("status") == "failed")

        # 所有工具都失败
        if failed_count == len(tool_results):
            errors = [r.get("error_message") for r in tool_results if r.get("error_message")]
            logger.error(
                "route_decision",
                from_node="tool_call",
                to_node="final_answer",
                reason="all_tools_failed",
                failed_count=failed_count,
                errors=errors[:2],  # 只记录前两个错误
                request_id=request_id,
            )
            return "final_answer"

    # 有成功结果 - 继续推理循环
    logger.info(
        "route_decision",
        from_node="tool_call",
        to_node="thinking",
        reason="continue_reasoning",
        tool_count=len(tool_results),
        success_count=sum(1 for r in tool_results if r.get("status") == "success"),
        step_count=state.get("step_count"),
        request_id=request_id,
    )
    return "thinking"


def route_after_approval(state: AgentState) -> str:
    """审批后的路由决策

    审批结果处理：
    - approved: 审批通过，继续执行工具
    - rejected: 审批拒绝，生成拒绝消息
    - pending: 等待审批（interrupt 状态，正常不会执行到这里）

    审批流程：
    1. Agent 在 approval_wait 节点被 interrupt 暂停
    2. 审批系统通过 Kafka 发送审批结果
    3. ApprovalCallbackHandler 恢复执行
    4. 根据审批结果决定下一步
    """
    approval_status = state.get("approval_status")
    approval_id = state.get("approval_id")
    request_id = state.get("request_id")

    # 审批通过 - 继续执行工具
    if approval_status == "approved":
        logger.info(
            "route_decision",
            from_node="approval_wait",
            to_node="tool_call",
            reason="approval_approved",
            approval_id=approval_id,
            request_id=request_id,
        )
        return "tool_call"

    # 审批拒绝 - 终止执行
    if approval_status == "rejected":
        logger.warning(
            "route_decision",
            from_node="approval_wait",
            to_node="final_answer",
            reason="approval_rejected",
            approval_id=approval_id,
            request_id=request_id,
        )
        return "final_answer"

    # 等待审批 - interrupt 状态（正常不会执行到这里）
    logger.info(
        "route_decision",
        from_node="approval_wait",
        to_node="final_answer",
        reason="waiting_approval",
        approval_id=approval_id,
        approval_status=approval_status,
        request_id=request_id,
    )
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
