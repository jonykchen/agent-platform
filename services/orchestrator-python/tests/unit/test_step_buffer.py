"""Step 批量写入缓冲区测试"""

import asyncio

import pytest

from app.core.step_buffer import StepBuffer, StepRecord


class MockConnectionPool:
    """Mock 数据库连接池"""

    def __init__(self):
        self.written_records = []
        self.write_calls = 0

    def connection(self):
        return MockConnection(self)


class MockConnection:
    """Mock 数据库连接"""

    def __init__(self, pool):
        self.pool = pool

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def cursor(self):
        return MockCursor(self.pool)


class MockCursor:
    """Mock 数据库游标"""

    def __init__(self, pool):
        self.pool = pool

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def executemany(self, query, values_list):
        self.pool.write_calls += 1
        self.pool.written_records.extend(values_list)


@pytest.fixture
def mock_pool():
    return MockConnectionPool()


@pytest.fixture
async def step_buffer(mock_pool):
    buffer = StepBuffer(mock_pool, batch_size=3, flush_interval_ms=100)
    await buffer.start()
    yield buffer
    await buffer.stop()


class TestStepBuffer:
    """StepBuffer 测试"""

    def test_step_record_creation(self):
        """测试步骤记录创建"""
        step = StepRecord(
            run_id="run_001",
            tenant_id="tenant_001",
            step_order=1,
            step_type="thinking",
            content="Test content",
        )

        assert step.run_id == "run_001"
        assert step.tenant_id == "tenant_001"
        assert step.step_order == 1
        assert step.step_type == "thinking"
        assert step.content == "Test content"

    @pytest.mark.asyncio
    async def test_add_and_flush(self, step_buffer, mock_pool):
        """测试添加和刷新"""
        step = StepRecord(
            run_id="run_001",
            tenant_id="tenant_001",
            step_order=1,
            step_type="thinking",
            content="Test",
        )

        await step_buffer.add_step(step)
        await step_buffer._flush_all()

        assert mock_pool.write_calls >= 1
        assert len(mock_pool.written_records) == 1

    @pytest.mark.asyncio
    async def test_batch_write(self, mock_pool):
        """测试批量写入"""
        buffer = StepBuffer(mock_pool, batch_size=5, flush_interval_ms=1000)
        await buffer.start()

        try:
            # 添加 10 条记录
            for i in range(10):
                step = StepRecord(
                    run_id=f"run_{i // 5}",
                    tenant_id="tenant_001",
                    step_order=i,
                    step_type="thinking",
                    content=f"Content {i}",
                )
                await buffer.add_step(step)

            # 手动刷新
            await buffer._flush_all()

            assert len(mock_pool.written_records) == 10
        finally:
            await buffer.stop()

    @pytest.mark.asyncio
    async def test_nowait_add(self, step_buffer):
        """测试非阻塞添加"""
        step = StepRecord(
            run_id="run_001",
            tenant_id="tenant_001",
            step_order=1,
            step_type="thinking",
            content="Test",
        )

        result = await step_buffer.add_step_nowait(step)
        assert result is True

    @pytest.mark.asyncio
    async def test_stats(self, step_buffer, mock_pool):
        """测试统计信息"""
        for i in range(3):
            step = StepRecord(
                run_id="run_001",
                tenant_id="tenant_001",
                step_order=i,
                step_type="thinking",
                content=f"Content {i}",
            )
            await step_buffer.add_step(step)

        await step_buffer._flush_all()

        stats = step_buffer.stats
        assert stats["total_added"] == 3
        assert stats["total_flushed"] == 3
        assert stats["batch_count"] >= 1
