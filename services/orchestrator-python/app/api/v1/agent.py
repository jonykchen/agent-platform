"""Agent API - Agent 运行管理

提供 Agent 执行任务的 API 端点。

【核心概念】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Agent API 用于：
1. 启动 Agent 执行任务
2. 查询执行状态
3. 取消正在执行的任务

【执行流程】
┌─────────────────────────────────────────────────────────────────────────┐
│                    POST /api/v1/agents/{agent_id}/runs                   │
│                              │                                          │
│                              ▼                                          │
│                    ┌─────────────────┐                                   │
│                    │  创建运行任务   │                                    │
│                    │  生成 run_id    │                                    │
│                    └─────────────────┘                                   │
│                              │                                          │
│               ┌──────────────┴──────────────┐                           │
│               │                             │                           │
│          [sync 模式]                   [async 模式]                     │
│               │                             │                           │
│               ▼                             ▼                           │
│      执行并等待结果              立即返回 run_id                          │
│               │                             │                           │
│               ▼                             ▼                           │
│         返回结果              后台异步执行                                │
│                                   │                                      │
│                                   ▼                                      │
│                          完成后回调 callback_url                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

【状态查询】
GET /api/v1/runs/{run_id}
- 返回当前状态、进度、已执行步数

【取消运行】
POST /api/v1/runs/{run_id}/cancel
- 设置取消标志，等待 Agent 检查点停止
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

import structlog

from app.api.middleware.request_context import get_request_id, get_tenant_id, get_user_id
from app.core.config import config
from app.graph.builder import get_agent_graph
from app.graph.state import create_initial_state
from app.memory.session_store import get_session_store
from app.infrastructure.redis_client import get_redis
from app.schemas.agent import (
    AgentCancelResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunStatus,
    AgentStatus,
    ExecutionMode,
    StepInfo,
)

logger = structlog.get_logger()
router = APIRouter()


def get_or_create_session_id(session_id: str | None, tenant_id: str, user_id: str) -> str:
    """获取或创建会话 ID"""
    if session_id:
        return session_id
    return f"sess_{uuid.uuid4().hex[:16]}_{tenant_id}"


@router.post("/agents/{agent_id}/runs", response_model=AgentRunResponse)
async def start_agent_run(agent_id: str, request: AgentRunRequest, req: Request):
    """启动 Agent 运行

    执行 Agent 编排流程，支持同步和异步两种模式。

    Args:
        agent_id: Agent 类型标识
        request: AgentRunRequest 运行请求
            - session_id: 可选的会话 ID
            - task: 任务描述
            - execution_mode: 执行模式（sync/async）
            - callback_url: 异步完成回调 URL
        req: FastAPI Request 对象

    Returns:
        AgentRunResponse 运行响应
            - run_id: 运行唯一标识
            - status: 运行状态
            - result: 执行结果（同步模式完成时）

    Raises:
        HTTPException: 参数校验失败或执行错误
    """
    request_id = get_request_id()
    tenant_id = get_tenant_id()
    user_id = get_user_id()
    run_id = f"run_{uuid.uuid4().hex[:16]}"

    start_time = time.time()

    logger.info(
        "agent_run_started",
        agent_id=agent_id,
        run_id=run_id,
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        execution_mode=request.execution_mode.value,
        task_preview=request.task[:100],
    )

    # 获取或创建会话
    session_id = get_or_create_session_id(request.session_id, tenant_id, user_id)

    # 构建初始状态
    initial_state = create_initial_state(
        input=request.task,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        request_id=request_id,
        max_steps=config.max_agent_steps,
    )

    # 添加上下文信息
    if request.context:
        initial_state["context"] = request.context

    # 获取 Agent 图
    graph = get_agent_graph()

    # 配置（用于 checkpoint 持久化）
    graph_config = {
        "configurable": {
            "thread_id": run_id,
        },
    }

    # 同步模式：执行并等待结果
    if request.execution_mode == ExecutionMode.SYNC:
        try:
            result = await graph.invoke(initial_state, config=graph_config)

            # 提取结果
            output = result.get("output", "")
            step_count = result.get("step_count", 0)
            model_used = result.get("model_used", "qwen-max")
            total_tokens = result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)

            # 确定状态
            status = AgentRunStatus.COMPLETED
            if result.get("error"):
                status = AgentRunStatus.FAILED
            elif result.get("approval_id"):
                status = AgentRunStatus.PENDING_APPROVAL

            latency_ms = int((time.time() - start_time) * 1000)

            # 构建步骤信息
            steps = None
            if result.get("step_history"):
                steps = [
                    StepInfo(
                        step_number=i,
                        node_name=step.get("node", "unknown"),
                        action=step.get("action", ""),
                        status="completed",
                    )
                    for i, step in enumerate(result["step_history"])
                ]

            logger.info(
                "agent_run_completed",
                agent_id=agent_id,
                run_id=run_id,
                request_id=request_id,
                status=status.value,
                step_count=step_count,
                latency_ms=latency_ms,
                total_tokens=total_tokens,
            )

            return AgentRunResponse(
                run_id=run_id,
                status=status,
                result=output if status != AgentRunStatus.FAILED else None,
                error=result.get("error") if status == AgentRunStatus.FAILED else None,
                steps=steps,
                model_used=model_used,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                approval_id=result.get("approval_id"),
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "agent_run_failed",
                agent_id=agent_id,
                run_id=run_id,
                request_id=request_id,
                error_type=type(e).__name__,
                error_message=str(e),
                latency_ms=latency_ms,
            )

            return AgentRunResponse(
                run_id=run_id,
                status=AgentRunStatus.FAILED,
                error=str(e),
                latency_ms=latency_ms,
            )

    # 异步模式：立即返回 run_id，后台执行
    else:
        from fastapi import BackgroundTasks
        import json

        # 将任务状态存储到 Redis
        redis_client = get_redis()
        await redis_client.hset(f"run:{run_id}", mapping={
            "status": "pending",
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request_id": request_id,
            "task": request.task[:500],  # 截断长任务描述
        })
        await redis_client.expire(f"run:{run_id}", 86400)  # 24小时过期

        logger.info(
            "agent_run_queued",
            agent_id=agent_id,
            run_id=run_id,
            request_id=request_id,
            callback_url=request.callback_url,
        )

        return AgentRunResponse(
            run_id=run_id,
            status=AgentRunStatus.PENDING,
            message="任务已排队，请通过状态查询 API 获取进度",
        )


async def _execute_agent_background(
    run_id: str,
    agent_id: str,
    initial_state: dict,
    graph_config: dict,
    callback_url: str | None,
):
    """后台执行 Agent 任务

    Args:
        run_id: 运行 ID
        agent_id: Agent ID
        initial_state: 初始状态
        graph_config: 图配置
        callback_url: 回调 URL
    """
    import httpx
    from datetime import datetime

    redis_client = get_redis()

    try:
        # 更新状态为 running
        await redis_client.hset(f"run:{run_id}", mapping={
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
        })

        # 执行 Agent
        graph = get_agent_graph()
        result = await graph.invoke(initial_state, config=graph_config)

        # 更新状态为 completed
        await redis_client.hset(f"run:{run_id}", mapping={
            "status": "completed",
            "output": result.get("output", ""),
            "step_count": str(result.get("step_count", 0)),
            "completed_at": datetime.utcnow().isoformat(),
        })

        logger.info(
            "agent_background_completed",
            run_id=run_id,
            agent_id=agent_id,
            step_count=result.get("step_count", 0),
        )

        # 回调通知
        if callback_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(callback_url, json={
                        "run_id": run_id,
                        "status": "completed",
                        "output": result.get("output", ""),
                    })
            except Exception as e:
                logger.warning(
                    "callback_failed",
                    run_id=run_id,
                    callback_url=callback_url,
                    error=str(e),
                )

    except Exception as e:
        # 更新状态为 failed
        await redis_client.hset(f"run:{run_id}", mapping={
            "status": "failed",
            "error": str(e)[:500],
            "failed_at": datetime.utcnow().isoformat(),
        })

        logger.error(
            "agent_background_failed",
            run_id=run_id,
            agent_id=agent_id,
            error=str(e),
        )

        # 回调通知失败
        if callback_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(callback_url, json={
                        "run_id": run_id,
                        "status": "failed",
                        "error": str(e),
                    })
            except Exception as callback_error:
                logger.warning(
                    "callback_failed",
                    run_id=run_id,
                    callback_url=callback_url,
                    error=str(callback_error),
                )


@router.get("/runs/{run_id}", response_model=AgentStatus)
async def get_run_status(run_id: str, req: Request):
    """查询运行状态

    获取 Agent 执行的当前状态和进度。

    Args:
        run_id: 运行唯一标识

    Returns:
        AgentStatus 状态信息
            - run_id: 运行 ID
            - status: 当前状态
            - step_count: 已执行步数
            - current_step: 当前步骤描述
            - progress: 进度百分比
    """
    request_id = get_request_id()

    logger.debug(
        "run_status_queried",
        run_id=run_id,
        request_id=request_id,
    )

    # 从 Redis 获取运行状态
    redis_client = get_redis()
    run_data = await redis_client.hgetall(f"run:{run_id}")

    if not run_data:
        raise HTTPException(
            status_code=404,
            detail=f"运行任务 {run_id} 不存在或已过期",
        )

    # 解析状态
    status_str = run_data.get("status", "pending")
    status = AgentRunStatus(status_str)
    step_count = int(run_data.get("step_count", 0))
    error = run_data.get("error")

    # 计算进度
    max_steps = config.max_agent_steps
    progress = min(int(step_count / max_steps * 100), 100)

    # 构建当前步骤描述
    current_step = ""
    if status == AgentRunStatus.PENDING:
        current_step = "任务排队等待执行"
        progress = 0
    elif status == AgentRunStatus.RUNNING:
        current_step = f"正在执行第 {step_count + 1} 步"
    elif status == AgentRunStatus.COMPLETED:
        current_step = "任务已完成"
        progress = 100
    elif status == AgentRunStatus.FAILED:
        current_step = f"任务执行失败: {error}"
        progress = 0

    return AgentStatus(
        run_id=run_id,
        status=status,
        step_count=step_count,
        current_step=current_step,
        progress=progress,
        message=error if status == AgentRunStatus.FAILED else None,
    )


@router.post("/runs/{run_id}/cancel", response_model=AgentCancelResponse)
async def cancel_run(run_id: str, req: Request):
    """取消运行

    设置取消标志，等待 Agent 在检查点停止。

    Args:
        run_id: 运行唯一标识

    Returns:
        AgentCancelResponse 取消结果

    Note:
        取消不是立即生效的，Agent 会在下一个检查点停止。
        通常在 1-5 秒内完成。
    """
    request_id = get_request_id()

    logger.info(
        "run_cancel_requested",
        run_id=run_id,
        request_id=request_id,
    )

    # TODO: 实现取消逻辑
    # 1. 在 Redis 中设置取消标志
    # 2. Agent 在每个节点检查取消标志
    # 3. 发现取消标志后优雅停止

    return AgentCancelResponse(
        run_id=run_id,
        status=AgentRunStatus.CANCELLED,
        message="取消请求已发送，Agent 将在下一个检查点停止",
    )