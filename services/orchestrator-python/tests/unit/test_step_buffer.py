"""Step 批量写入缓冲区测试"""

import asyncio
import os
import tempfile

import pytest

from app.core.step_buffer import (
    StepBuffer,
    StepRecord,
    WALEntry,
    _write_to_wal,
    _read_wal,
    _clear_wal_entries,
    _cleanup_expired_wal,
)


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


class TestWALEntry:
    """WALEntry 测试"""

    def test_wal_entry_creation(self):
        """测试 WAL 条目创建"""
        entry = WALEntry(
            timestamp="2024-01-01T00:00:00Z",
            run_id="run_001",
            step={"run_id": "run_001", "content": "test"},
        )

        assert entry.timestamp == "2024-01-01T00:00:00Z"
        assert entry.run_id == "run_001"
        assert entry.step["content"] == "test"

    def test_wal_entry_json_line(self):
        """测试 WAL 条目 JSON 行格式"""
        entry = WALEntry(
            timestamp="2024-01-01T00:00:00Z",
            run_id="run_001",
            step={"run_id": "run_001", "content": "test"},
        )

        json_line = entry.to_json_line()
        assert json_line.endswith("\n")
        assert '"timestamp"' in json_line
        assert '"run_id"' in json_line

    def test_wal_entry_from_json_line(self):
        """测试从 JSON 行解析 WAL 条目"""
        line = '{"timestamp": "2024-01-01T00:00:00Z", "run_id": "run_001", "step": {"content": "test"}}'

        entry = WALEntry.from_json_line(line)
        assert entry is not None
        assert entry.timestamp == "2024-01-01T00:00:00Z"
        assert entry.run_id == "run_001"
        assert entry.step["content"] == "test"

    def test_wal_entry_from_invalid_json(self):
        """测试从无效 JSON 解析"""
        entry = WALEntry.from_json_line("invalid json")
        assert entry is None


class TestWALFunctions:
    """WAL 函数测试"""

    @pytest.fixture(autouse=True)
    def setup_temp_wal(self, tmp_path, monkeypatch):
        """使用临时 WAL 文件"""
        self.temp_wal_file = str(tmp_path / "test_wal.log")
        monkeypatch.setattr("app.core.step_buffer.WAL_FILE", self.temp_wal_file)

    def test_write_to_wal(self):
        """测试写入 WAL"""
        steps = [
            StepRecord(
                run_id="run_001",
                tenant_id="tenant_001",
                step_order=1,
                step_type="thinking",
                content="Test content",
            ),
            StepRecord(
                run_id="run_002",
                tenant_id="tenant_001",
                step_order=1,
                step_type="thinking",
                content="Another content",
            ),
        ]

        _write_to_wal(steps)

        assert os.path.exists(self.temp_wal_file)
        entries = _read_wal()
        assert len(entries) == 2

    def test_read_wal_empty_file(self):
        """测试读取空 WAL 文件"""
        entries = _read_wal()
        assert entries == []

    def test_clear_wal_entries(self):
        """测试清理 WAL 条目"""
        steps = [
            StepRecord(
                run_id="run_001",
                tenant_id="tenant_001",
                step_order=1,
                step_type="thinking",
                content="Test",
            ),
            StepRecord(
                run_id="run_002",
                tenant_id="tenant_001",
                step_order=2,
                step_type="thinking",
                content="Test 2",
            ),
        ]

        _write_to_wal(steps)
        _clear_wal_entries({"run_001"})

        entries = _read_wal()
        assert len(entries) == 1
        assert entries[0].run_id == "run_002"

    def test_clear_all_wal_entries(self):
        """测试清理所有 WAL 条目（文件应被删除）"""
        steps = [
            StepRecord(
                run_id="run_001",
                tenant_id="tenant_001",
                step_order=1,
                step_type="thinking",
                content="Test",
            ),
        ]

        _write_to_wal(steps)
        _clear_wal_entries({"run_001"})

        assert not os.path.exists(self.temp_wal_file)


class TestWALRecovery:
    """WAL 恢复测试"""

    @pytest.fixture(autouse=True)
    def setup_temp_wal(self, tmp_path, monkeypatch):
        """使用临时 WAL 文件"""
        self.temp_wal_file = str(tmp_path / "test_wal.log")
        monkeypatch.setattr("app.core.step_buffer.WAL_FILE", self.temp_wal_file)

    @pytest.mark.asyncio
    async def test_recover_from_wal_on_start(self):
        """测试启动时自动恢复 WAL"""
        # 先写入一些 WAL 数据
        steps = [
            StepRecord(
                run_id="run_001",
                tenant_id="tenant_001",
                step_order=1,
                step_type="thinking",
                content="Recovered content",
            ),
        ]
        _write_to_wal(steps)

        # 创建 buffer 并启动
        mock_pool = MockConnectionPool()
        buffer = StepBuffer(mock_pool, batch_size=10, flush_interval_ms=1000)
        await buffer.start()

        try:
            # 检查恢复统计
            stats = buffer.stats
            assert stats["wal_recovered"] >= 1
        finally:
            await buffer.stop()

    @pytest.mark.asyncio
    async def test_wal_protected_on_write_failure(self):
        """测试写入失败时 WAL 保护"""
        mock_pool = FailingMockConnectionPool()
        buffer = StepBuffer(mock_pool, batch_size=1, flush_interval_ms=1000)
        await buffer.start()

        try:
            step = StepRecord(
                run_id="run_fail",
                tenant_id="tenant_001",
                step_order=1,
                step_type="thinking",
                content="Should be in WAL",
            )
            await buffer.add_step(step)
            await buffer._flush_all()

            # 写入失败，但 WAL 应该存在
            entries = _read_wal()
            assert any(e.run_id == "run_fail" for e in entries)
        finally:
            await buffer.stop()


class FailingMockConnectionPool:
    """模拟写入失败的连接池"""

    def connection(self):
        return FailingMockConnection()


class FailingMockConnection:
    """模拟写入失败的连接"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def cursor(self):
        return FailingMockCursor()


class FailingMockCursor:
    """模拟写入失败的游标"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def executemany(self, query, values_list):
        raise Exception("Simulated database failure")
