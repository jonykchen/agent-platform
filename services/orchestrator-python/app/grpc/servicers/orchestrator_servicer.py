"""Orchestrator gRPC Servicer 实现

实现 OrchestratorService 的所有 RPC 方法。

【核心概念】gRPC vs HTTP 历史消息处理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

关键差异：
┌─────────────────────────────────────────────────────────────────────────┐
│ 协议       │ 历史来源                                     │ 说明        │
├───────────┼───────────────────────────────────────────────┼────────────┤
│ HTTP API  │ SessionStore.get_history(session_id)          │ 从 Redis 加载│
│ gRPC API  │ ChatRequest.history                            │ 直接传入     │
└─────────────────────────────────────────────────────────────────────────┘

Gateway Java 已经从数据库加载历史消息并通过 gRPC 传递，
Orchestrator Python **不应**再从 SessionStore 加载，直接使用 request.history。

【调用流程】
```
Gateway Java                Orchestrator Python
    │                              │
    │  ChatRequest {               │
    │    message: "你可以做什么"     │
    │    history: [                 │
    │      {role: "user",          │
    │       content: "你好"},       │
    │      {role: "assistant",     │
    │       content: "您好！"}      │
    │    ]                          │
    │  }                            │
    │ ─────────────────────────────>│
    │                              │
    │  ChatResponse {              │
    │    response: "我可以帮助..."   │
    │  }                           │
    │<───────────────────────────── │
```

【参考】
- contracts/proto/gateway/orchestrator.proto
- services/gateway-java/src/main/java/com/platform/gateway/service/OrchestratorClient.java
"""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator

import structlog
from grpc import aio

from app.core.config import config
from app.core.exceptions import BasePlatformException
from app.gen.common import error_code_pb2
from app.gen.gateway import orchestrator_pb2, orchestrator_pb2_grpc
from app.graph.builder import get_agent_graph
from app.graph.state import create_initial_state
from app.grpc.utils.context_extractor import extract_context_from_request
from app.grpc.utils.error_mapper import create_error_detail

logger = structlog.get_logger()


class OrchestratorServiceServicer(orchestrator_pb2_grpc.OrchestratorServiceServicer):
    """Orchestrator 服务实现

    实现以下 RPC 方法：
    - ChatCompletion: 对话补全
    - StreamChatCompletion: 流式对话补全
    - ExecuteAgent: Agent 任务执行
    - GetSession: 查询会话信息
    - GetRunStatus: 查询运行状态
    - CancelRun: 取消运行
    """

    async def ChatCompletion(
        self,
        request: orchestrator_pb2.ChatRequest,
        context: aio.ServicerContext,
    ) -> orchestrator_pb2.ChatResponse:
        """对话补全

        关键实现：
        1. 从 RequestContext 提取元数据
        2. **直接使用 request.history**（不从 SessionStore 加载）
        3. 构建初始状态并执行 Agent
        4. 返回响应

        Args:
            request: ChatRequest 包含消息和历史
            context: gRPC 上下文

        Returns:
            ChatResponse 响应结果
        """
        start_time = time.time()

        # 提取请求上下文
        ctx = extract_context_from_request(request.context)
        request_id = ctx.get("request_id") or f"req_{uuid.uuid4().hex[:16]}"
        tenant_id = ctx.get("tenant_id") or "default"
        user_id = ctx.get("user_id") or "anonymous"
        session_id = ctx.get("session_id") or f"sess_{uuid.uuid4().hex[:16]}_{tenant_id}"

        logger.info(
            "grpc_chat_completion_received",
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            message_length=len(request.message),
            history_count=len(request.history),
        )

        try:
            # ====== 关键：直接使用 request.history ======
            # Gateway Java 已经从数据库加载历史并传递，不从 SessionStore 加载
            history = [{"role": msg.role, "content": msg.content} for msg in request.history]

            # 构建初始状态
            initial_state = create_initial_state(
                input=request.message,
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                request_id=request_id,
                max_steps=config.max_agent_steps,
            )

            # 设置历史消息（关键！）
            initial_state["messages"] = history

            # 获取 Agent 图
            graph = get_agent_graph()

            # 配置
            graph_config = {
                "configurable": {
                    "thread_id": request_id,
                },
            }

            logger.info(
                "agent_execution_started",
                request_id=request_id,
                session_id=session_id,
                history_count=len(history),
                max_steps=config.max_agent_steps,
            )

            # 执行 Agent
            result = await graph.ainvoke(initial_state, config=graph_config)

            # 提取结果
            output = result.get("output", "")
            tool_calls = result.get("tool_calls", [])
            approval_id = result.get("approval_id")

            latency_ms = int((time.time() - start_time) * 1000)

            # 确定结束原因
            finish_reason = "stop"
            if approval_id:
                finish_reason = "pending_approval"
            elif result.get("error"):
                finish_reason = "error"

            # 构建 ToolCall 列表
            tool_calls_proto = []
            for tc in tool_calls:
                tool_calls_proto.append(
                    orchestrator_pb2.ToolCall(
                        call_id=tc.get("tool_id", ""),
                        tool_name=tc.get("name", ""),
                        arguments_json=tc.get("arguments", "{}"),
                    )
                )

            # 构建响应
            response = orchestrator_pb2.ChatResponse(
                context=request.context,
                response=output,
                model_used=result.get("model_used", "qwen-max"),
                prompt_tokens=result.get("prompt_tokens", 50),
                completion_tokens=result.get("completion_tokens", 100),
                total_tokens=result.get("prompt_tokens", 50) + result.get("completion_tokens", 100),
                cost_usd=float(result.get("total_tokens", 150) * 0.00001),
                latency_ms=latency_ms,
                finish_reason=finish_reason,
                created_at=int(time.time() * 1000),
            )

            # 添加 tool_calls
            if tool_calls_proto:
                response.tool_calls.extend(tool_calls_proto)

            logger.info(
                "grpc_chat_completion_completed",
                request_id=request_id,
                latency_ms=latency_ms,
                finish_reason=finish_reason,
                tokens=response.total_tokens,
            )

            # ====== 持久化对话到数据库 ======
            await self._persist_conversation(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                request_id=request_id,
                user_message=request.message,
                assistant_message=output,
                model_used=result.get("model_used", "qwen-max"),
                total_tokens=response.total_tokens,
                latency_ms=latency_ms,
                status="completed" if finish_reason == "stop" else finish_reason,
            )

            return response

        except BasePlatformException as e:
            # 业务异常
            logger.error(
                "grpc_chat_completion_business_error",
                request_id=request_id,
                error_code=e.code,
                message=e.message,
            )

            # 创建 ErrorDetail
            error_detail = create_error_detail(e, request_id)

            # 构建错误响应
            response = orchestrator_pb2.ChatResponse(
                context=request.context,
                response="",
                finish_reason="error",
                created_at=int(time.time() * 1000),
            )
            response.error.CopyFrom(error_detail)

            return response

        except Exception as e:
            # 未知异常
            logger.exception(
                "grpc_chat_completion_error",
                request_id=request_id,
                error=str(e),
            )

            # 创建通用错误响应
            error_detail = error_code_pb2.ErrorDetail(
                code=error_code_pb2.ERR_INTERNAL,
                message=str(e),
                user_message="处理请求时发生错误",
                request_id=request_id,
            )

            response = orchestrator_pb2.ChatResponse(
                context=request.context,
                response="",
                finish_reason="error",
                created_at=int(time.time() * 1000),
            )
            response.error.CopyFrom(error_detail)

            return response

    # 流式分块大小（字符数）。答案级流式按此粒度切块下发，
    # 在"首字延迟"与"块数量"之间取平衡。
    STREAM_CHUNK_SIZE = 24

    async def StreamChatCompletion(
        self,
        request: orchestrator_pb2.ChatRequest,
        context: aio.ServicerContext,
    ) -> AsyncIterator[orchestrator_pb2.ChatStreamChunk]:
        """流式对话补全（SSE / gRPC streaming）

        【流式策略：答案级流式】
        完整执行 Agent 图（thinking → risk_check → tool_call → approval_wait →
        final_answer），确保工具调用、风控、审批等逻辑不被绕过；图执行完成后，
        将最终答案按 STREAM_CHUNK_SIZE 切块逐块下发，并在最后一块携带
        finish_reason。

        - 命中审批中断时：发送一个 finish_reason="pending_approval" 的终止块，
          附带 approval_id，前端据此提示"等待审批"。
        - 发生错误时：发送 finish_reason="error" 的终止块，附带 ErrorDetail。

        【关于 token 级流式】
        当前 thinking 节点使用自定义 ModelGatewayClient 而非 LangChain ChatModel，
        LangGraph 无法自动产出 token 级事件。如需 token 级流式，需将 thinking
        节点改造为基于 LangChain ChatModel 的 astream（后续优化项），届时本方法
        切换为消费 graph.astream_events 即可，对外协议（ChatStreamChunk）不变。

        Args:
            request: ChatRequest 包含消息和历史
            context: gRPC 上下文

        Yields:
            ChatStreamChunk 流式响应块
        """
        start_time = time.time()

        ctx = extract_context_from_request(request.context)
        request_id = ctx.get("request_id") or f"req_{uuid.uuid4().hex[:16]}"
        tenant_id = ctx.get("tenant_id") or "default"
        user_id = ctx.get("user_id") or "anonymous"
        session_id = ctx.get("session_id") or f"sess_{uuid.uuid4().hex[:16]}_{tenant_id}"

        logger.info(
            "grpc_stream_chat_completion_received",
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            message_length=len(request.message),
            history_count=len(request.history),
        )

        chunk_index = 0

        try:
            # 直接使用 request.history（与 ChatCompletion 一致）
            history = [{"role": msg.role, "content": msg.content} for msg in request.history]

            initial_state = create_initial_state(
                input=request.message,
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                request_id=request_id,
                max_steps=config.max_agent_steps,
            )
            initial_state["messages"] = history

            graph = get_agent_graph()
            graph_config = {"configurable": {"thread_id": request_id}}

            # 执行完整 Agent 图（保留工具/风控/审批逻辑）
            result = await graph.ainvoke(initial_state, config=graph_config)

            output = result.get("output", "")
            approval_id = result.get("approval_id")
            error = result.get("error")

            # 审批中断：发送等待审批终止块
            if approval_id:
                yield orchestrator_pb2.ChatStreamChunk(
                    context=request.context,
                    chunk_id=f"{request_id}_approval",
                    chunk_index=chunk_index,
                    delta=output or "",
                    finish_reason="pending_approval",
                )
                logger.info(
                    "grpc_stream_pending_approval",
                    request_id=request_id,
                    approval_id=approval_id,
                )
                return

            # 业务错误：发送错误终止块
            if error:
                yield orchestrator_pb2.ChatStreamChunk(
                    context=request.context,
                    chunk_id=f"{request_id}_error",
                    chunk_index=chunk_index,
                    delta="",
                    finish_reason="error",
                    error=error_code_pb2.ErrorDetail(
                        code=error_code_pb2.ERR_INTERNAL,
                        message=str(error)[:500],
                        user_message="处理请求时发生错误",
                        request_id=request_id,
                    ),
                )
                return

            # 正常输出：按块切分逐块下发
            text = output or ""
            total = len(text)
            for offset in range(0, total, self.STREAM_CHUNK_SIZE):
                delta = text[offset : offset + self.STREAM_CHUNK_SIZE]
                is_last = offset + self.STREAM_CHUNK_SIZE >= total
                yield orchestrator_pb2.ChatStreamChunk(
                    context=request.context,
                    chunk_id=f"{request_id}_{chunk_index}",
                    chunk_index=chunk_index,
                    delta=delta,
                    finish_reason="stop" if is_last else "",
                )
                chunk_index += 1
                # 让出事件循环，使下游能及时收到块（避免一次性刷出）
                await asyncio.sleep(0)

            # 空输出兜底：仍需发送一个带 finish_reason 的终止块
            if total == 0:
                yield orchestrator_pb2.ChatStreamChunk(
                    context=request.context,
                    chunk_id=f"{request_id}_empty",
                    chunk_index=chunk_index,
                    delta="",
                    finish_reason="stop",
                )

            logger.info(
                "grpc_stream_chat_completion_completed",
                request_id=request_id,
                latency_ms=int((time.time() - start_time) * 1000),
                chunks=chunk_index,
                output_length=total,
            )

            # ====== 持久化对话到数据库 ======
            await self._persist_conversation(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                request_id=request_id,
                user_message=request.message,
                assistant_message=text,
                model_used=result.get("model_used", "deepseek-chat"),
                total_tokens=result.get("total_tokens", 0),
                latency_ms=int((time.time() - start_time) * 1000),
                status="completed",
            )

        except BasePlatformException as e:
            logger.error(
                "grpc_stream_business_error",
                request_id=request_id,
                error_code=e.code,
                message=e.message,
            )
            error_detail = create_error_detail(e, request_id)
            chunk = orchestrator_pb2.ChatStreamChunk(
                context=request.context,
                chunk_id=f"{request_id}_error",
                chunk_index=chunk_index,
                delta="",
                finish_reason="error",
            )
            chunk.error.CopyFrom(error_detail)
            yield chunk

        except Exception as e:
            logger.exception(
                "grpc_stream_chat_completion_error",
                request_id=request_id,
                error=str(e),
            )
            yield orchestrator_pb2.ChatStreamChunk(
                context=request.context,
                chunk_id=f"{request_id}_error",
                chunk_index=chunk_index,
                delta="",
                finish_reason="error",
                error=error_code_pb2.ErrorDetail(
                    code=error_code_pb2.ERR_INTERNAL,
                    message=str(e)[:500],
                    user_message="处理请求时发生错误",
                    request_id=request_id,
                ),
            )

    async def ExecuteAgent(
        self,
        request: orchestrator_pb2.AgentRunRequest,
        context: aio.ServicerContext,
    ) -> orchestrator_pb2.AgentRunResponse:
        """Agent 任务执行

        暂未实现。
        """
        return orchestrator_pb2.AgentRunResponse(
            context=request.context,
            run_id="",
            session_id=request.session_id,
            status="error",
            error=error_code_pb2.ErrorDetail(
                code=error_code_pb2.ERR_INTERNAL,
                message="ExecuteAgent not implemented",
                user_message="Agent 任务执行暂不支持",
            ),
        )

    async def GetSession(
        self,
        request: orchestrator_pb2.GetSessionRequest,
        context: aio.ServicerContext,
    ) -> orchestrator_pb2.GetSessionResponse:
        """查询会话信息

        暂未实现。
        """
        return orchestrator_pb2.GetSessionResponse(
            context=request.context,
            session_id=request.session_id,
            status="unknown",
        )

    async def GetRunStatus(
        self,
        request: orchestrator_pb2.GetRunStatusRequest,
        context: aio.ServicerContext,
    ) -> orchestrator_pb2.GetRunStatusResponse:
        """查询运行状态

        暂未实现。
        """
        return orchestrator_pb2.GetRunStatusResponse(
            context=request.context,
            run_id=request.run_id,
            status="unknown",
        )

    async def CancelRun(
        self,
        request: orchestrator_pb2.CancelRunRequest,
        context: aio.ServicerContext,
    ) -> orchestrator_pb2.CancelRunResponse:
        """取消运行

        暂未实现。
        """
        return orchestrator_pb2.CancelRunResponse(
            context=request.context,
            run_id=request.run_id,
            cancelled=False,
            status="unknown",
        )

    async def _persist_conversation(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        request_id: str,
        user_message: str,
        assistant_message: str,
        model_used: str,
        total_tokens: int,
        latency_ms: int,
        status: str,
    ) -> None:
        """持久化对话到数据库

        将用户消息和助手回复保存到 agent_session 表，
        同时创建 agent_run 记录用于审计和历史查询。

        Args:
            session_id: 会话 ID
            tenant_id: 租户 ID
            user_id: 用户 ID
            request_id: 请求 ID
            user_message: 用户消息
            assistant_message: 助手回复
            model_used: 使用的模型
            total_tokens: 总 token 数
            latency_ms: 延迟（毫秒）
            status: 运行状态
        """
        try:
            from app.infrastructure.database import get_db_pool

            pool = get_db_pool()
            if not pool:
                logger.warning("persist_skip", reason="no_db_pool")
                return

            async with pool.acquire() as conn:
                # 1. 确保会话存在
                await conn.execute(
                    """
                    INSERT INTO agent_session (id, tenant_id, user_id, title, status, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, 'active', NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET updated_at = NOW()
                    """,
                    session_id,
                    tenant_id,
                    user_id,
                    user_message[:100] if user_message else "新对话",
                )

                # 2. 获取下一个 run_number
                run_number = await conn.fetchval(
                    "SELECT COALESCE(MAX(run_number), 0) + 1 FROM agent_run WHERE session_id = $1",
                    session_id,
                )

                # 3. 创建 agent_run 记录
                run_id = f"run_{request_id}"
                await conn.execute(
                    """
                    INSERT INTO agent_run (
                        id, session_id, tenant_id, user_id, run_number,
                        input_message, output_message, status,
                        model_used, total_tokens, duration_ms,
                        started_at, completed_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
                    """,
                    run_id,
                    session_id,
                    tenant_id,
                    user_id,
                    run_number,
                    user_message,
                    assistant_message,
                    status,
                    model_used,
                    total_tokens,
                    latency_ms,
                )

                # 4. 创建 agent_step 记录（用户消息）
                await conn.execute(
                    """
                    INSERT INTO agent_step (
                        id, run_id, tenant_id, step_order, step_type,
                        content, status, created_at
                    ) VALUES (gen_random_uuid(), $1, $2, 0, 'user_message', $3, 'completed', NOW())
                    """,
                    run_id,
                    tenant_id,
                    user_message,
                )

                # 5. 创建 agent_step 记录（助手回复）
                await conn.execute(
                    """
                    INSERT INTO agent_step (
                        id, run_id, tenant_id, step_order, step_type,
                        content, status, created_at
                    ) VALUES (gen_random_uuid(), $1, $2, 1, 'assistant_message', $3, 'completed', NOW())
                    """,
                    run_id,
                    tenant_id,
                    assistant_message,
                )

                logger.info(
                    "conversation_persisted",
                    session_id=session_id,
                    run_id=run_id,
                    run_number=run_number,
                )

        except Exception as e:
            logger.error(
                "persist_conversation_failed",
                session_id=session_id,
                error=str(e),
            )
