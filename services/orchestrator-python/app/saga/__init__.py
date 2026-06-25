"""Saga 分布式事务模块

本模块实现了基于 LangGraph 的 Saga 编排模式，用于处理跨服务分布式事务。

核心组件：
- SagaStatus: Saga 状态枚举
- SagaStep: Saga 步骤记录
- SagaState: Saga 状态定义
- CompensationRegistry: 补偿动作注册表

使用示例：
    from app.saga import CompensationRegistry, SagaStatus

    # 注册补偿动作
    registry = CompensationRegistry()
    registry.register("execute_payment", refund_payment)

    # 执行补偿
    await registry.compensate("execute_payment", context)
"""

from .compensations import CompensationRegistry, registry
from .state import SagaState, SagaStatus, SagaStep

__all__ = [
    "CompensationRegistry",
    "registry",
    "SagaState",
    "SagaStatus",
    "SagaStep",
]
