"""LangGraph 状态机节点 - Agent 推理引擎核心

【模块架构】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    ┌─────────────────────────────────┐
                    │         User Request            │
                    │      (用户输入 + Context)       │
                    └─────────────────┬───────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LangGraph State Machine                            │
│                                                                             │
│                    ┌─────────────────────────────────┐                      │
│                    │      thinking_node              │                      │
│                    │   (思考节点 - 模型推理)          │                      │
│                    │                                 │                      │
│                    │ • 分析用户意图                   │                      │
│                    │ • 决定执行路径                   │                      │
│                    │ • 生成工具调用参数               │                      │
│                    └─────────────────┬───────────────┘                      │
│                                      │                                      │
│              ┌───────────────────────┼───────────────────────┐              │
│              │                       │                       │              │
│              ▼                       ▼                       ▼              │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐        │
│  │  tool_call_node │     │rag_retrieve_node│     │ final_answer    │        │
│  │  (工具调用节点) │     │  (RAG 检索节点) │     │    _node        │        │
│  │                 │     │                 │     │ (最终答案节点)  │        │
│  │ • 参数校验      │     │ • 知识库检索    │     │                 │        │
│  │ • ToolBus 调用 │     │ • 向量匹配      │     │ • 整合结果      │        │
│  │ • 结果解析      │     │ • 文档返回      │     │ • 生成回复      │        │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘        │
│              │                       │                       │              │
│              ▼                       │                       │              │
│  ┌─────────────────┐                 │                       │              │
│  │ risk_check_node │                 │                       │              │
│  │  (风险检查节点) │                 │                       │              │
│  │                 │                 │                       │              │
│  │ • 评估风险等级  │                 │                       │              │
│  │ • 决定审批流程  │                 │                       │              │
│  └─────────────────┘                 │                       │              │
│              │                       │                       │              │
│              ▼                       │                       │              │
│  ┌─────────────────┐                 │                       │              │
│  │approval_wait_   │                 │                       │              │
│  │    node         │                 │                       │              │
│  │ (审批等待节点)  │                 │                       │              │
│  │                 │                 │                       │              │
│  │ • 等待人工审批  │                 │                       │              │
│  │ • 超时处理      │                 │                       │              │
│  └─────────────────┘                 │                       │              │
│              │                       │                       │              │
│              └───────────────────────┴───────────────────────┘              │
│                                      │                                      │
│                                      ▼                                      │
│                    ┌─────────────────────────────────┐                      │
│                    │      thinking_node              │                      │
│                    │   (循环推理，max_steps=10)      │                      │
│                    └─────────────────────────────────┘                      │
│                                      │                                      │
│                                      ▼                                      │
│                    ┌─────────────────────────────────┐                      │
│                    │      Final Response             │                      │
│                    │   (返回给用户)                  │                      │
│                    └─────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘

【节点职责】
┌────────────────────┬──────────────────────────────────────────────────────────────┐
│ 节点                │ 职责描述                                                      │
├────────────────────┼──────────────────────────────────────────────────────────────┤
│ thinking_node      │ 思考节点：模型推理，分析意图，决定下一步路径                   │
│                    │ • 查询类 → tool_call_node                                     │
│                    │ • 知识类 → rag_retrieve_node                                  │
│                    │ • 简单问答 → final_answer_node                                │
│ tool_call_node     │ 工具调用节点：参数校验、ToolBus 调用、结果解析                 │
│                    │ 集成 JSONSchemaValidator 防止恶意输入                         │
│ rag_retrieve_node  │ RAG 检索节点：知识库检索、向量匹配、文档返回                   │
│                    │ (暂未完全实现)                                                 │
│ risk_check_node    │ 风险检查节点：评估操作风险等级，决定是否需要审批               │
│                    │ • LOW → 直接执行                                              │
│                    │ • MEDIUM → 记录审计                                           │
│                    │ • HIGH/CRITICAL → approval_wait_node                         │
│ approval_wait_node │ 审批等待节点：等待人工审批，超时处理                          │
│                    │ 超时时间: APPROVAL_WAIT_TIMEOUT_S = 7200s (2小时)             │
│ final_answer_node  │ 最终答案节点：整合所有结果，生成最终回复                      │
│                    │ 输出 output_guard 检测敏感信息                                │
└────────────────────┴──────────────────────────────────────────────────────────────┘

【状态流转】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AgentState 状态定义 (见 state.py):

```python
class AgentState(TypedDict):
    messages: list[dict]           # 对话历史
    tool_calls: list[dict]         # 待执行/已执行的工具调用
    current_step: str              # 当前节点标识
    risk_level: str                # 风险等级: low/medium/high/critical
    needs_approval: bool           # 是否需要审批
    consecutive_errors: int        # 连续失败计数 (S-AGENT-11)
    step_count: int                # 步骤计数，防止无限循环
    thinking: str                  # 推理过程描述
    final_answer: str              # 最终答案
```

状态流转图:
```
START → thinking → [tool_call | rag_retrieve | final_answer]
                              │
                              ▼
                        risk_check
                              │
                              ▼
                   [approval_wait | 直接返回]
                              │
                              ▼
                        thinking (循环)
                              │
                              ▼
                        final_answer → END
```

【推理模式】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

当前采用 ReAct (Reasoning + Acting) 模式:

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 模式               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ ReAct (当前)       │ • 首字响应快（直接推理）    │ • 复杂任务可能多轮循环      │
│                    │ • 循环可控（max_steps）     │ • 无全局规划                │
│                    │ • 适合单工具简单推理        │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Plan-and-Execute   │ • 全局规划                  │ • 首字响应慢                │
│ (未来可选)         │ • 复杂任务更稳定            │ • 规划可能失败              │
│                    │ • 更可控                    │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Multi-Agent        │ • 任务分解                  │ • 架构复杂                  │
│ (未来可选)         │ • 专家协作                  │ • 协调开销                  │
│                    │ • 适合复杂场景              │                              │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【使用示例】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
# 1. 在 LangGraph builder 中使用节点
from langgraph.graph import StateGraph
from app.graph.nodes import (
    thinking_node,
    tool_call_node,
    risk_check_node,
    approval_wait_node,
    final_answer_node,
    rag_retrieve_node,
)
from app.graph.state import AgentState

# 构建状态图
graph = StateGraph(AgentState)

# 添加节点
graph.add_node("thinking", thinking_node)
graph.add_node("tool_call", tool_call_node)
graph.add_node("risk_check", risk_check_node)
graph.add_node("approval_wait", approval_wait_node)
graph.add_node("final_answer", final_answer_node)
graph.add_node("rag_retrieve", rag_retrieve_node)

# 定义边（条件路由）
graph.add_conditional_edges(
    "thinking",
    route_after_thinking,  # 路由函数
    {
        "tool_call": "tool_call",
        "rag_retrieve": "rag_retrieve",
        "final_answer": "final_answer",
    }
)

graph.add_edge("tool_call", "risk_check")
graph.add_conditional_edges(
    "risk_check",
    route_after_risk_check,
    {
        "approval_wait": "approval_wait",
        "thinking": "thinking",
    }
)

graph.add_edge("approval_wait", "thinking")
graph.add_edge("final_answer", END)

# 2. 直接调用节点（测试）
from app.graph.nodes import thinking_node
from app.graph.state import AgentState

state: AgentState = {
    "messages": [{"role": "user", "content": "查询订单 ORD-123 的状态"}],
    "tool_calls": [],
    "current_step": "",
    "risk_level": "low",
    "needs_approval": False,
    "consecutive_errors": 0,
    "step_count": 0,
    "thinking": "",
    "final_answer": "",
}

# 执行思考节点
result = await thinking_node(state)
print(result["current_step"])  # "tool_call"
print(result["tool_calls"])    # [{"name": "query_order_status", "arguments": {"order_id": "ORD-123"}}]

# 3. 工具调用节点
from app.graph.nodes import tool_call_node

state_with_tool_calls = {
    ...,
    "tool_calls": [{"name": "query_order_status", "arguments": {"order_id": "ORD-123"}}]
}

result = await tool_call_node(state_with_tool_calls)
print(result["messages"][-1])  # 包含工具执行结果

# 4. 风险检查节点
from app.graph.nodes import risk_check_node

result = await risk_check_node(state_after_tool_call)
print(result["risk_level"])     # "medium"
print(result["needs_approval"]) # True/False

# 5. 最终答案节点
from app.graph.nodes import final_answer_node

result = await final_answer_node(state_with_all_results)
print(result["final_answer"])  # "订单 ORD-123 当前状态为已完成..."
```

【节点输出字段】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

每个节点返回部分状态更新（Partial[AgentState]）:

┌────────────────────┬──────────────────────────────────────────────────────────────┐
│ 节点                │ 输出字段                                                      │
├────────────────────┼──────────────────────────────────────────────────────────────┤
│ thinking_node      │ current_step, tool_calls, thinking, step_count                │
│ tool_call_node     │ messages (追加工具结果), consecutive_errors                   │
│ rag_retrieve_node  │ messages (追加知识库文档)                                      │
│ risk_check_node    │ risk_level, needs_approval                                    │
│ approval_wait_node │ messages (追加审批结果), needs_approval                       │
│ final_answer_node  │ final_answer, messages (追加最终回复)                         │
└────────────────────┴──────────────────────────────────────────────────────────────┘

【安全红线】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- [S-AGENT-03] 用户输入限制 MAX_USER_INPUT_TOKENS=8000
- [S-AGENT-04] thinking_node 集成上下文截断 (context_manager)
- [S-AGENT-05] final_answer_node 集成输出防护 (output_guard)
- [S-AGENT-08] tool_call_node 超时控制 TOOL_CALL_TIMEOUT_S=15
- [S-AGENT-10] 循环限制 MAX_AGENT_STEPS=10，防止无限循环
- [S-AGENT-11] consecutive_errors 计数，连续失败 3 次终止

【性能指标】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 简单问答 P95: < 6s (thinking → final_answer)
- 单工具任务 P95: < 15s (thinking → tool_call → risk_check → final_answer)
- 工具调用成功率: ≥ 98%

【参考】
- LangGraph 文档: https://langchain-ai.github.io/langgraph/
- ReAct 论文: https://arxiv.org/abs/2210.03629
- Plan-and-Execute: https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/
"""

from app.graph.nodes.approval_wait import approval_wait_node
from app.graph.nodes.final_answer import final_answer_node
from app.graph.nodes.rag_retrieve import rag_retrieve_node
from app.graph.nodes.risk_check import risk_check_node
from app.graph.nodes.thinking import thinking_node
from app.graph.nodes.tool_call import tool_call_node

__all__ = [
    "thinking_node",
    "tool_call_node",
    "risk_check_node",
    "approval_wait_node",
    "final_answer_node",
    "rag_retrieve_node",
]
