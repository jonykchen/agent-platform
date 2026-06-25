"""Saga 状态定义与持久化

扩展 LangGraph AgentState，增加 Saga 相关字段。
Saga 状态随 Checkpoint 一起持久化到 Redis。

使用示例：
    from app.saga.state import SagaState, SagaStatus, SagaStep

    # 创建 Saga 状态
    saga_state = SagaState(
        saga_id="saga-123",
        run_id="run-456",
        status=SagaStatus.RUNNING,
    )

    # 添加步骤
    step = SagaStep(
        step_index=0,
        tool_name="execute_payment",
        status="executing",
    )
    saga_state.steps.append(step)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class SagaStatus(str, Enum):
    """Saga 状态枚举"""

    RUNNING = "running"  # 执行中
    COMPENSATING = "compensating"  # 补偿中（回滚）
    COMPLETED = "completed"  # 成功完成
    FAILED = "failed"  # 执行失败
    COMPENSATION_FAILED = "compensation_failed"  # 补偿失败（需人工干预）

    def is_terminal(self) -> bool:
        """判断是否为终态"""
        return self in {
            SagaStatus.COMPLETED,
            SagaStatus.FAILED,
            SagaStatus.COMPENSATION_FAILED,
        }

    def can_transition_to(self, new_status: SagaStatus) -> bool:
        """判断是否可以转换到新状态"""
        transitions = {
            SagaStatus.RUNNING: {
                SagaStatus.COMPENSATING,
                SagaStatus.COMPLETED,
                SagaStatus.FAILED,
            },
            SagaStatus.COMPENSATING: {
                SagaStatus.COMPLETED,
                SagaStatus.COMPENSATION_FAILED,
            },
            SagaStatus.COMPLETED: set(),
            SagaStatus.FAILED: set(),
            SagaStatus.COMPENSATION_FAILED: set(),
        }
        return new_status in transitions.get(self, set())


@dataclass
class SagaStep:
    """Saga 步骤记录

    记录每个工具调用的执行状态和结果，用于补偿时回溯。
    """

    step_index: int  # 步骤序号
    tool_name: str  # 工具名称
    status: str  # pending / executing / completed / failed / compensating / compensated
    input_data: dict = field(default_factory=dict)  # 工具输入
    output_data: dict = field(default_factory=dict)  # 工具输出
    error: str | None = None  # 错误信息
    started_at: float | None = None  # 开始时间戳
    completed_at: float | None = None  # 完成时间戳
    compensation_status: str | None = None  # 补偿状态
    compensation_error: str | None = None  # 补偿错误信息

    def is_completed(self) -> bool:
        """判断步骤是否已完成"""
        return self.status == "completed"

    def is_failed(self) -> bool:
        """判断步骤是否失败"""
        return self.status == "failed"

    def needs_compensation(self) -> bool:
        """判断是否需要补偿"""
        return self.status == "completed" and self.compensation_status is None

    def mark_compensating(self) -> None:
        """标记为补偿中"""
        self.compensation_status = "compensating"

    def mark_compensated(self) -> None:
        """标记为已补偿"""
        self.compensation_status = "compensated"

    def mark_compensation_failed(self, error: str) -> None:
        """标记补偿失败"""
        self.compensation_status = "failed"
        self.compensation_error = error


@dataclass
class SagaState:
    """Saga 状态定义

    包含 Saga 执行的所有状态信息，随 LangGraph Checkpoint 一起持久化。

    Attributes:
        saga_id: Saga 唯一标识
        run_id: 关联的 Agent Run ID
        status: 当前状态
        steps: 已执行的步骤列表
        current_step_index: 当前执行到的步骤索引
        error: 错误信息（失败时）
        metadata: 附加元数据
        created_at: 创建时间戳
        updated_at: 最后更新时间戳
    """

    saga_id: str
    run_id: str
    status: SagaStatus = SagaStatus.RUNNING
    steps: list[SagaStep] = field(default_factory=list)
    current_step_index: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float | None = None
    updated_at: float | None = None

    def add_step(self, tool_name: str, input_data: dict) -> SagaStep:
        """添加新步骤

        Args:
            tool_name: 工具名称
            input_data: 工具输入

        Returns:
            新创建的步骤
        """
        step = SagaStep(
            step_index=len(self.steps),
            tool_name=tool_name,
            status="pending",
            input_data=input_data,
        )
        self.steps.append(step)
        self.current_step_index = step.step_index
        logger.info(
            "Saga step added",
            saga_id=self.saga_id,
            step_index=step.step_index,
            tool_name=tool_name,
        )
        return step

    def get_current_step(self) -> SagaStep | None:
        """获取当前步骤"""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def get_completed_steps(self) -> list[SagaStep]:
        """获取所有已完成的步骤"""
        return [step for step in self.steps if step.is_completed()]

    def get_steps_needing_compensation(self) -> list[SagaStep]:
        """获取需要补偿的步骤（逆序）"""
        return [step for step in reversed(self.steps) if step.needs_compensation()]

    def transition_to(self, new_status: SagaStatus) -> None:
        """转换状态

        Args:
            new_status: 新状态

        Raises:
            ValueError: 如果状态转换不合法
        """
        if not self.status.can_transition_to(new_status):
            raise ValueError(f"Invalid state transition: {self.status} -> {new_status}")
        logger.info(
            "Saga state transition",
            saga_id=self.saga_id,
            old_status=self.status,
            new_status=new_status,
        )
        self.status = new_status

    def mark_failed(self, error: str) -> None:
        """标记失败

        Args:
            error: 错误信息
        """
        self.error = error
        self.transition_to(SagaStatus.FAILED)

    def mark_compensating(self) -> None:
        """开始补偿"""
        self.transition_to(SagaStatus.COMPENSATING)

    def mark_completed(self) -> None:
        """标记完成"""
        self.transition_to(SagaStatus.COMPLETED)

    def mark_compensation_failed(self, error: str) -> None:
        """标记补偿失败

        Args:
            error: 补偿失败信息
        """
        self.error = error
        self.transition_to(SagaStatus.COMPENSATION_FAILED)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "saga_id": self.saga_id,
            "run_id": self.run_id,
            "status": self.status.value,
            "steps": [
                {
                    "step_index": step.step_index,
                    "tool_name": step.tool_name,
                    "status": step.status,
                    "input_data": step.input_data,
                    "output_data": step.output_data,
                    "error": step.error,
                    "started_at": step.started_at,
                    "completed_at": step.completed_at,
                    "compensation_status": step.compensation_status,
                    "compensation_error": step.compensation_error,
                }
                for step in self.steps
            ],
            "current_step_index": self.current_step_index,
            "error": self.error,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SagaState:
        """从字典反序列化"""
        steps = [
            SagaStep(
                step_index=step_data["step_index"],
                tool_name=step_data["tool_name"],
                status=step_data["status"],
                input_data=step_data.get("input_data", {}),
                output_data=step_data.get("output_data", {}),
                error=step_data.get("error"),
                started_at=step_data.get("started_at"),
                completed_at=step_data.get("completed_at"),
                compensation_status=step_data.get("compensation_status"),
                compensation_error=step_data.get("compensation_error"),
            )
            for step_data in data.get("steps", [])
        ]
        return cls(
            saga_id=data["saga_id"],
            run_id=data["run_id"],
            status=SagaStatus(data["status"]),
            steps=steps,
            current_step_index=data.get("current_step_index", 0),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
