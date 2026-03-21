"""Chat API - 对话补全

核心职责：
1. 接收用户对话请求
2. 管理 Agent 执行会话
3. 返回对话响应

请求处理流程：
┌─────────────────────────────────────────────────────────┐
│                   HTTP POST /chat/completions            │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 提取请求上下文  │                     │
│                  │ request_id      │                     │
│                  │ tenant_id       │                     │
│                  │ user_id         │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 创建/加载会话   │                     │
│                  │ session_id      │                     │
│                  │ 加载历史消息    │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 构建 Agent 状态 │                     │
│                  │ initial_state   │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 执行 Agent 图   │                     │
│                  │ graph.invoke()  │                     │
│                  └─────────────────┘                    │
│                           │                             │
│            ┌──────────────┼──────────────┐             │
│            │              │              │             │
│        [正常完成]    [需要审批]    [出错]                │
│            │              │              │             │
│            ▼              ▼              ▼              │
│      保存消息     保存 Checkpoint   返回错误            │
│      返回结果     返回 approval_id                      │
│                                                         │
│                  ┌─────────────────┐                    │
│                  │ 返回 ChatResponse│                    │
│                  └─────────────────┘                    │
└─────────────────────────────────────────────────────────┘

会话管理：
- session_id: 会话唯一标识，用于持久化对话历史
- 历史 messages 存储在 Redis，最多保留 10 条
- 新会话自动生成 session_id

审批恢复：
- POST /chat/resume 恢复审批等待的对话
- Kafka 回调自动恢复 (ApprovalCallbackHandler)

"""

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
    1. 提取请求上下文（request_id, tenant_id, user_id）
    2. 获取或创建会话，加载历史消息
    3. 构建 Agent 初始状态
    4. 运行 LangGraph 状态机
    5. 保存消息到会话
    6. 如果需要审批，保存 Checkpoint
    7. 返回结果

    Args:
        request: ChatRequest 对话请求
            - message: 用户输入消息
            - session_id: 可选的会话 ID
            - model: 可选的指定模型
            - stream: 是否流式输出（暂不支持）
        req: FastAPI Request 对象

    Returns:
        ChatResponse 对话响应
            - request_id: 请求追踪 ID
            - session_id: 会话 ID
            - response: Agent 生成的响应
            - finish_reason: 结束原因（stop/pending_approval/error）
            - approval_id: 审批 ID（如需要）
    """
    request_id = get_request_id()
    tenant_id = get_tenant_id()
    user_id = get_user_id()

    start_time = time.time()

    logger.info(
        "request_received",
        endpoint="/chat/completions",
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        message_length=len(request.message),
        session_id=request.session_id,
        stream=request.stream,
    )

    # 获取或创建会话
    session_id = get_or_create_session_id(request.session_id, tenant_id, user_id)

    logger.debug(
        "session_resolved",
        session_id=session_id,
        is_new=not request.session_id,
        request_id=request_id,
    )

    # 获取存储实例
    session_store = get_session_store()
    checkpoint_store = get_checkpoint_store()

    # 加载历史消息（用于多轮对话上下文）
    history = await session_store.get_history(session_id, limit=10)

    logger.debug(
        "history_loaded",
        session_id=session_id,
        message_count=len(history),
        request_id=request_id,
    )

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

    # 配置（用于 checkpoint 持久化）
    graph_config = {
        "configurable": {
            "thread_id": request_id,
        },
    }

    logger.info(
        "agent_execution_started",
        request_id=request_id,
        session_id=session_id,
        input_preview=request.message[:100],
        max_steps=config.max_agent_steps,
    )

    # 运行 Agent
    try:
        result = await graph.invoke(initial_state, config=graph_config)

        # 提取结果
        output = result.get("output", "")
        tool_calls = result.get("tool_calls", [])
        approval_id = result.get("approval_id")
        step_count = result.get("step_count", 0)

        # 保存消息到会话
        await session_store.append_message(session_id, "user", request.message)
        if output:
            await session_store.append_message(session_id, "assistant", output)

        # 如果需要审批，保存 Checkpoint 用于恢复
        if approval_id:
            await checkpoint_store.save(request_id, result)
            logger.info(
                "checkpoint_saved",
                request_id=request_id,
                approval_id=approval_id,
                reason="approval_required",
            )

        latency_ms = int((time.time() - start_time) * 1000)

        # 获取模型使用信息
        model_used = result.get("model_used", "qwen-max")
        prompt_tokens = result.get("prompt_tokens", 50)
        completion_tokens = result.get("completion_tokens", 100)
        total_tokens = prompt_tokens + completion_tokens

        # 计算成本（简化计算）
        cost_usd = total_tokens * 0.00001

        # 确定结束原因
        finish_reason = "stop"
        if approval_id:
            finish_reason = "pending_approval"
        elif result.get("error"):
            finish_reason = "error"

        logger.info(
            "request_completed",
            endpoint="/chat/completions",
            request_id=request_id,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            step_count=step_count,
            model_used=model_used,
            total_tokens=total_tokens,
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
        latency_ms = int((time.time() - start_time) * 1000)

        logger.error(
            "request_failed",
            endpoint="/chat/completions",
            request_id=request_id,
            error_type=type(e).__name__,
            error_message=str(e),
            latency_ms=latency_ms,
        )

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