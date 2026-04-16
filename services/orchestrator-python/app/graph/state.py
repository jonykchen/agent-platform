"""LangGraph 状态机定义

【核心概念】状态管理在 Agent 系统中的作用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

状态是 Agent 执行过程中所有信息的载体，贯穿整个推理循环。

为什么选择 LangGraph 的状态管理？
┌─────────────────────────────────────────────────────────────────────────┐
│  方案              │  优点                    │  缺点                  │
├────────────────────┼──────────────────────────┼────────────────────────┤
│  全局变量          │  简单直接                │  并发不安全、难调试    │
│  类封装            │  OOP 友好                │  序列化复杂、状态追踪难│
│  LangGraph State   │  自动追踪、支持回滚      │  学习曲线              │
│  ✓ TypedDict       │  类型安全、IDE 支持      │                        │
└─────────────────────────────────────────────────────────────────────────┘

【技术选型】TypedDict vs dataclass vs Pydantic Model
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ TypedDict (选择)   │ • Python 3.8+ 原生支持      │ • 无运行时验证              │
│                    │ • 零运行时开销              │ • IDE 类型推断依赖插件      │
│                    │ • LangGraph 原生支持        │                              │
│                    │ • JSON 序列化简单           │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ dataclass          │ • OOP 友好                  │ • 序列化需自定义            │
│                    │ • 运行时类型检查            │ • 不可变更新繁琐            │
│                    │ • 默认值支持                │ • LangGraph 需适配          │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Pydantic Model     │ • 完整的验证机制            │ • 与 LangGraph 集成不紧密   │
│                    │ • JSON 自动序列化           │ • 运行时开销                │
│                    │ • 错误信息友好              │ • 需额外的依赖              │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择 TypedDict 的原因】
1. LangGraph 的 Annotated[list, add_messages] reducer 只支持 TypedDict
2. Agent 状态需要序列化到 Redis/MemorySaver，TypedDict 直接是 dict
3. 零运行时开销：Python Agent 追求性能，不需要额外验证层
4. 类型安全：mypy/Pyright 能检查类型错误，开发阶段已足够

【Annotated[list, add_messages] 的魔法原理】
这是 LangGraph 的核心特性，实现了类似 Redux reducer 的不可变更新：
- 当节点返回 {"messages": [new_msg]} 时，LangGraph 自动执行：
  new_state["messages"] = old_state["messages"] + [new_msg]
- 如果返回 {"messages": [{"id": "x", ...}]，add_messages 会删除指定 ID
- 这避免了手动管理消息列表的复杂性

【设计原则】状态字段分类
1. 会话元数据：session_id, tenant_id, user_id, request_id
   - 用于多租户隔离、审计追踪
2. 执行控制：step_count, max_steps, current_step
   - 防止无限循环，控制执行流程
3. 数据流转：messages, tool_calls, tool_results
   - Agent 与外部系统交互的数据
4. 风控审批：risk_level, approval_id, approval_status
   - 高风险操作的人工审批机制
5. 错误处理：error, error_code, consecutive_errors
   - 统一错误码体系，便于前端处理
   - S-AGENT-11: 连续失败计数，防止无限错误循环

【参考】
- LangGraph 状态管理: https://langchain-ah.readthedocs.io/en/latest/concepts/state.html
- TypedDict PEP 589: https://peps.python.org/pep-0589/
"""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Agent 状态 - LangGraph 状态机核心数据结构

    【设计模式】Immutable State + Reducer

    状态在节点间传递时遵循不可变原则：
    - 每个节点返回的是"状态更新"而非完整状态
    - LangGraph 自动合并更新到当前状态
    - 类似 React 的 setState 或 Redux 的 reducer

    示例：
        # 节点返回部分更新
        def my_node(state: AgentState) -> dict:
            return {"step_count": state["step_count"] + 1}

        # LangGraph 自动合并：
        # new_state = {**old_state, **returned_updates}

    【消息累积机制】
    messages 字段使用 add_messages reducer：
    - 返回 {"messages": [new_msg]} → 追加到现有列表
    - 返回 {"messages": [{"id": "x", "content": "删除"}]} → 删除指定 ID

    这是 LangGraph 的核心特性，让对话历史自动累积。
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # 会话元数据 - 用于多租户隔离和追踪
    # ═══════════════════════════════════════════════════════════════════════════

    # 对话历史（自动累积）
    # Annotated[list, add_messages] 是 LangGraph 的特殊语法
    # 表示：1) 这是一个列表类型 2) 使用 add_messages reducer 合并更新
    # 效果：每次返回 {"messages": [...]} 会追加到现有列表，而非覆盖
    messages: Annotated[list, add_messages]

    # 当前输入 - 用户本轮消息
    input: str

    # 会话信息 - 用于：
    # - session_id: 持久化对话历史，支持多轮对话
    # - tenant_id: 多租户数据隔离，确保不同租户数据不混淆
    # - user_id: 权限校验，审计追踪
    # - request_id: 全链路追踪，日志关联
    session_id: str
    tenant_id: str
    user_id: str
    request_id: str

    # ═══════════════════════════════════════════════════════════════════════════
    # 执行控制 - 防止无限循环，控制 Agent 行为
    # ═══════════════════════════════════════════════════════════════════════════

    # 步骤计数器 - 每次进入 thinking 节点时递增
    step_count: int

    # 最大步骤限制 - 防止 Agent 陷入无限循环
    # 默认 10 步，可根据任务复杂度调整
    max_steps: int

    # 当前步骤类型 - 控制流程路由
    # 可能值：tool_call, rag_retrieve, final_answer, error, max_steps_exceeded
    current_step: str

    # ═══════════════════════════════════════════════════════════════════════════
    # 工具调用数据 - Agent 与外部系统交互
    # ═══════════════════════════════════════════════════════════════════════════

    # 工具调用请求 - 由 thinking 节点生成
    # 格式：[{"call_id": "...", "tool_name": "...", "arguments": {...}}]
    tool_calls: list[dict]

    # 工具执行结果 - 由 tool_call 节点返回
    # 格式：[{"call_id": "...", "status": "success", "result_json": "..."}]
    tool_results: list[dict]

    # ═══════════════════════════════════════════════════════════════════════════
    # RAG 检索结果 - 知识库支持（暂未实现）
    # ═══════════════════════════════════════════════════════════════════════════

    # RAG 检索到的文档片段
    retrieved_docs: list[dict]

    # ═══════════════════════════════════════════════════════════════════════════
    # 风险检查 - 高风险操作的人工审批机制
    # ═══════════════════════════════════════════════════════════════════════════

    # 风险等级 - 由 risk_check 节点评估
    # 可能值：low, medium, high, critical
    risk_level: str

    # 风险原因 - 记录触发风控的具体原因
    risk_reason: str | None

    # ═══════════════════════════════════════════════════════════════════════════
    # 审批信息 - 支持高风险操作的人工审批
    # ═══════════════════════════════════════════════════════════════════════════

    # 审批单 ID - 需要审批时生成，用于追踪审批状态
    approval_id: str | None

    # 审批状态 - 由审批系统回调更新
    # 可能值：pending, approved, rejected
    approval_status: str | None

    # ═══════════════════════════════════════════════════════════════════════════
    # 输出与错误处理
    # ═══════════════════════════════════════════════════════════════════════════

    # 最终输出 - 由 final_answer 节点生成
    output: str

    # 错误信息 - 发生异常时记录
    error: str | None

    # 错误码 - 统一的错误码体系，便于前端处理
    # 格式：ERR_<模块>_<错误类型>，如 ERR_AGENT_MAX_STEPS_EXCEEDED
    error_code: str | None

    # 连续失败计数 - 用于 S-AGENT-11（连续失败 ≥ 3 次终止）
    consecutive_errors: int

    # 最大连续失败阈值 - 默认 3
    max_consecutive_errors: int

    # ═══════════════════════════════════════════════════════════════════════════
    # 扩展元数据 - 灵活扩展字段
    # ═══════════════════════════════════════════════════════════════════════════

    # 用于存储非标准字段，如 A/B 测试分组、客户端版本等
    metadata: dict


def create_initial_state(
    input: str,
    session_id: str,
    tenant_id: str,
    user_id: str,
    request_id: str,
    max_steps: int = 10,
) -> AgentState:
    """创建初始状态

    【工厂函数模式】
    使用工厂函数而非直接构造 TypedDict 的好处：
    1. 提供默认值，简化调用
    2. 类型检查更严格
    3. 可扩展验证逻辑

    Args:
        input: 用户输入消息
        session_id: 会话 ID（用于持久化）
        tenant_id: 租户 ID（用于多租户隔离）
        user_id: 用户 ID（用于权限校验）
        request_id: 请求追踪 ID（全链路追踪）
        max_steps: 最大步骤数，防止无限循环（默认 10）

    Returns:
        AgentState: 初始化的状态字典

    使用示例：
        state = create_initial_state(
            input="查询订单 ORD-12345",
            session_id="sess_abc123",
            tenant_id="tenant_001",
            user_id="user_123",
            request_id="req_xyz789",
        )
        # 然后传入 graph.invoke(state)
    """
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
        consecutive_errors=0,
        max_consecutive_errors=3,
        metadata={},
    )