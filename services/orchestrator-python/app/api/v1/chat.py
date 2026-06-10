"""Chat API - 对话补全

核心职责：
1. 接收用户对话请求
2. 管理 Agent 执行会话
3. 返回对话响应

【核心概念】Chat API 是 Agent 的入口
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chat API 是用户与 Agent 系统的主要交互点：
- 接收用户自然语言输入
- 调用 LangGraph Agent 进行推理
- 返回 Agent 的响应或审批请求

【技术选型】会话管理策略
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 策略               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Redis 存储 (选择)  │ • 跨实例共享                │ • 网络开销                  │
│                    │ • 持久化                    │ • Redis 故障影响服务        │
│                    │ • 支持 TTL 过期             │                              │
│                    │ • 无需本地内存              │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 内存存储           │ • 最快                      │ • 实例重启丢失              │
│                    │ • 无网络开销                │ • 无法跨实例                │
│                    │                             │ • 内存占用                  │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 数据库存储         │ • 最可靠                    │ • 性能最差                  │
│                    │ • 完整审计                  │ • 写入压力大                │
│                    │                             │ • 需缓存层                  │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择 Redis 的原因】
1. Agent 会话需要跨实例共享（K8s 多副本部署）
2. Redis 提供 TTL 自动过期，无需清理旧会话
3. 性能平衡：比内存慢，但远快于数据库

【请求处理流程】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

【审批恢复机制】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

当 Agent 执行到 approval_wait 节点时：
1. LangGraph 使用 interrupt 机制暂停执行
2. 保存 Checkpoint 到 Redis（含当前状态）
3. 返回 approval_id 给前端
4. 用户在前端或审批系统审批后：
   - POST /chat/resume 恢复执行
   - 或 Kafka 回调自动恢复 (ApprovalCallbackHandler)
5. Agent 从中断点继续执行

【历史消息限制】
- 最多保留 10 条历史消息
- 超出部分触发摘要生成（见 summary_generator.py）

"""

import asyncio
import json
import time
import uuid

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.middleware.request_context import get_request_id, get_tenant_id, get_user_id
from app.core.config import config
from app.graph.builder import get_agent_graph
from app.graph.state import create_initial_state
from app.memory.checkpoint_store import get_checkpoint_store
from app.memory.session_store import get_session_store

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


# SSE 流式分块大小（字符数）
STREAM_CHUNK_SIZE = 24


def _sse_event(data: dict) -> str:
    """格式化为 SSE data 帧"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# 节点 → 用户可见进度阶段映射（用于流式进度事件）
_NODE_STAGE_LABELS: dict[str, str] = {
    "thinking": "思考中",
    "rag_retrieve": "检索知识库",
    "risk_check": "安全检查",
    "tool_call": "调用工具",
    "approval_wait": "等待审批",
    "final_answer": "生成回答",
}


async def _stream_chat_sse(
    request: "ChatRequest",
    request_id: str,
    tenant_id: str,
    user_id: str,
    start_time: float,
):
    """SSE 流式对话补全生成器

    生产级 Agent 流式策略：通过 graph.astream(stream_mode="updates") 驱动
    Agent 图执行，实时推送每个节点的进度事件（思考/检索/工具调用/审批），
    待最终答案生成后再以 token 块逐帧下发，最后发送 [DONE] 终止帧。

    带工具调用的 Agent 无法对整段对话做纯 token 流式（工具调用会打断生成），
    因此采用业界通行的「进度事件 + 最终答案流式」方案（与带工具的 ChatGPT 一致）。

    SSE 帧格式（与前端 useSSE.ts 约定一致，额外字段前端忽略）：
    - 进度：{"delta": "", "finish_reason": null, "stage": "thinking", "node": "..."}
    - 增量：{"delta": "...", "finish_reason": null, "session_id": "..."}
    - 结束：{"delta": "", "finish_reason": "stop"|"pending_approval"|"error", ...}
    - 终止：data: [DONE]
    """
    session_id = get_or_create_session_id(request.session_id, tenant_id, user_id)
    session_store = get_session_store()
    checkpoint_store = get_checkpoint_store()

    try:
        history = await session_store.get_history(session_id, limit=10)

        # 注入长时记忆上下文（与非流式路径保持一致）
        from app.memory.memory_manager import (
            format_memories_for_context,
            retrieve_relevant_memories,
        )

        relevant_memories = await retrieve_relevant_memories(
            query=request.message,
            tenant_id=tenant_id,
            user_id=user_id,
            top_k=config.memory_retrieve_top_k,
        )
        memory_context = format_memories_for_context(relevant_memories)

        initial_state = create_initial_state(
            input=request.message,
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            max_steps=config.max_agent_steps,
        )
        initial_state["messages"] = history
        if memory_context:
            initial_state["messages"].append({"role": "system", "content": memory_context})

        graph = get_agent_graph()
        graph_config = {"configurable": {"thread_id": request_id}}

        # 累积最终状态：astream(updates) 每次产出 {node_name: state_delta}
        final_output = ""
        approval_id = None
        error = None
        last_state: dict = {}
        seen_stages: set[str] = set()

        async for chunk in graph.astream(initial_state, config=graph_config, stream_mode="updates"):
            for node_name, update in chunk.items():
                if not isinstance(update, dict):
                    continue
                last_state.update(update)

                # 推送节点进度事件（每个阶段仅推一次，避免循环刷屏）
                stage = _NODE_STAGE_LABELS.get(node_name)
                if stage and node_name not in seen_stages:
                    seen_stages.add(node_name)
                    yield _sse_event(
                        {
                            "delta": "",
                            "finish_reason": None,
                            "session_id": session_id,
                            "request_id": request_id,
                            "node": node_name,
                            "stage": stage,
                        }
                    )
                    await asyncio.sleep(0)

                if update.get("output"):
                    final_output = update["output"]
                if update.get("approval_id"):
                    approval_id = update["approval_id"]
                if update.get("error"):
                    error = update["error"]

        # 审批中断：astream 在 interrupt_before=approval_wait 处暂停，
        # 通过 graph 状态快照获取 approval_id 并保存 checkpoint
        if approval_id is None:
            try:
                snapshot = await graph.aget_state(graph_config)
                approval_id = (snapshot.values or {}).get("approval_id")
                if approval_id and not final_output:
                    final_output = (snapshot.values or {}).get("output", "")
            except Exception:
                pass

        # 持久化会话消息
        await session_store.append_message(session_id, "user", request.message)
        if final_output and not approval_id:
            await session_store.append_message(session_id, "assistant", final_output)

        # 审批中断
        if approval_id:
            await checkpoint_store.save(request_id, last_state)
            yield _sse_event(
                {
                    "delta": final_output or "",
                    "finish_reason": "pending_approval",
                    "session_id": session_id,
                    "request_id": request_id,
                    "approval_id": approval_id,
                }
            )
            yield "data: [DONE]\n\n"
            return

        # 业务错误
        if error:
            yield _sse_event(
                {
                    "delta": "",
                    "finish_reason": "error",
                    "session_id": session_id,
                    "request_id": request_id,
                    "error": str(error)[:500],
                }
            )
            yield "data: [DONE]\n\n"
            return

        # 正常输出按块下发（打字机效果）
        text = final_output or ""
        total = len(text)
        for offset in range(0, total, STREAM_CHUNK_SIZE):
            delta = text[offset : offset + STREAM_CHUNK_SIZE]
            is_last = offset + STREAM_CHUNK_SIZE >= total
            yield _sse_event(
                {
                    "delta": delta,
                    "finish_reason": "stop" if is_last else None,
                    "session_id": session_id,
                    "request_id": request_id,
                }
            )
            await asyncio.sleep(0)

        if total == 0:
            yield _sse_event(
                {
                    "delta": "",
                    "finish_reason": "stop",
                    "session_id": session_id,
                    "request_id": request_id,
                }
            )

        yield "data: [DONE]\n\n"

        # 流式完成后写入长时记忆（与非流式路径一致）
        if final_output:
            from app.memory.memory_manager import (
                extract_key_entities_from_tool_results,
                save_to_long_term_memory,
            )

            key_entities = extract_key_entities_from_tool_results(last_state.get("tool_results", []))
            await save_to_long_term_memory(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                user_query=request.message,
                agent_response=final_output,
                key_entities=key_entities,
            )

        logger.info(
            "stream_request_completed",
            endpoint="/chat/completions",
            request_id=request_id,
            latency_ms=int((time.time() - start_time) * 1000),
            output_length=total,
        )

    except Exception as e:
        logger.exception(
            "stream_request_failed",
            request_id=request_id,
            error=str(e),
        )
        yield _sse_event(
            {
                "delta": "",
                "finish_reason": "error",
                "session_id": session_id,
                "request_id": request_id,
                "error": str(e)[:500],
            }
        )
        yield "data: [DONE]\n\n"


@router.post("/chat/completions")
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

    # 流式输出：返回 SSE 响应（text/event-stream）
    if request.stream:
        return StreamingResponse(
            _stream_chat_sse(request, request_id, tenant_id, user_id, start_time),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲，确保实时下发
            },
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

    # 检索相关长时记忆（跨会话召回）
    from app.memory.memory_manager import (
        format_memories_for_context,
        retrieve_relevant_memories,
    )

    relevant_memories = await retrieve_relevant_memories(
        query=request.message,
        tenant_id=tenant_id,
        user_id=user_id,
        top_k=config.memory_retrieve_top_k,
    )

    # 格式化记忆为上下文
    memory_context = format_memories_for_context(relevant_memories)

    logger.info(
        "memories_retrieved_for_context",
        request_id=request_id,
        memory_count=len(relevant_memories),
        has_context=bool(memory_context),
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

    # 添加记忆上下文（如果有）
    if memory_context:
        initial_state["messages"].append(
            {
                "role": "system",
                "content": memory_context,
            }
        )
        logger.debug(
            "memory_context_injected",
            request_id=request_id,
            context_length=len(memory_context),
        )

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

        # 保存消息到会话（触发摘要生成）
        await session_store.append_message(session_id, "user", request.message)
        if output:
            await session_store.append_message(session_id, "assistant", output)

            # 保存到长时记忆（跨会话召回）
            from app.memory.memory_manager import (
                extract_key_entities_from_tool_results,
                save_to_long_term_memory,
            )

            # 提取关键实体（从工具结果中）
            key_entities = extract_key_entities_from_tool_results(result.get("tool_results", []))

            # 存储对话到长时记忆
            await save_to_long_term_memory(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                user_query=request.message,
                agent_response=output,
                key_entities=key_entities,
            )

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

    if output and session_id:
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
