"""Step 批量写入缓冲区 (P-05)

实现内存攒批、定时刷新和优雅停机。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import structlog
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

logger = structlog.get_logger()


@dataclass
class StepRecord:
    """待写入的步骤记录"""

    run_id: str
    tenant_id: str
    step_order: int
    step_type: str
    content: str
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: dict | None = None
    thinking: str | None = None
    token_count: int = 0
    duration_ms: int | None = None
    metadata: dict = field(default_factory=dict)
    created_at: str | None = None


class StepBuffer:
    """Step 批量写入缓冲区

    特性：
    - 内存攒批：收集 N 条 step 后批量写入
    - 定时刷新：等待 T 毫秒后自动刷新
    - 背压控制：缓冲区满时阻塞
    - 优雅停机：刷新所有待写入数据

    使用方式:
        buffer = StepBuffer(db_pool, batch_size=50, flush_interval_ms=500)
        await buffer.start()
        await buffer.add_step(step_record)
        # ... 应用结束时
        await buffer.stop()
    """

    def __init__(
        self,
        db_pool: AsyncConnectionPool,
        batch_size: int = 50,
        flush_interval_ms: int = 500,
        max_buffer_size: int = 1000,
    ):
        self.db_pool = db_pool
        self.batch_size = batch_size
        self.flush_interval = flush_interval_ms / 1000
        self.max_buffer_size = max_buffer_size

        self._buffer: asyncio.Queue[StepRecord] = asyncio.Queue(maxsize=max_buffer_size)
        self._running = False
        self._flush_task: asyncio.Task | None = None
        self._stats = {"total_added": 0, "total_flushed": 0, "batch_count": 0}

    async def start(self) -> None:
        """启动后台刷新任务"""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "StepBuffer started",
            batch_size=self.batch_size,
            flush_interval_ms=self.flush_interval * 1000,
            max_buffer_size=self.max_buffer_size,
        )

    async def stop(self) -> None:
        """停止并刷新所有待写入数据"""
        if not self._running:
            return

        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # 最终刷新
        await self._flush_all()
        logger.info("StepBuffer stopped", stats=self._stats)

    async def add_step(self, step: StepRecord) -> None:
        """添加 step 到缓冲区

        如果缓冲区满，会阻塞等待。
        """
        await self._buffer.put(step)
        self._stats["total_added"] += 1

        # 如果达到批次大小，立即触发刷新
        if self._buffer.qsize() >= self.batch_size:
            asyncio.create_task(self._flush())

    async def add_step_nowait(self, step: StepRecord) -> bool:
        """非阻塞添加 step

        Returns:
            True 成功添加，False 缓冲区满
        """
        try:
            self._buffer.put_nowait(step)
            self._stats["total_added"] += 1
            return True
        except asyncio.QueueFull:
            return False

    async def _flush_loop(self) -> None:
        """后台定时刷新循环"""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Flush loop error", error=str(e))

    async def _flush(self) -> None:
        """刷新一批数据到数据库"""
        batch: list[StepRecord] = []

        while len(batch) < self.batch_size:
            try:
                step = self._buffer.get_nowait()
                batch.append(step)
            except asyncio.QueueEmpty:
                break

        if batch:
            await self._write_batch(batch)

    async def _flush_all(self) -> None:
        """刷新所有待写入数据"""
        batch: list[StepRecord] = []

        while True:
            try:
                step = self._buffer.get_nowait()
                batch.append(step)
            except asyncio.QueueEmpty:
                break

        if batch:
            await self._write_batch(batch)

    async def _write_batch(self, steps: list[StepRecord]) -> None:
        """批量写入数据库"""
        if not steps:
            return

        query = """
            INSERT INTO agent_step (
                id, run_id, tenant_id, step_order, step_type, content,
                tool_name, tool_input, tool_output, thinking,
                token_count, duration_ms, metadata, created_at
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        # 准备批量数据
        values_list = []
        for step in steps:
            values_list.append((
                step.run_id,
                step.tenant_id,
                step.step_order,
                step.step_type,
                step.content,
                step.tool_name,
                step.tool_input or {},
                step.tool_output or {},
                step.thinking,
                step.token_count,
                step.duration_ms,
                step.metadata or {},
                step.created_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ))

        try:
            async with self.db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(query, values_list)

            self._stats["total_flushed"] += len(steps)
            self._stats["batch_count"] += 1

            logger.debug(
                "Step batch written",
                batch_size=len(steps),
                total_flushed=self._stats["total_flushed"],
            )

        except Exception as e:
            logger.error("Failed to write step batch", error=str(e), batch_size=len(steps))
            # 不重试，丢弃数据（可根据需求改为重试或写入死信队列）

    @property
    def stats(self) -> dict:
        """获取统计信息"""
        return {
            **self._stats,
            "buffer_size": self._buffer.qsize(),
            "max_buffer_size": self.max_buffer_size,
        }

    @property
    def is_running(self) -> bool:
        return self._running
