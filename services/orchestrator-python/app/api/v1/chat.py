"""Chat API - 对话补全"""

import time
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

import structlog

from app.api.middleware.request_context import get_request_id, get_tenant_id, get_user_id
from app.core.config import config
from app.graph.builder import get_agent_graph
from app.graph.state import create_initial_state
from app.memory.session_store import get_session_store, SessionStore
from app.memory.checkpoint_store import get_checkpoint_store, CheckpointStore
from app.tools.clients import get_model_gateway_client, get_tool_bus_client

logger = structlog.get_logger()
router = APIRouter()


class ChatRequest(BaseModel):
    """对话请求"""

    message: str = Field(..., min_length=1, max_length=8000, description="用户输入消息")
    session_id: str | None = Field(None, description="会话 ID")
    model: str | None = Field(None, description="指定模型")
    temperature: float | None = Field(None, ge=0, le=2, description="温度参数")
    max_tokens: int | None = Field(None, ge=1, le=8000, description="最大 token 数")
    stream: bool = Field(False, description="是否流式输出")
    enable_rag: bool = Field(True, description="是否启用 RAG")
    enable_tools: bool = Field(True, description="是否启用工具")


class ChatResponse(BaseModel):
    """对话响应"""

    request_id: str
    session_id: str
    response: str
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: int
    finish_reason: str
    tool_calls: list[dict] | None = None
    approval_id: str | None = None


def get_or_create_session_id(session_id: str | None, tenant_id: str, user_id: str) -> str:
    """获取或创建会话 ID"""
    if session_id:
        return session_id
    # 生成新会话 ID
    return f"sess_{uuid.uuid4().hex[:16]}_{tenant_id}"


@router.post("/chat/completions", response_model=ChatResponse)
async def chat_completion(request: ChatRequest, req: Request):
    """对话补全

    执行 Agent 编排流程：
    1. 加载/创建会话
    2. 构建初始状态
    3. 运行 LangGraph 状态机
    4. 返回结果
    """
    request_id = get_request_id()
    tenant_id = get_tenant_id()
    user_id = get_user_id()

    start_time = time.time()

    logger.info(
        "Chat request",
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        message_length=len(request.message),
        session_id=request.session_id,
        stream=request.stream,
    )

    # 获取或创建会话
    session_id = get_or_create_session_id(request.session_id, tenant_id, user_id)

    # 获取存储实例
    session_store = get_session_store()
    checkpoint_store = get_checkpoint_store()

    # 加载历史消息
    history = await session_store.get_history(session_id, limit=10)

    # 构建初始状态
    initial_state = create_initial_state(
        input=request.message,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        request_id=request_id,
        max_steps=config.max_agent_steps,
    )

    # 添加历史消息
    initial_state["messages"] = history

    # 获取 Agent 图
    graph = get_agent_graph()

    # 配置（用于 checkpoint）
    graph_config = {
        "configurable": {
            "thread_id": request_id,
        },
    }

    # 运行 Agent
    try:
        result = await graph.invoke(initial_state, config=graph_config)

        # 提取结果
        output = result.get("output", "")
        tool_calls = result.get("tool_calls", [])
        approval_id = result.get("approval_id")

        # 保存消息到会话
        await session_store.append_message(session_id, "user", request.message)
        if output:
            await session_store.append_message(session_id, "assistant", output)

        # 如果需要审批，保存 checkpoint
        if approval_id:
            await checkpoint_store.save(request_id, result)

        latency_ms = int((time.time() - start_time) * 1000)

        # 获取模型使用信息（从结果或默认）
        model_used = result.get("model_used", "qwen-max")
        prompt_tokens = result.get("prompt_tokens", 50)
        completion_tokens = result.get("completion_tokens", 100)
        total_tokens = prompt_tokens + completion_tokens

        # 计算成本（简化）
        cost_usd = total_tokens * 0.00001  # Mock 成本

        finish_reason = "stop"
        if approval_id:
            finish_reason = "pending_approval"
        elif result.get("error"):
            finish_reason = "error"

        logger.info(
            "Chat completed",
            request_id=request_id,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            approval_id=approval_id,
        )

        return ChatResponse(
            request_id=request_id,
            session_id=session_id,
            response=output,
            model_used=model_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            tool_calls=tool_calls if tool_calls else None,
            approval_id=approval_id,
        )

    except Exception as e:
        logger.error(
            "Chat failed",
            request_id=request_id,
            error=str(e),
        )

        latency_ms = int((time.time() - start_time) * 1000)

        return ChatResponse(
            request_id=request_id,
            session_id=session_id,
            response=f"抱歉，处理您的请求时出现问题：{str(e)}",
            model_used="error",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=0.0,
            latency_ms=latency_ms,
            finish_reason="error",
        )


@router.post("/chat/resume")
async def resume_chat(request: dict, req: Request):
    """恢复暂停的对话（审批通过后）

    Args:
        request: {"run_id": "...", "approval_status": "approved/rejected"}
    """
    run_id = request.get("run_id")
    approval_status = request.get("approval_status")

    if not run_id or not approval_status:
        return {"error": "缺少必要参数"}

    checkpoint_store = get_checkpoint_store()

    # 加载 checkpoint
    checkpoint = await checkpoint_store.load(run_id)
    if not checkpoint:
        return {"error": "Checkpoint 不存在或已过期"}

    # 更新审批状态
    checkpoint["approval_status"] = approval_status

    # 获取 Agent 图
    graph = get_agent_graph()

    # 恢复执行
    graph_config = {
        "configurable": {
            "thread_id": run_id,
        },
    }

    # 从审批等待节点恢复
    result = await graph.invoke(checkpoint, config=graph_config)

    # 清理 checkpoint
    await checkpoint_store.delete(run_id)

    # 保存最终消息
    session_store = get_session_store()
    session_id = checkpoint.get("session_id")
    output = result.get("output", "")

    if output:
        await session_store.append_message(session_id, "assistant", output)

    return {
        "run_id": run_id,
        "session_id": session_id,
        "output": output,
        "status": "completed",
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, req: Request):
    """获取会话信息"""
    session_store = get_session_store()
    info = await session_store.get_session_info(session_id)
    history = await session_store.get_history(session_id)
    return {
        "session_id": session_id,
        "info": info,
        "history": history,
    }


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str, req: Request):
    """清空会话"""
    session_store = get_session_store()
    await session_store.clear(session_id)
    return {"session_id": session_id, "status": "cleared"}