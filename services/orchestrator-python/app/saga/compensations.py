"""Saga 补偿动作注册表

每个工具调用可注册对应的补偿动作。
补偿动作在 Saga 回滚时按逆序执行。

使用示例：
    from app.saga.compensations import CompensationRegistry

    registry = CompensationRegistry()
    registry.register("execute_payment", refund_payment)
    registry.register("create_order", cancel_order)

    # 执行补偿
    await registry.compensate("execute_payment", context)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog

logger = structlog.get_logger()


class CompensationRegistry:
    """补偿动作注册表

    管理工具补偿动作的注册和执行。
    补偿动作在 Saga 回滚时按逆序执行。

    Attributes:
        _compensations: 补偿动作映射表
    """

    def __init__(self) -> None:
        """初始化补偿注册表"""
        self._compensations: dict[str, Callable[[dict[str, Any]], Awaitable[None]]] = {}

    def register(
        self,
        tool_name: str,
        compensation: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """注册补偿动作

        Args:
            tool_name: 工具名称
            compensation: 补偿函数，接收工具执行上下文，返回 None
        """
        if tool_name in self._compensations:
            logger.warning(
                "Overwriting existing compensation",
                tool_name=tool_name,
            )
        self._compensations[tool_name] = compensation
        logger.info("Compensation registered", tool_name=tool_name)

    def unregister(self, tool_name: str) -> None:
        """取消注册补偿动作

        Args:
            tool_name: 工具名称
        """
        if tool_name in self._compensations:
            del self._compensations[tool_name]
            logger.info("Compensation unregistered", tool_name=tool_name)

    def has_compensation(self, tool_name: str) -> bool:
        """检查是否已注册补偿动作

        Args:
            tool_name: 工具名称

        Returns:
            是否已注册
        """
        return tool_name in self._compensations

    async def compensate(self, tool_name: str, context: dict[str, Any]) -> None:
        """执行补偿动作

        Args:
            tool_name: 工具名称
            context: 工具执行上下文（包含 input、output、metadata）

        Raises:
            Exception: 补偿失败时抛出异常
        """
        compensation = self._compensations.get(tool_name)
        if compensation is None:
            logger.warning(
                "No compensation registered",
                tool_name=tool_name,
            )
            return

        try:
            await compensation(context)
            logger.info(
                "Compensation succeeded",
                tool_name=tool_name,
            )
        except Exception as e:
            logger.error(
                "Compensation failed",
                tool_name=tool_name,
                error=str(e),
            )
            # 补偿失败：记录到 Saga 状态，等待人工干预
            raise

    def get_registered_tools(self) -> list[str]:
        """获取所有已注册补偿的工具名称

        Returns:
            工具名称列表
        """
        return list(self._compensations.keys())

    def clear(self) -> None:
        """清空所有注册的补偿动作"""
        self._compensations.clear()
        logger.info("All compensations cleared")


# ====== 全局补偿注册表 ======
registry = CompensationRegistry()


# ====== 补偿动作实现示例 ======


async def refund_payment(context: dict[str, Any]) -> None:
    """支付退款补偿

    调用 ToolBus 的 refund_payment 工具，
    将已支付的金额退回原账户。

    Args:
        context: 工具执行上下文，包含：
            - output.payment_id: 支付 ID
            - output.amount: 退款金额
    """
    from app.tools.tool_bus_client import get_tool_bus_client

    client = get_tool_bus_client()
    payment_id = context.get("output", {}).get("payment_id")
    amount = context.get("output", {}).get("amount")

    if not payment_id:
        logger.error("Cannot refund: missing payment_id", context=context)
        return

    await client.execute_tool(
        tool_name="refund_payment",
        parameters={
            "payment_id": payment_id,
            "amount": amount,
            "reason": "saga_compensation",
        },
    )


async def cancel_order(context: dict[str, Any]) -> None:
    """取消订单补偿

    Args:
        context: 工具执行上下文，包含：
            - output.order_id: 订单 ID
    """
    from app.tools.tool_bus_client import get_tool_bus_client

    client = get_tool_bus_client()
    order_id = context.get("output", {}).get("order_id")

    if not order_id:
        logger.error("Cannot cancel order: missing order_id", context=context)
        return

    await client.execute_tool(
        tool_name="cancel_order",
        parameters={
            "order_id": order_id,
            "reason": "saga_compensation",
        },
    )


async def cancel_payment(context: dict[str, Any]) -> None:
    """取消支付补偿（支付尚未完成时）

    Args:
        context: 工具执行上下文，包含：
            - output.payment_id: 支付 ID
    """
    from app.tools.tool_bus_client import get_tool_bus_client

    client = get_tool_bus_client()
    payment_id = context.get("output", {}).get("payment_id")

    if not payment_id:
        return

    await client.execute_tool(
        tool_name="cancel_payment",
        parameters={
            "payment_id": payment_id,
            "reason": "saga_compensation",
        },
    )


async def release_stock(context: dict[str, Any]) -> None:
    """释放库存预留补偿

    Args:
        context: 工具执行上下文，包含：
            - output.reservation_id: 预留 ID
    """
    from app.tools.tool_bus_client import get_tool_bus_client

    client = get_tool_bus_client()
    reservation_id = context.get("output", {}).get("reservation_id")

    if not reservation_id:
        return

    await client.execute_tool(
        tool_name="release_stock_reservation",
        parameters={"reservation_id": reservation_id},
    )


# ====== 注册补偿动作 ======
registry.register("execute_payment", refund_payment)
registry.register("create_order", cancel_order)
registry.register("reserve_stock", release_stock)
