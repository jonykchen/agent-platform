"""Agent 运行相关的 Pydantic 模型

定义 Agent 执行请求和状态查询的数据结构。

【核心概念】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Agent API 用于：
1. 启动 Agent 执行任务（AgentRunRequest）
2. 查询执行状态（AgentStatus）
3. 获取执行结果（AgentRunResponse）
4. 取消正在执行的任务

【执行模式】
- sync: 同步执行，等待完成后返回结果
- async: 异步执行，立即返回 run_id，通过轮询或回调获取结果

【状态流转】
pending -> running -> completed/failed/cancelled
              |
              +-> pending_approval -> approved/rejected -> running -> completed
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    """执行模式"""

    SYNC = "sync"  # 同步执行
    ASYNC = "async"  # 异步执行


class AgentRunStatus(str, Enum):
    """Agent 运行状态"""

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 正在执行
    PENDING_APPROVAL = "pending_approval"  # 等待审批
    APPROVED = "approved"  # 审批通过
    REJECTED = "rejected"  # 审批拒绝
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"  # 执行失败
    CANCELLED = "cancelled"  # 已取消


class AgentRunRequest(BaseModel):
    """Agent 运行请求

    启动 Agent 执行一个任务。

    Attributes:
        session_id: 关联的会话 ID
        task: 任务描述（自然语言）
        execution_mode: 执行模式（sync/async）
        agent_id: 指定 Agent 类型（可选）
        context: 上下文信息（可选）
        callback_url: 完成回调 URL（异步模式）

    Example:
        ```json
        {
            "session_id": "sess_abc123",
            "task": "帮我分析销售数据并生成报告",
            "execution_mode": "async",
            "callback_url": "https://example.com/webhook/agent-callback"
        }
        ```
    """

    session_id: str | None = Field(default=None, description="关联的会话 ID")
    task: str = Field(..., min_length=1, max_length=16000, description="任务描述")
    execution_mode: ExecutionMode = Field(default=ExecutionMode.SYNC, description="执行模式")
    agent_id: str | None = Field(default=None, description="指定 Agent 类型")
    context: dict | None = Field(default=None, description="上下文信息")
    callback_url: str | None = Field(default=None, description="完成回调 URL")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "sess_abc123",
                    "task": "帮我分析销售数据并生成报告",
                    "execution_mode": "async",
                    "callback_url": "https://example.com/webhook/agent-callback",
                }
            ]
        }
    }


class StepInfo(BaseModel):
    """执行步骤信息

    记录 Agent 执行的单个步骤。

    Attributes:
        step_number: 步骤序号
        node_name: 节点名称
        action: 执行动作
        input: 输入数据
        output: 输出数据
        status: 步骤状态
        started_at: 开始时间
        completed_at: 完成时间
    """

    step_number: int = Field(..., ge=0, description="步骤序号")
    node_name: str = Field(..., description="节点名称")
    action: str = Field(..., description="执行动作")
    input: dict | None = Field(default=None, description="输入数据")
    output: dict | None = Field(default=None, description="输出数据")
    status: str = Field(default="completed", description="步骤状态")
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")


class AgentRunResponse(BaseModel):
    """Agent 运行响应

    返回 Agent 执行结果。

    Attributes:
        run_id: 运行唯一标识
        status: 运行状态
        result: 执行结果（完成时填充）
        error: 错误信息（失败时填充）
        steps: 执行步骤列表
        model_used: 使用的模型
        total_tokens: 总 token 数
        latency_ms: 总耗时（毫秒）
        approval_id: 审批 ID（如需审批）
    """

    run_id: str = Field(..., description="运行 ID")
    status: AgentRunStatus = Field(..., description="运行状态")
    result: str | None = Field(default=None, description="执行结果")
    error: str | None = Field(default=None, description="错误信息")
    steps: list[StepInfo] | None = Field(default=None, description="执行步骤")
    model_used: str | None = Field(default=None, description="使用的模型")
    total_tokens: int = Field(default=0, ge=0, description="总 token 数")
    latency_ms: int = Field(default=0, ge=0, description="总耗时（毫秒）")
    approval_id: str | None = Field(default=None, description="审批 ID")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "run_id": "run_xyz789",
                    "status": "completed",
                    "result": "销售分析报告已生成，本月销售额同比增长 15%",
                    "total_tokens": 2500,
                    "latency_ms": 8500,
                }
            ]
        }
    }


class AgentStatus(BaseModel):
    """Agent 运行状态

    用于查询运行状态的响应。

    Attributes:
        run_id: 运行唯一标识
        status: 当前状态
        step_count: 已执行步数
        current_step: 当前步骤描述
        progress: 进度百分比（0-100）
        started_at: 开始时间
        estimated_completion: 预计完成时间
        message: 状态消息
    """

    run_id: str = Field(..., description="运行 ID")
    status: AgentRunStatus = Field(..., description="当前状态")
    step_count: int = Field(default=0, ge=0, description="已执行步数")
    current_step: str | None = Field(default=None, description="当前步骤描述")
    progress: int = Field(default=0, ge=0, le=100, description="进度百分比")
    started_at: datetime | None = Field(default=None, description="开始时间")
    estimated_completion: datetime | None = Field(default=None, description="预计完成时间")
    message: str | None = Field(default=None, description="状态消息")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "run_id": "run_xyz789",
                    "status": "running",
                    "step_count": 3,
                    "current_step": "正在调用工具 query_sales_data",
                    "progress": 45,
                    "message": "执行中",
                }
            ]
        }
    }


class AgentCancelResponse(BaseModel):
    """取消 Agent 运行的响应

    Attributes:
        run_id: 运行 ID
        status: 取消后的状态
        message: 操作结果消息
    """

    run_id: str = Field(..., description="运行 ID")
    status: AgentRunStatus = Field(default=AgentRunStatus.CANCELLED, description="取消后状态")
    message: str = Field(default="运行已取消", description="操作结果消息")

    model_config = {
        "json_schema_extra": {"examples": [{"run_id": "run_xyz789", "status": "cancelled", "message": "运行已取消"}]}
    }
