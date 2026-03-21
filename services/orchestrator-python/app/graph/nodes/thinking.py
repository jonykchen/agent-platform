"""思考节点 - 模型推理，决定下一步行动"""

import structlog

from app.graph.state import AgentState

logger = structlog.get_logger()


async def thinking_node(state: AgentState) -> dict:
    """思考节点

    使用模型分析当前状态，决定：
    1. 是否需要调用工具
    2. 是否需要 RAG 检索
    3. 是否可以直接回答
    4. 任务是否完成

    Returns:
        更新状态字典，包含：
        - current_step: 当前步骤类型
        - tool_calls: 需要调用的工具列表
        - thinking: 推理过程
        - error: 错误信息（如有）
    """
    logger.info(
        "thinking_node started",
        request_id=state["request_id"],
        step_count=state["step_count"],
    )

    # 检查是否超过最大步骤数
    if state["step_count"] >= state["max_steps"]:
        return {
            "current_step": "max_steps_exceeded",
            "error": f"超过最大步骤数 {state['max_steps']}",
            "error_code": "ERR_AGENT_MAX_STEPS_EXCEEDED",
        }

    # TODO: 调用模型网关进行推理
    # 当前使用 Mock 实现

    user_input = state["input"]

    # 简单意图分类
    if _is_query_request(user_input):
        # 需要查询类工具
        tool_call = {
            "call_id": f"call_{state['step_count']}",
            "tool_name": _detect_tool(user_input),
            "arguments": _extract_arguments(user_input),
        }
        return {
            "current_step": "tool_call",
            "tool_calls": [tool_call],
            "thinking": f"分析用户输入，判断需要调用 {tool_call['tool_name']} 工具",
            "step_count": state["step_count"] + 1,
        }

    if _is_rag_request(user_input):
        # 需要 RAG 检索
        return {
            "current_step": "rag_retrieve",
            "thinking": "分析用户输入，判断需要进行知识检索",
            "step_count": state["step_count"] + 1,
        }

    # 可以直接回答
    return {
        "current_step": "final_answer",
        "output": _generate_direct_response(user_input),
        "thinking": "简单问题，可以直接回答",
        "step_count": state["step_count"] + 1,
    }


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


def _generate_direct_response(input: str) -> str:
    """生成直接响应"""
    # Mock 响应
    return f"收到您的问题：{input[:50]}。这是一个简单的咨询，我可以直接为您解答。\n\n请问还有其他需要帮助的吗？"