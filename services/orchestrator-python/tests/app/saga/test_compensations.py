"""Saga 补偿动作注册表测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.saga.compensations import CompensationRegistry


@pytest.fixture
def registry() -> CompensationRegistry:
    """创建测试用补偿注册表"""
    return CompensationRegistry()


@pytest.fixture
def mock_compensation() -> AsyncMock:
    """创建模拟补偿函数"""
    return AsyncMock()


class TestCompensationRegistry:
    """CompensationRegistry 测试"""

    def test_should_register_compensation(self, registry: CompensationRegistry, mock_compensation: AsyncMock):
        """应该正确注册补偿动作"""
        registry.register("tool_a", mock_compensation)

        assert registry.has_compensation("tool_a") is True

    def test_should_unregister_compensation(self, registry: CompensationRegistry, mock_compensation: AsyncMock):
        """应该正确取消注册补偿动作"""
        registry.register("tool_a", mock_compensation)
        registry.unregister("tool_a")

        assert registry.has_compensation("tool_a") is False

    def test_should_not_raise_when_unregister_nonexistent(self, registry: CompensationRegistry):
        """取消注册不存在的补偿动作不应该抛出异常"""
        registry.unregister("nonexistent")

    def test_should_overwrite_existing_compensation(self, registry: CompensationRegistry):
        """应该覆盖已存在的补偿动作"""
        compensation1 = AsyncMock()
        compensation2 = AsyncMock()

        registry.register("tool_a", compensation1)
        registry.register("tool_a", compensation2)

        assert registry.has_compensation("tool_a") is True

    def test_should_check_compensation_exists(self, registry: CompensationRegistry, mock_compensation: AsyncMock):
        """应该正确检查补偿动作是否存在"""
        registry.register("tool_a", mock_compensation)

        assert registry.has_compensation("tool_a") is True
        assert registry.has_compensation("tool_b") is False

    @pytest.mark.asyncio
    async def test_should_execute_compensation(self, registry: CompensationRegistry, mock_compensation: AsyncMock):
        """应该正确执行补偿动作"""
        registry.register("tool_a", mock_compensation)
        context = {"output": {"id": "123"}}

        await registry.compensate("tool_a", context)

        mock_compensation.assert_called_once_with(context)

    @pytest.mark.asyncio
    async def test_should_not_raise_when_no_compensation_registered(self, registry: CompensationRegistry):
        """没有注册补偿动作时不应该抛出异常"""
        context = {"output": {"id": "123"}}

        # 应该正常返回，不抛出异常
        await registry.compensate("nonexistent", context)

    @pytest.mark.asyncio
    async def test_should_raise_when_compensation_fails(self, registry: CompensationRegistry):
        """补偿动作失败时应该抛出异常"""
        failing_compensation = AsyncMock(side_effect=Exception("Compensation failed"))
        registry.register("tool_a", failing_compensation)
        context = {"output": {"id": "123"}}

        with pytest.raises(Exception, match="Compensation failed"):
            await registry.compensate("tool_a", context)

    def test_should_get_registered_tools(self, registry: CompensationRegistry, mock_compensation: AsyncMock):
        """应该正确获取所有已注册的工具名称"""
        registry.register("tool_a", mock_compensation)
        registry.register("tool_b", mock_compensation)
        registry.register("tool_c", mock_compensation)

        tools = registry.get_registered_tools()

        assert len(tools) == 3
        assert "tool_a" in tools
        assert "tool_b" in tools
        assert "tool_c" in tools

    def test_should_clear_all_compensations(self, registry: CompensationRegistry, mock_compensation: AsyncMock):
        """应该正确清空所有补偿动作"""
        registry.register("tool_a", mock_compensation)
        registry.register("tool_b", mock_compensation)

        registry.clear()

        assert registry.has_compensation("tool_a") is False
        assert registry.has_compensation("tool_b") is False
        assert len(registry.get_registered_tools()) == 0

    def test_should_return_empty_list_when_no_compensations(self, registry: CompensationRegistry):
        """没有补偿动作时应该返回空列表"""
        assert registry.get_registered_tools() == []


class TestCompensationActions:
    """补偿动作实现测试"""

    @pytest.mark.asyncio
    @patch("app.saga.compensations.get_tool_bus_client")
    async def test_refund_payment_should_call_tool_bus(self, mock_get_client: MagicMock):
        """refund_payment 应该调用 ToolBus"""
        from app.saga.compensations import refund_payment

        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        context = {"output": {"payment_id": "pay-123", "amount": 100.0}}

        await refund_payment(context)

        mock_client.execute_tool.assert_called_once_with(
            tool_name="refund_payment",
            parameters={
                "payment_id": "pay-123",
                "amount": 100.0,
                "reason": "saga_compensation",
            },
        )

    @pytest.mark.asyncio
    async def test_refund_payment_should_skip_when_no_payment_id(self, registry: CompensationRegistry):
        """没有 payment_id 时应该跳过"""
        from app.saga.compensations import refund_payment

        context = {"output": {}}

        # 不应该抛出异常
        await refund_payment(context)

    @pytest.mark.asyncio
    @patch("app.saga.compensations.get_tool_bus_client")
    async def test_cancel_order_should_call_tool_bus(self, mock_get_client: MagicMock):
        """cancel_order 应该调用 ToolBus"""
        from app.saga.compensations import cancel_order

        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        context = {"output": {"order_id": "order-123"}}

        await cancel_order(context)

        mock_client.execute_tool.assert_called_once_with(
            tool_name="cancel_order",
            parameters={
                "order_id": "order-123",
                "reason": "saga_compensation",
            },
        )

    @pytest.mark.asyncio
    async def test_cancel_order_should_skip_when_no_order_id(self, registry: CompensationRegistry):
        """没有 order_id 时应该跳过"""
        from app.saga.compensations import cancel_order

        context = {"output": {}}

        # 不应该抛出异常
        await cancel_order(context)

    @pytest.mark.asyncio
    @patch("app.saga.compensations.get_tool_bus_client")
    async def test_cancel_payment_should_call_tool_bus(self, mock_get_client: MagicMock):
        """cancel_payment 应该调用 ToolBus"""
        from app.saga.compensations import cancel_payment

        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        context = {"output": {"payment_id": "pay-123"}}

        await cancel_payment(context)

        mock_client.execute_tool.assert_called_once_with(
            tool_name="cancel_payment",
            parameters={
                "payment_id": "pay-123",
                "reason": "saga_compensation",
            },
        )

    @pytest.mark.asyncio
    async def test_cancel_payment_should_skip_when_no_payment_id(self, registry: CompensationRegistry):
        """没有 payment_id 时应该跳过"""
        from app.saga.compensations import cancel_payment

        context = {"output": {}}

        # 不应该抛出异常
        await cancel_payment(context)

    @pytest.mark.asyncio
    @patch("app.saga.compensations.get_tool_bus_client")
    async def test_release_stock_should_call_tool_bus(self, mock_get_client: MagicMock):
        """release_stock 应该调用 ToolBus"""
        from app.saga.compensations import release_stock

        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        context = {"output": {"reservation_id": "res-123"}}

        await release_stock(context)

        mock_client.execute_tool.assert_called_once_with(
            tool_name="release_stock_reservation",
            parameters={"reservation_id": "res-123"},
        )

    @pytest.mark.asyncio
    async def test_release_stock_should_skip_when_no_reservation_id(self, registry: CompensationRegistry):
        """没有 reservation_id 时应该跳过"""
        from app.saga.compensations import release_stock

        context = {"output": {}}

        # 不应该抛出异常
        await release_stock(context)
