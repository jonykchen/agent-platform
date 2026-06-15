"""思考节点 - 模型推理，决定下一步行动

核心职责：
1. 分析用户输入，理解意图
2. 决定执行路径：
   - 工具调用：需要外部数据或执行操作
   - RAG 检索：需要知识库支持（暂未实现）
   - 直接回答：简单问题，无需外部资源
3. 生成工具调用参数（如需要）

推理流程：
┌─────────────────────────────────────────┐
│           用户输入                       │
│               │                         │
│               ▼                         │
│        ┌─────────────┐                  │
│        │ 意图分类    │                   │
│        └─────────────┘                  │
│               │                         │
│    ┌──────────┼──────────┐              │
│    │          │          │              │
│ [查询类]   [知识类]   [简单问答]         │
│    │          │          │              │
│    ▼          ▼          ▼              │
│ tool_call  rag_retrieve  final_answer   │
│    │          │          │              │
│    ▼          └──────────┴──► END       │
│ 工具名+参数                              │
└─────────────────────────────────────────┘

意图分类规则：
- 查询类关键词：查询、订单、用户、信息、状态、余额
- 知识类关键词：什么是、如何、说明、介绍、文档、政策
- 其他：直接回答

输出字段：
- current_step: 下一步类型 (tool_call/rag_retrieve/final_answer)
- tool_calls: 工具调用列表（如需要）
- thinking: 推理过程描述
- step_count: 累加步骤计数

【技术选型】ReAct 模式 vs Plan-and-Execute 模式
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 模式               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ ReAct (当前选择)   │ • 首字响应快（直接推理）    │ • 复杂任务可能多轮循环      │
│                    │ • 循环可控（max_steps）     │ • 无全局规划                │
│                    │ • 适合单工具简单推理        │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Plan-and-Execute   │ • 全局规划，步骤明确        │ • 首字响应延迟高（需先规划）│
│                    │ • 复杂任务执行更高效        │ • 规划失败需重试            │
│                    │ • 可并行执行独立步骤        │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Multi-Agent        │ • 跨域协作能力强            │ • 编排复杂度高              │
│                    │ • 专业分工，质量高          │ • 通信开销大                │
│                    │                             │ • 调试困难                  │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择 ReAct 的原因】
本项目主要处理客服场景（订单查询、用户信息、简单操作），特点：
1. 请求简单：90%+ 的请求只需 1-2 步工具调用
2. 响应快：用户期望首字响应 < 2s
3. 追踪易：每步都有日志，便于问题定位

Plan-and-Execute 更适合：数据分析、报告生成、多步骤自动化工作流。
"""

import json
import time

import structlog

from app.core.config import config
from app.core.exceptions import AllProvidersDownError, ModelTimeoutError
from app.core.metrics import record_model_call
from app.graph.state import AgentState

logger = structlog.get_logger()

# 系统提示词模板
SYSTEM_PROMPT = """你是一个智能助手，负责分析用户请求并决定最佳行动方案。

你的职责：
1. 分析用户输入，理解意图
2. 决定执行路径：
   - 工具调用：需要外部数据或执行操作
   - 直接回答：简单问题，无需外部资源

当需要调用工具时，返回 tool_calls 格式。
当可以直接回答时，返回 content 内容。

可用工具：
- query_order_status: 查询订单状态，参数 order_id
- get_user_info: 获取用户信息，参数 user_id
- create_payment: 创建支付订单，参数 amount, user_id

请根据用户请求选择合适的行动。"""


async def thinking_node(state: AgentState) -> dict:
    """思考节点

    使用模型分析当前状态，决定：
    1. 是否需要调用工具
    2. 是否需要 RAG 检索
    3. 是否可以直接回答
    4. 任务是否完成

    输入状态：
    - input: 用户原始输入
    - messages: 对话历史
    - tool_results: 上一步工具结果（如有）

    输出状态：
    - current_step: 下一步类型
    - tool_calls: 工具调用列表
    - thinking: 推理过程
    - step_count: 累加后的步骤数
    - consecutive_errors: 连续失败计数（S-AGENT-11）

    Returns:
        更新状态字典
    """

    start_time = time.monotonic()
    request_id = state["request_id"]
    step_count = state["step_count"]
    max_steps = state["max_steps"]
    consecutive_errors = state.get("consecutive_errors", 0)

    # 检查取消标志
    from app.graph.nodes.cancel_check import check_cancel_flag

    cancel_result = await check_cancel_flag(state)
    if cancel_result:
        return cancel_result

    logger.info(
        "node_started",
        node="thinking",
        step=step_count,
        max_steps=max_steps,
        consecutive_errors=consecutive_errors,
        input_preview=state["input"][:100] if state.get("input") else "",
        request_id=request_id,
    )

    # 检查是否超过最大步骤数 - 防止无限循环
    if step_count >= max_steps:
        logger.warning(
            "step_limit_reached",
            step_count=step_count,
            max_steps=max_steps,
            request_id=request_id,
        )
        return {
            "current_step": "max_steps_exceeded",
            "error": f"超过最大步骤数 {max_steps}",
            "error_code": "ERR_AGENT_MAX_STEPS_EXCEEDED",
        }

    # RAG 检索门：知识型问题且尚未检索时，先走 RAG 节点补充上下文，再回到 thinking。
    # 检索后 retrieved_docs 被填充，避免再次触发，杜绝 thinking↔rag_retrieve 死循环。
    enable_rag = state.get("enable_rag", True)
    already_retrieved = bool(state.get("retrieved_docs"))
    if (
        enable_rag
        and not already_retrieved
        and step_count == 0
        and state.get("input")
        and _is_rag_request(state["input"])
    ):
        logger.info(
            "thinking_route_to_rag",
            reason="knowledge_request_detected",
            request_id=request_id,
        )
        return {
            "current_step": "rag_retrieve",
            "thinking": "检测到知识型问题，先检索知识库",
        }

    # 构建对话消息
    messages = await _build_messages(state)

    # 调用模型网关进行推理
    try:
        from app.tools.clients.model_gateway_client import get_model_gateway_client

        client = get_model_gateway_client()

        # 获取工具定义（如果有）
        tools = _get_available_tools(state)

        model_response = await client.chat_completion(
            messages=messages,
            model=config.default_model if hasattr(config, "default_model") else None,
            temperature=config.default_temperature if hasattr(config, "default_temperature") else 0.7,
            max_tokens=config.default_max_tokens if hasattr(config, "default_max_tokens") else 2000,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            fallback=True,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # 记录模型调用指标（成功）：供 model_call_total / model_call_latency_seconds
        # 告警与看板使用。model/provider 优先取响应回传值，缺省回落到配置默认。
        record_model_call(
            model=str(model_response.get("model") or getattr(config, "default_model", "unknown")),
            provider=str(model_response.get("provider") or "model-gateway"),
            status="success",
            latency=duration_ms / 1000.0,
        )

        # 解析模型响应
        result = _parse_model_response(model_response, step_count, request_id, duration_ms)

        # S-AGENT-11: 成功时重置连续失败计数
        result["consecutive_errors"] = 0

        logger.info(
            "node_completed",
            node="thinking",
            step=step_count,
            duration_ms=duration_ms,
            decision=result.get("current_step", "unknown"),
            consecutive_errors_reset=True,
            request_id=request_id,
        )

        return result

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # 记录模型调用指标（失败）：保证 model_call_total{status="error"} 有数据，
        # 否则错误率告警永远不会触发。
        record_model_call(
            model=str(getattr(config, "default_model", "unknown")),
            provider="model-gateway",
            status="error",
            latency=duration_ms / 1000.0,
        )

        # S-AGENT-11: 增加连续失败计数
        new_consecutive_errors = consecutive_errors + 1

        logger.error(
            "node_failed",
            node="thinking",
            step=step_count,
            duration_ms=duration_ms,
            error=str(e),
            error_type=type(e).__name__,
            consecutive_errors=new_consecutive_errors,
            request_id=request_id,
        )

        # 根据异常类型返回错误
        result = _handle_model_error(e, step_count, request_id)
        result["consecutive_errors"] = new_consecutive_errors
        return result


def _is_query_request(input: str) -> bool:
    """判断是否需要查询工具"""
    keywords = ["查询", "订单", "用户", "信息", "状态", "余额"]
    return any(k in input for k in keywords)


def _is_rag_request(input: str) -> bool:
    """判断是否需要 RAG 检索"""
    keywords = ["什么是", "如何", "说明", "介绍", "文档", "政策"]
    return any(k in input for k in keywords)


def _detect_tool(input: str) -> str:
    """检测需要的工具"""
    if "订单" in input:
        return "query_order_status"
    if "用户" in input:
        return "get_user_info"
    return "unknown"


def _extract_arguments(input: str) -> dict:
    """从输入提取工具参数"""
    # 简单提取逻辑
    import re

    # 提取订单号
    order_match = re.search(r"ORD[-\w]+", input)
    if order_match:
        return {"order_id": order_match.group()}

    # 提取用户 ID
    user_match = re.search(r"用户[号]?[:\s]?([a-zA-Z0-9]+)", input)
    if user_match:
        return {"user_id": user_match.group(1)}

    return {}


async def _build_messages(state: AgentState) -> list[dict]:
    """构建对话消息

    消息结构：
    1. System 提示词（定义 Agent 角色和能力）
    2. 对话历史（多轮对话支持）
    3. 工具结果（如果有）
    4. 当前用户输入

    【S-AGENT-03】集成上下文管理器，自动截断超长对话

    Args:
        state: Agent 状态

    Returns:
        OpenAI 格式的消息列表
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 注入 RAG 检索到的知识库文档（作为 system 上下文，供模型据此作答）
    if state.get("retrieved_docs"):
        doc_blocks = []
        for i, doc in enumerate(state["retrieved_docs"][:5]):
            content = doc.get("content") or doc.get("text") or ""
            source = doc.get("source") or doc.get("title") or f"doc_{i + 1}"
            if content:
                doc_blocks.append(f"[{source}]\n{content}")
        if doc_blocks:
            messages.append(
                {
                    "role": "system",
                    "content": "以下是与用户问题相关的知识库检索结果，请优先依据这些资料作答：\n\n"
                    + "\n\n".join(doc_blocks),
                }
            )

    # 添加对话历史
    if state.get("messages"):
        for msg in state["messages"]:
            if isinstance(msg, dict):
                messages.append(msg)

    # 添加工具结果（如果有）
    if state.get("tool_results"):
        for result in state["tool_results"]:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": result.get("call_id", ""),
                    "content": result.get("result_json", ""),
                }
            )

    # 添加当前输入
    messages.append({"role": "user", "content": state["input"]})

    # 【S-AGENT-03】上下文截断：防止 token 超限
    from app.core.config import config
    from app.core.context_manager import truncate_context_async

    max_context_tokens = getattr(config, "max_context_window_tokens", 128000)

    # 检查是否需要截断
    from app.core.token_counter import count_message_tokens

    current_tokens = count_message_tokens(messages)

    if current_tokens > max_context_tokens - 8000:  # 预留 8000 给响应
        logger.warning(
            "context_truncation_needed",
            current_tokens=current_tokens,
            max_tokens=max_context_tokens,
            request_id=state.get("request_id"),
        )
        # 异步版：被截断的历史走 LLM 生成高质量摘要（thinking 节点为 async）
        messages = await truncate_context_async(messages[1:], SYSTEM_PROMPT)  # 排除已添加的 system
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

        logger.info(
            "context_truncated",
            original_tokens=current_tokens,
            truncated_tokens=count_message_tokens(messages),
            message_count=len(messages),
            request_id=state.get("request_id"),
        )

    return messages


def _get_available_tools(state: AgentState) -> list[dict] | None:
    """获取可用工具定义

    工具定义格式遵循 OpenAI Function Calling 规范。
    从共享 mock_registry 获取定义，确保与 tool_call 节点一致。

    Args:
        state: Agent 状态（可从中获取租户特定的工具列表）

    Returns:
        工具定义列表，或 None（无可用工具）
    """
    from app.tools.mock_registry import MOCK_TOOL_DEFINITIONS

    return MOCK_TOOL_DEFINITIONS


def _parse_model_response(
    response: dict,
    step_count: int,
    request_id: str,
    duration_ms: int,
) -> dict:
    """解析模型响应

    响应类型判断：
    1. finish_reason == "tool_calls": 工具调用
    2. finish_reason == "stop": 直接回答
    3. 其他: 异常处理

    S-AGENT-04/05: 输出泄露检测在解析后进行

    Args:
        response: 模型网关返回的响应
        step_count: 当前步骤数
        request_id: 请求 ID
        duration_ms: 耗时

    Returns:
        状态更新字典
    """
    choices = response.get("choices", [])
    if not choices:
        logger.warning(
            "empty_choices",
            response=response,
            request_id=request_id,
        )
        return {
            "current_step": "error",
            "error": "模型返回空响应",
            "error_code": "ERR_MODEL_EMPTY_RESPONSE",
            "step_count": step_count + 1,
        }

    choice = choices[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason", "stop")

    # 工具调用
    if finish_reason == "tool_calls" or message.get("tool_calls"):
        tool_calls = []
        for tc in message.get("tool_calls", []):
            function = tc.get("function", {})
            try:
                arguments = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}

            tool_calls.append(
                {
                    "call_id": tc.get("id", f"call_{step_count}"),
                    "tool_name": function.get("name", ""),
                    "arguments": arguments,
                }
            )

        logger.debug(
            "parsed_tool_calls",
            tool_calls=tool_calls,
            request_id=request_id,
        )

        return {
            "current_step": "tool_call",
            "tool_calls": tool_calls,
            "thinking": f"模型决定调用 {len(tool_calls)} 个工具",
            "step_count": step_count + 1,
        }

    # 直接回答 - S-AGENT-04/05 输出泄露检测
    content = message.get("content", "")
    if content:
        # 输出泄露检测
        from app.core.output_guard import output_guard

        scan_result = output_guard.scan(content, {"request_id": request_id})

        if scan_result["action"] == "sanitize":
            content = output_guard.sanitize(content, {"request_id": request_id})
            logger.warning(
                "output_sanitized",
                leakage_type=scan_result["leakage_type"],
                request_id=request_id,
            )

        return {
            "current_step": "final_answer",
            "output": content,
            "thinking": "模型直接回答用户问题",
            "step_count": step_count + 1,
        }

    # 无内容响应
    return {
        "current_step": "error",
        "error": "模型返回无内容响应",
        "error_code": "ERR_MODEL_EMPTY_CONTENT",
        "step_count": step_count + 1,
    }


def _handle_model_error(error: Exception, step_count: int, request_id: str) -> dict:
    """处理模型调用错误

    错误类型映射：
    - ModelTimeoutError → ERR_MODEL_TIMEOUT
    - AllProvidersDownError → ERR_MODEL_ALL_PROVIDERS_DOWN
    - 其他 → ERR_MODEL_CALL_FAILED

    Args:
        error: 异常对象
        step_count: 当前步骤数
        request_id: 请求 ID

    Returns:
        状态更新字典
    """
    if isinstance(error, ModelTimeoutError):
        timeout_s = error.details.get("timeout_s", "unknown")
        return {
            "current_step": "error",
            "error": f"模型调用超时: {timeout_s}秒",
            "error_code": "ERR_MODEL_TIMEOUT",
            "step_count": step_count + 1,
        }

    if isinstance(error, AllProvidersDownError):
        return {
            "current_step": "error",
            "error": "所有模型提供商不可用",
            "error_code": "ERR_MODEL_ALL_PROVIDERS_DOWN",
            "step_count": step_count + 1,
        }

    # 其他错误
    return {
        "current_step": "error",
        "error": f"模型调用失败: {str(error)}",
        "error_code": "ERR_MODEL_CALL_FAILED",
        "step_count": step_count + 1,
    }
