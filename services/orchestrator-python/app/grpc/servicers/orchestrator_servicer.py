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

import time
import uuid
from typing import AsyncIterator

import grpc
from grpc import aio
import structlog

from app.gen.gateway import orchestrator_pb2, orchestrator_pb2_grpc
from app.gen.common import error_code_pb2
from app.grpc.utils.context_extractor import extract_context_from_request
from app.grpc.utils.error_mapper import map_exception_to_grpc_status, create_error_detail
from app.graph.builder import get_agent_graph
from app.graph.state import create_initial_state
from app.core.config import config
from app.core.exceptions import BasePlatformException

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
            history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.history
            ]

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
            result = await graph.invoke(initial_state, config=graph_config)

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

    async def StreamChatCompletion(
        self,
        request: orchestrator_pb2.ChatRequest,
        context: aio.ServicerContext,
    ) -> AsyncIterator[orchestrator_pb2.ChatStreamChunk]:
        """流式对话补全

        暂未实现，返回单个错误块。
        """
        yield orchestrator_pb2.ChatStreamChunk(
            context=request.context,
            chunk_id="error",
            chunk_index=0,
            delta="",
            finish_reason="error",
            error=error_code_pb2.ErrorDetail(
                code=error_code_pb2.ERR_INTERNAL,
                message="StreamChatCompletion not implemented",
                user_message="流式输出暂不支持",
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
