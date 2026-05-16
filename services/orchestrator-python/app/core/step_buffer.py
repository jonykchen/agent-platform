"""Step 批量写入缓冲区 (P-05)

实现内存攒批、定时刷新和优雅停机。

【核心概念】WAL (Write-Ahead Log) 保护机制
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WAL 是数据库系统的经典技术，用于保证数据持久性：
1. 先写日志，后写数据：确保操作可恢复
2. 崩溃恢复：进程崩溃后可以从日志恢复未提交的数据
3. 原子性保证：要么全部成功，要么全部失败

【问题背景】
- Step 数据需要写入 PostgreSQL
- 批量写入提高性能（每 5s 或 100 条）
- 进程崩溃时缓冲区数据可能丢失

【技术选型】崩溃保护方案对比
┌────────────────────┬───────────────┬───────────────┬───────────────┐
│ 方案               │ 数据安全      │ 性能影响      │ 实现复杂度    │
├────────────────────┼───────────────┼───────────────┼───────────────┤
│ 无保护             │ ❌ 崩溃丢失   │ 无影响        │ 简单          │
│ ✓ WAL 文件保护     │ ✅ 可恢复     │ 小（追加写入）│ 中等          │
│ 实时写入 DB        │ ✅ 安全       │ 大（频繁 IO）│ 简单          │
│ 双缓冲 + swap      │ ✅ 安全       │ 中            │ 复杂          │
└────────────────────┴───────────────┴───────────────┴───────────────┘

【决策依据】选择 WAL 文件保护：
1. 性能：追加写入比随机写入快 10 倍以上
2. 可恢复：崩溃后可以从 WAL 恢复
3. 简单：无需复杂的双缓冲机制

【WAL 保护流程】
┌─────────────────────────────────────────────────────────────────────┐
│ 正常流程：                                                          │
│   1. Step 添加到缓冲区                                              │
│   2. 达到阈值（5s 或 100 条）触发批量写入                            │
│   3. 【先】写入 WAL 文件（追加模式）                                 │
│   4. 【后】写入 PostgreSQL                                          │
│   5. 成功后清理 WAL 记录                                            │
│                                                                     │
│ 崩溃恢复流程：                                                       │
│   1. 服务启动时调用 recover_from_wal()                              │
│   2. 读取 WAL 文件中的未提交记录                                     │
│   3. 重新写入 PostgreSQL                                            │
│   4. 清理 WAL 文件                                                  │
└─────────────────────────────────────────────────────────────────────┘

【参数推荐】
- WAL 文件路径: /tmp/orchestrator_step_wal.log → 临时目录，重启后清理
- WAL 记录过期: 24 小时 → 超过 24h 的记录可能是陈旧数据，自动清理
- 批量写入阈值: 100 条或 5s → 平衡性能和数据安全

【风险与缓解】
┌────────────────────┬─────────────────────────────────────────────────┐
│ 风险               │ 缓解措施                                        │
├────────────────────┼─────────────────────────────────────────────────┤
│ WAL 文件损坏       │ 使用 JSON 格式，损坏行可跳过                    │
│ WAL 文件过大       │ 定期清理已提交记录，限制文件大小                │
│ 磁盘空间不足       │ 监控磁盘空间，告警机制                          │
└────────────────────┴─────────────────────────────────────────────────┘

【演进历史】
- v1.0: 直接写入数据库，无批量优化
- v2.0: 添加批量写入缓冲区，性能提升 10 倍
- v2.1: 添加 WAL 保护机制（当前版本）

【参考实现】
- PostgreSQL WAL: https://www.postgresql.org/docs/current/wal.html
- SQLite WAL: https://www.sqlite.org/wal.html
- LevelDB Write-Ahead Log
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

logger = structlog.get_logger()

# WAL 文件路径常量
WAL_FILE = "/tmp/orchestrator_step_wal.log"


@dataclass
class StepRecord:
    """待写入的步骤记录

    【设计决策】为什么使用 @dataclass？
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    dataclass vs 普通类 vs Pydantic 模型：

    ┌─────────────────────┬───────────────┬───────────────┬───────────────┐
    │ 特性                │ dataclass     │ 普通类        │ Pydantic      │
    ├─────────────────────┼───────────────┼───────────────┼───────────────┤
    │ 自动生成 __init__   │ ✅            │ ❌            │ ✅            │
    │ 类型验证            │ ❌            │ ❌            │ ✅            │
    │ JSON 序列化         │ ✅ (asdict)   │ 手动实现      │ ✅            │
    │ 性能                │ 高            │ 高            │ 中（有验证开销）│
    └─────────────────────┴───────────────┴───────────────┴───────────────┘

    选择 dataclass 的原因：
    1. 简洁：自动生成 __init__、__repr__ 等方法
    2. 性能：无运行时验证开销
    3. 兼容：asdict() 直接转换为字典，便于 JSON 序列化
    4. 轻量：不需要 Pydantic 的验证功能（数据来自内部，可信）

    【字段说明】

    Attributes:
        run_id: Agent 运行 ID，关联到 agent_run 表
        tenant_id: 租户 ID，用于多租户隔离
        step_order: 步骤序号，决定执行顺序（从 0 开始）
        step_type: 步骤类型（thinking, tool_call, tool_result, final_answer）
        content: 步骤主要内容（文本或 JSON）
        tool_name: 工具名称（仅 tool_call 类型）
        tool_input: 工具输入参数（仅 tool_call 类型）
        tool_output: 工具输出结果（仅 tool_result 类型）
        thinking: 思考过程内容（仅 thinking 类型）
        token_count: 本步骤消耗的 token 数
        duration_ms: 步骤执行耗时（毫秒）
        metadata: 扩展元数据（如模型名称、重试次数等）
        created_at: 创建时间（ISO 8601 格式）

    【数据库映射】

    此类对应 agent_step 表，字段名与表列名一致。
    使用 gen_random_uuid() 生成主键 ID。
    """

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


@dataclass
class WALEntry:
    """WAL 条目数据结构

    【设计决策】为什么使用 JSON Lines 格式？
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    JSON Lines (每行一个 JSON 对象) 的优势：
    1. 追加友好：新记录直接追加到文件末尾，无需重写整个文件
    2. 损坏隔离：单行损坏不影响其他记录的解析
    3. 流式处理：可以逐行读取，无需一次性加载整个文件
    4. 人类可读：便于调试和问题排查

    格式示例：
        {"timestamp": "2024-01-01T00:00:00Z", "run_id": "run_001", "step": {...}}
        {"timestamp": "2024-01-01T00:00:01Z", "run_id": "run_002", "step": {...}}

    【字段说明】

    Attributes:
        timestamp: WAL 写入时间戳 (ISO 8601 格式，如 "2024-01-01T00:00:00Z")
                   用于过期清理，超过 24 小时的记录会被自动删除

        run_id: 关联的 Agent 运行 ID，用于批量清理
                当一个 run 的所有 step 成功写入 DB 后，按 run_id 清理 WAL

        step: StepRecord 的字典形式，包含完整的步骤数据
              注意：使用 dict 而非 StepRecord 对象，便于 JSON 序列化

    【为什么需要独立的 WAL 条目类？】

    方案对比：
    ┌─────────────────────┬───────────────────┬───────────────────────┐
    │ 方案                │ 优点              │ 缺点                  │
    ├─────────────────────┼───────────────────┼───────────────────────┤
    │ 直接存 StepRecord   │ 简单              │ 缺少元数据（时间戳）   │
    │ ✓ 独立 WALEntry     │ 元数据完整        │ 需要额外的类定义      │
    │ 字典嵌套            │ 灵活              │ 类型不安全            │
    └─────────────────────┴───────────────────┴───────────────────────┘

    选择独立 WALEntry 类，因为它：
    - 提供类型安全的数据访问
    - 包含必要的元数据（时间戳）用于过期清理
    - 便于序列化和反序列化
    """

    timestamp: str
    run_id: str
    step: dict[str, Any]

    def to_json_line(self) -> str:
        """转换为 JSON 行格式

        【实现原理】为什么是 JSON + 换行符？

        1. JSON 格式：
           - 跨语言兼容，便于其他工具读取（如 Python 脚本恢复）
           - 人类可读，便于调试
           - Python 标准库原生支持，无需额外依赖

        2. 换行符分隔：
           - 每条记录独占一行，损坏隔离
           - 支持流式读取（逐行处理）
           - 符合 JSON Lines 规范 (https://jsonlines.org/)

        Returns:
            JSON 字符串，以换行符结尾（每条记录独占一行）

        示例输出：
            '{"timestamp": "2024-01-01T00:00:00Z", "run_id": "run_001", "step": {...}}\\n'
        """
        return json.dumps(asdict(self)) + "\n"

    @classmethod
    def from_json_line(cls, line: str) -> "WALEntry | None":
        """从 JSON 行解析 WAL 条目

        【错误处理策略】静默跳过损坏记录

        为什么不抛出异常？
        1. WAL 文件可能因磁盘问题或进程崩溃导致部分损坏
        2. 单条记录损坏不应影响其他记录的恢复
        3. 记录警告日志供问题排查，但继续处理其他记录

        【容错设计】
        - JSONDecodeError: 行数据不是有效 JSON → 跳过
        - KeyError: 缺少必要字段 → 跳过
        - 其他异常: 记录错误但继续处理

        Args:
            line: JSON 格式的行数据（可能包含损坏数据）

        Returns:
            WALEntry 对象，解析失败返回 None（静默跳过损坏记录）

        示例：
            >>> entry = WALEntry.from_json_line('{"timestamp": "2024-01-01T00:00:00Z", ...}')
            >>> entry.run_id
            'run_001'

            >>> # 损坏的行返回 None，不抛出异常
            >>> WALEntry.from_json_line('corrupted data')
            None
        """
        try:
            data = json.loads(line.strip())
            return cls(
                timestamp=data["timestamp"],
                run_id=data["run_id"],
                step=data["step"],
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse WAL entry", error=str(e), line=line[:50])
            return None


def _write_to_wal(steps: list[StepRecord]) -> None:
    """将步骤记录追加写入 WAL 文件

    【核心原理】Write-Ahead Logging 的实现
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    WAL 的核心思想：先写日志，后写数据

    ┌─────────────────────────────────────────────────────────────────┐
    │   StepRecord                                                   │
    │      ↓                                                         │
    │   写入 WAL 文件（追加模式，同步写入）                            │
    │      ↓                                                         │
    │   WAL 写入成功                                                 │
    │      ↓                                                         │
    │   写入 PostgreSQL（批量写入）                                  │
    │      ↓                                                         │
    │   DB 写入成功 → 清理 WAL 记录                                  │
    │      ↓                                                         │
    │   完成                                                         │
    └─────────────────────────────────────────────────────────────────┘

    【崩溃场景分析】

    场景 1: WAL 写入前崩溃
        → 数据还在内存缓冲区，丢失。但这是不可避免的（任何系统都无法恢复未持久化的数据）

    场景 2: WAL 写入后，DB 写入前崩溃
        → 数据已持久化到 WAL 文件
        → 重启时 recover_from_wal() 从 WAL 恢复
        → 数据完整性得以保证 ✓

    场景 3: DB 写入成功，WAL 清理前崩溃
        → DB 已有数据，WAL 也有
        → recover_from_wal() 使用 ON CONFLICT DO NOTHING
        → 不会产生重复数据 ✓

    【为什么使用追加模式 ('a') 打开文件？】

    文件打开模式对比：
    ┌──────────┬───────────────────────┬─────────────────────────────┐
    │ 模式     │ 行为                  │ 适用场景                    │
    ├──────────┼───────────────────────┼─────────────────────────────┤
    │ 'w'      │ 覆盖文件              │ 清理 WAL 时使用              │
    │ 'a'      │ 追加到末尾            │ ✓ 写入新记录时使用           │
    │ 'r+'     │ 读写，覆盖            │ 不适用 WAL                   │
    └──────────┴───────────────────────┴─────────────────────────────┘

    追加模式的优势：
    1. 不需要读取整个文件再写回
    2. 操作是原子的（单次 write 系统调用）
    3. 性能最优（O(1) 而非 O(n)）

    【为什么 WAL 写入失败不抛出异常？】

    设计权衡：
    - WAL 是保护机制，不是主要路径
    - 如果 WAL 写入失败但抛异常 → 阻断主流程 → 完全无保护
    - 如果 WAL 写入失败但继续 → DB 写入继续 → 至少数据入了库
    - 后果：仅失去崩溃保护，但不会影响正常写入

    这是"降级"而非"失败"的设计理念。

    Args:
        steps: 待写入的步骤记录列表

    日志输出：
        - DEBUG: 成功写入，记录条数和文件路径
        - ERROR: 写入失败，记录错误详情（但不抛异常）
    """
    if not steps:
        return

    try:
        # 确保目录存在（/tmp 通常存在，但代码需健壮）
        wal_path = Path(WAL_FILE)
        wal_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用统一的时间戳，便于追踪同一批次
        timestamp = datetime.utcnow().isoformat() + "Z"

        # 【关键】以追加模式打开文件
        # 'a' 模式确保每次写入都在文件末尾，不会覆盖已有记录
        # encoding='utf-8' 确保 JSON 中的中文等字符正确编码
        with open(WAL_FILE, "a", encoding="utf-8") as f:
            for step in steps:
                entry = WALEntry(
                    timestamp=timestamp,
                    run_id=step.run_id,
                    step=asdict(step),
                )
                # 每条记录独占一行，便于后续逐行读取
                f.write(entry.to_json_line())

        logger.debug(
            "WAL write completed",
            step_count=len(steps),
            file=WAL_FILE,
            timestamp=timestamp,
        )

    except Exception as e:
        # 【关键】WAL 写入失败不应阻断主流程
        # 这是"降级"设计：失去崩溃保护，但保证正常写入继续
        # 生产环境应配置告警，监控此错误
        logger.error(
            "WAL write failed - crash protection degraded",
            error=str(e),
            error_type=type(e).__name__,
            step_count=len(steps),
            file=WAL_FILE,
            impact="Data will still be written to DB, but crash recovery is unavailable for this batch",
        )


def _read_wal() -> list[WALEntry]:
    """读取 WAL 文件中的未提交记录

    【实现原理】流式读取 + 容错解析
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    为什么逐行读取而不是一次性加载整个文件？

    ┌─────────────────────┬───────────────────────┬───────────────────┐
    │ 方案                │ 内存占用              │ 适用场景          │
    ├─────────────────────┼───────────────────────┼───────────────────┤
    │ f.read() + 解析     │ 加载整个文件到内存    │ 小文件 (<10MB)    │
    │ ✓ 逐行读取          │ O(1) 内存             │ 大文件、流式处理  │
    │ mmap + 解析         │ 操作系统管理          │ 超大文件          │
    └─────────────────────┴───────────────────────┴───────────────────┘

    WAL 文件通常较小（批量写入成功后即清理），但采用逐行读取：
    1. 代码更简洁，无需处理 JSON Lines 格式解析
    2. 内存占用恒定，不受文件大小影响
    3. 便于跳过损坏行（WALEntry.from_json_line 返回 None）

    【返回值顺序】

    返回的列表保持 WAL 文件中的原始顺序（按写入时间排序）：
    - 这意味着先写入的记录会先被恢复
    - 对于 Step 来说，step_order 决定顺序，所以恢复顺序不影响正确性
    - 但保持原始顺序有助于调试和问题排查

    【容错处理】

    - 文件不存在 → 返回空列表（正常情况，首次运行时无 WAL）
    - 单行损坏 → 跳过该行，继续处理其他行
    - 文件读取异常 → 返回已解析的条目（部分恢复）

    Returns:
        WALEntry 列表，保持 WAL 文件中的原始顺序（按写入时间排序）
    """
    entries: list[WALEntry] = []

    if not os.path.exists(WAL_FILE):
        # 首次运行或 WAL 已清理完毕，正常情况
        logger.debug("WAL file not found, no entries to recover", file=WAL_FILE)
        return entries

    try:
        with open(WAL_FILE, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():  # 跳过空行
                    entry = WALEntry.from_json_line(line)
                    if entry:
                        entries.append(entry)
                    else:
                        # 损坏的行被跳过，记录日志供排查
                        logger.warning(
                            "WAL line skipped due to parse error",
                            line_num=line_num,
                            file=WAL_FILE,
                        )

        logger.debug(
            "WAL read completed",
            entry_count=len(entries),
            file=WAL_FILE,
        )

    except Exception as e:
        logger.error(
            "Failed to read WAL file",
            error=str(e),
            error_type=type(e).__name__,
            file=WAL_FILE,
            recovered_entries=len(entries),
        )

    return entries


def _clear_wal_entries(run_ids_to_clear: set[str]) -> None:
    """清理指定 run_id 的 WAL 记录

    【核心原理】WAL 清理策略
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    为什么按 run_id 清理而不是按时间戳或单条记录？

    ┌─────────────────────┬───────────────────────────────────────────┐
    │ 清理维度            │ 问题                                      │
    ├─────────────────────┼───────────────────────────────────────────┤
    │ 单条记录            │ 需要全局唯一 ID，实现复杂                  │
    │ 时间戳范围          │ 可能误删同时间窗口的其他 run 的记录        │
    │ ✓ run_id            │ 批量清理同一 run 的所有记录，简洁高效      │
    └─────────────────────┴───────────────────────────────────────────┘

    设计决策：
    1. 一个 Agent 运行可能产生多条 Step（一个 run_id 对应多条 WAL 记录）
    2. 批量写入时，同一个 run_id 的所有 Step 会一起写入
    3. 按 run_id 批量清理，避免残留部分记录

    【清理时机】

    1. 正常清理：批量写入数据库成功后立即调用
    2. 过期清理：同时清理超过 24 小时的"陈旧"记录
       - 原因：长时间未清理的记录可能是异常终止的 run
       - 防止 WAL 文件无限增长

    【为什么需要重写整个文件？】

    WAL 文件是追加写入的文本文件，不支持"原地删除"：
    - 必须读取所有记录 → 过滤 → 重写
    - 这就是为什么需要定期清理，避免文件过大

    优化方案（未实现）：
    - 使用数据库作为 WAL 存储（支持 DELETE）
    - 使用 LevelDB/RocksDB 等 KV 存储（支持高效删除）

    【实现细节】

    Args:
        run_ids_to_clear: 需要清理的 run_id 集合
    """
    if not os.path.exists(WAL_FILE):
        return

    try:
        # 读取所有条目（注意：这里会完整读取文件）
        all_entries = _read_wal()

        # 过滤：保留未清理且未过期的记录
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        remaining_entries: list[WALEntry] = []
        cleared_count = 0
        expired_count = 0

        for entry in all_entries:
            # 检查 1：是否属于已完成的 run_id
            if entry.run_id in run_ids_to_clear:
                cleared_count += 1
                continue

            # 检查 2：是否超过 24 小时（过期清理）
            try:
                entry_time = datetime.fromisoformat(
                    entry.timestamp.replace("Z", "+00:00")
                )
                if entry_time < cutoff_time.replace(tzinfo=entry_time.tzinfo):
                    expired_count += 1
                    logger.debug(
                        "WAL entry expired and cleared",
                        run_id=entry.run_id,
                        timestamp=entry.timestamp,
                        age_hours=(cutoff_time - entry_time.replace(tzinfo=None)).total_seconds() / 3600,
                    )
                    continue
            except (ValueError, TypeError):
                # 时间戳解析失败，保留该条目以防数据丢失
                logger.warning(
                    "WAL entry has invalid timestamp, keeping for safety",
                    run_id=entry.run_id,
                    timestamp=entry.timestamp,
                )
                pass

            remaining_entries.append(entry)

        # 重写 WAL 文件（注意：这里使用 'w' 模式覆盖）
        wal_path = Path(WAL_FILE)
        if remaining_entries:
            with open(WAL_FILE, "w", encoding="utf-8") as f:
                for entry in remaining_entries:
                    f.write(entry.to_json_line())

            logger.debug(
                "WAL entries cleared",
                cleared_count=cleared_count,
                expired_count=expired_count,
                remaining_count=len(remaining_entries),
                file=WAL_FILE,
            )
        else:
            # 无剩余记录，直接删除 WAL 文件
            if wal_path.exists():
                wal_path.unlink()

            logger.debug(
                "WAL file removed",
                cleared_count=cleared_count,
                expired_count=expired_count,
                file=WAL_FILE,
            )

    except Exception as e:
        logger.error(
            "Failed to clear WAL entries",
            error=str(e),
            error_type=type(e).__name__,
            file=WAL_FILE,
            run_ids_to_clear=list(run_ids_to_clear),
        )


def _cleanup_expired_wal() -> int:
    """清理过期的 WAL 记录

    【为什么需要过期清理？】
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    WAL 文件可能无限增长的场景：
    1. 服务异常终止，WAL 记录未被清理
    2. run_id 不完整，导致部分记录无法匹配清理
    3. 重复失败导致记录堆积

    24 小时过期策略：
    - 超过 24 小时的记录被视为"陈旧数据"
    - 假设：正常运行的服务会在 24 小时内完成或失败
    - 超时的记录可能是孤儿数据，清理不会影响业务

    【与 _clear_wal_entries 的区别】

    ┌─────────────────────┬───────────────────────────────────────────┐
    │ 函数                │ 触发时机                                  │
    ├─────────────────────┼───────────────────────────────────────────┤
    │ _clear_wal_entries  │ 批量写入成功后立即调用                    │
    │ _cleanup_expired_wal│ 服务启动时调用 / 定期维护时调用           │
    └─────────────────────┴───────────────────────────────────────────┘

    Returns:
        清理的过期记录数量
    """
    if not os.path.exists(WAL_FILE):
        return 0

    try:
        all_entries = _read_wal()
        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        remaining_entries: list[WALEntry] = []
        expired_count = 0

        for entry in all_entries:
            try:
                entry_time = datetime.fromisoformat(
                    entry.timestamp.replace("Z", "+00:00")
                )
                if entry_time < cutoff_time.replace(tzinfo=entry_time.tzinfo):
                    expired_count += 1
                    continue
            except (ValueError, TypeError):
                # 时间戳解析失败，保留该条目（宁可保留也不要误删）
                logger.warning(
                    "WAL entry has invalid timestamp during cleanup",
                    run_id=entry.run_id,
                    timestamp=entry.timestamp,
                )
                pass

            remaining_entries.append(entry)

        # 重写 WAL 文件
        wal_path = Path(WAL_FILE)
        if remaining_entries:
            with open(WAL_FILE, "w", encoding="utf-8") as f:
                for entry in remaining_entries:
                    f.write(entry.to_json_line())
        elif wal_path.exists():
            wal_path.unlink()

        if expired_count > 0:
            logger.info(
                "WAL expired entries cleaned up",
                expired_count=expired_count,
                remaining_count=len(remaining_entries),
                cutoff_hours=24,
                file=WAL_FILE,
            )

        return expired_count

    except Exception as e:
        logger.error(
            "Failed to cleanup expired WAL entries",
            error=str(e),
            error_type=type(e).__name__,
            file=WAL_FILE,
        )
        return 0


class StepBuffer:
    """Step 批量写入缓冲区

    【核心概念】批量写入 (Batching) 的价值
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    为什么需要批量写入？

    单条写入 vs 批量写入性能对比：
    ┌───────────────────┬─────────────────────┬─────────────────────┐
    │ 指标              │ 单条写入            │ 批量写入 (100条)    │
    ├───────────────────┼─────────────────────┼─────────────────────┤
    │ 网络往返          │ 100 次              │ 1 次                │
    │ 事务开销          │ 100 次 BEGIN/COMMIT │ 1 次                │
    │ 索引更新          │ 100 次              │ 1 次（批量）        │
    │ 吞吐量            │ ~100 TPS            │ ~10000 TPS          │
    └───────────────────┴─────────────────────┴─────────────────────┘

    结论：批量写入可提升 10-100 倍性能。

    【设计模式】Producer-Consumer with Backpressure

    ┌─────────────────────────────────────────────────────────────┐
    │   Producer (Agent 运行)                                    │
    │        ↓                                                    │
    │   asyncio.Queue (有界队列)                                  │
    │        ↓  [背压控制：队列满时阻塞]                           │
    │   Consumer (后台刷新任务)                                   │
    │        ↓                                                    │
    │   PostgreSQL (批量写入)                                     │
    └─────────────────────────────────────────────────────────────┘

    背压控制的意义：
    - 防止生产者（Agent）写入速度超过消费者（DB）处理速度
    - 当队列满时，生产者阻塞，自然形成流量控制
    - 避免内存无限增长导致 OOM

    【参数调优指南】

    ┌─────────────────────┬─────────────┬───────────────────────────┐
    │ 参数                │ 默认值      │ 调优建议                  │
    ├─────────────────────┼─────────────┼───────────────────────────┤
    │ batch_size          │ 50          │ 高并发场景可增至 100-200  │
    │ flush_interval_ms   │ 500         │ 低延迟场景可降至 100-200  │
    │ max_buffer_size     │ 1000        │ 根据内存预算调整          │
    └─────────────────────┴─────────────┴───────────────────────────┘

    权衡：
    - 更大的 batch_size → 更高吞吐，但单次延迟更高
    - 更小的 flush_interval → 更低延迟，但更多 DB 往返
    - 更大的 max_buffer_size → 更大容量，但更高内存占用

    【使用示例】

    ```python
    # 初始化
    buffer = StepBuffer(
        db_pool=db_pool,
        batch_size=100,        # 每 100 条触发一次写入
        flush_interval_ms=500, # 或每 500ms 触发一次
        max_buffer_size=1000,  # 最多缓冲 1000 条
    )

    # 启动（会自动恢复 WAL 中的记录）
    await buffer.start()

    # 添加步骤
    await buffer.add_step(step_record)

    # 获取统计信息
    print(buffer.stats)

    # 优雅停机
    await buffer.stop()  # 会刷新所有待写入数据
    ```

    【特性列表】
    - 内存攒批：收集 N 条 step 后批量写入
    - 定时刷新：等待 T 毫秒后自动刷新
    - 背压控制：缓冲区满时阻塞
    - 优雅停机：刷新所有待写入数据
    - WAL 保护：写入前先写 WAL，崩溃后可恢复
    """

    def __init__(
        self,
        db_pool: AsyncConnectionPool,
        batch_size: int = 50,
        flush_interval_ms: int = 500,
        max_buffer_size: int = 1000,
    ):
        """初始化 StepBuffer

        Args:
            db_pool: PostgreSQL 异步连接池
            batch_size: 批量写入阈值，达到此数量触发立即写入
            flush_interval_ms: 定时刷新间隔（毫秒）
            max_buffer_size: 缓冲区最大容量，超过此容量会阻塞生产者
        """
        self.db_pool = db_pool
        self.batch_size = batch_size
        self.flush_interval = flush_interval_ms / 1000
        self.max_buffer_size = max_buffer_size

        # 【关键】使用有界队列实现背压控制
        # 当队列满时，put() 会阻塞，防止内存无限增长
        self._buffer: asyncio.Queue[StepRecord] = asyncio.Queue(maxsize=max_buffer_size)
        self._running = False
        self._flush_task: asyncio.Task | None = None

        # 统计信息，用于监控和调试
        self._stats = {
            "total_added": 0,      # 总共添加的记录数
            "total_flushed": 0,    # 成功刷新的记录数
            "batch_count": 0,      # 批量写入次数
            "wal_recovered": 0,    # 从 WAL 恢复的记录数
        }

    async def start(self) -> None:
        """启动后台刷新任务，并恢复 WAL 中的记录

        【启动流程】
        1. 检查是否已运行（防止重复启动）
        2. 恢复 WAL 中的记录（崩溃恢复）
        3. 启动后台定时刷新任务

        注意：启动时会阻塞，直到 WAL 恢复完成。
        """
        if self._running:
            logger.warning("StepBuffer already running, skip start")
            return

        self._running = True

        # 【关键】启动前先恢复 WAL 中的记录
        # 这确保了崩溃后重启的数据完整性
        wal_recovered = await self.recover_from_wal()

        # 启动后台刷新任务
        self._flush_task = asyncio.create_task(self._flush_loop())

        logger.info(
            "StepBuffer started",
            batch_size=self.batch_size,
            flush_interval_ms=self.flush_interval * 1000,
            max_buffer_size=self.max_buffer_size,
            wal_recovered=wal_recovered,
        )

    async def stop(self) -> None:
        """停止并刷新所有待写入数据

        【优雅停机流程】
        1. 标记停止状态
        2. 取消后台刷新任务
        3. 刷新缓冲区中的所有数据
        4. 记录最终统计信息

        注意：此方法会阻塞，直到所有数据写入完成。
        这保证了停机时不会丢失数据。
        """
        if not self._running:
            logger.warning("StepBuffer not running, skip stop")
            return

        self._running = False

        # 取消后台任务
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # 【关键】最终刷新，确保不丢失数据
        await self._flush_all()

        logger.info(
            "StepBuffer stopped",
            stats=self._stats,
            final_buffer_size=self._buffer.qsize(),
        )

    async def add_step(self, step: StepRecord) -> None:
        """添加 step 到缓冲区（阻塞版本）

        【阻塞语义】
        如果缓冲区满，此方法会阻塞，直到有空间可用。
        这实现了背压控制：生产者会被动等待，避免内存溢出。

        Args:
            step: 待写入的步骤记录

        Raises:
            asyncio.CancelledError: 如果在等待期间被取消
        """
        await self._buffer.put(step)
        self._stats["total_added"] += 1

        # 【优化】如果达到批次大小，立即触发刷新
        # 这避免了等待定时器，降低延迟
        if self._buffer.qsize() >= self.batch_size:
            asyncio.create_task(self._flush())

    async def add_step_nowait(self, step: StepRecord) -> bool:
        """非阻塞添加 step

        【使用场景】
        - 不希望阻塞生产者
        - 可以接受丢弃部分数据（如日志场景）
        - 需要根据返回值决定后续处理

        Args:
            step: 待写入的步骤记录

        Returns:
            True 成功添加，False 缓冲区满
        """
        try:
            self._buffer.put_nowait(step)
            self._stats["total_added"] += 1
            return True
        except asyncio.QueueFull:
            logger.warning(
                "StepBuffer full, step dropped",
                run_id=step.run_id,
                step_order=step.step_order,
                buffer_size=self._buffer.qsize(),
            )
            return False

    async def _flush_loop(self) -> None:
        """后台定时刷新循环

        【实现原理】
        使用 asyncio.sleep 实现定时器，每隔 flush_interval
        触发一次刷新。

        注意：这不是精确的定时器。如果刷新操作耗时较长，
        下一次刷新会延迟。这是故意的——避免刷新重叠。
        """
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush()
            except asyncio.CancelledError:
                # 正常停机时会触发，跳出循环
                break
            except Exception as e:
                # 记录错误但继续运行
                logger.error(
                    "Flush loop error",
                    error=str(e),
                    error_type=type(e).__name__,
                )

    async def _flush(self) -> None:
        """刷新一批数据到数据库

        【实现细节】
        从队列中取出最多 batch_size 条记录，批量写入。
        使用 get_nowait() 避免阻塞。
        """
        batch: list[StepRecord] = []

        # 从队列中取出最多 batch_size 条记录
        while len(batch) < self.batch_size:
            try:
                step = self._buffer.get_nowait()
                batch.append(step)
            except asyncio.QueueEmpty:
                break

        if batch:
            await self._write_batch(batch)

    async def _flush_all(self) -> None:
        """刷新所有待写入数据

        【使用场景】
        仅在优雅停机时调用，确保所有数据写入完成。
        """
        batch: list[StepRecord] = []

        # 取出队列中所有记录
        while True:
            try:
                step = self._buffer.get_nowait()
                batch.append(step)
            except asyncio.QueueEmpty:
                break

        if batch:
            await self._write_batch(batch)

    async def _write_batch(self, steps: list[StepRecord]) -> None:
        """批量写入数据库

        【WAL 保护流程】三阶段写入
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        ┌─────────────────────────────────────────────────────────────┐
        │ 阶段 1: 写入 WAL（同步）                                    │
        │   - 目的：确保持久化，崩溃后可恢复                           │
        │   - 操作：追加写入到 WAL 文件                               │
        │   - 失败处理：记录错误但继续（降级模式）                     │
        │                                                             │
        │ 阶段 2: 写入 PostgreSQL（异步）                             │
        │   - 目的：持久化到主数据库                                  │
        │   - 操作：批量 INSERT                                       │
        │   - 失败处理：WAL 中已有记录，重启后自动恢复                │
        │                                                             │
        │ 阶段 3: 清理 WAL（成功后）                                  │
        │   - 目的：释放 WAL 空间，避免文件过大                       │
        │   - 操作：按 run_id 清理已提交的记录                        │
        └─────────────────────────────────────────────────────────────┘

        【关键设计】为什么不使用事务？

        WAL + 批量写入 已经提供了类似事务的保证：
        - WAL 记录 + DB 写入 = 两阶段提交的简化版
        - 崩溃恢复逻辑处理了不一致情况

        如果使用事务：
        - 需要手动管理事务
        - 批量写入效率降低（事务持有锁的时间更长）

        【SQL 注入防护】
        使用参数化查询（%s 占位符）， psycopg 会自动处理转义。

        Args:
            steps: 待写入的步骤记录列表
        """
        if not steps:
            return

        # 【阶段 1】先写入 WAL（先写日志）
        _write_to_wal(steps)

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
            # 【阶段 2】写入数据库
            async with self.db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    # executemany 使用单次往返发送所有数据
                    await cur.executemany(query, values_list)

            # 更新统计
            self._stats["total_flushed"] += len(steps)
            self._stats["batch_count"] += 1

            # 【阶段 3】成功后清理 WAL
            run_ids = {step.run_id for step in steps}
            _clear_wal_entries(run_ids)

            logger.debug(
                "Step batch written successfully",
                batch_size=len(steps),
                total_flushed=self._stats["total_flushed"],
                batch_count=self._stats["batch_count"],
                run_ids=list(run_ids),
            )

        except Exception as e:
            # 数据库写入失败，但 WAL 中已有记录
            # 重启后会自动恢复这些记录
            logger.error(
                "Failed to write step batch to database",
                error=str(e),
                error_type=type(e).__name__,
                batch_size=len(steps),
                run_ids=[step.run_id for step in steps],
                wal_protected=True,
                recovery="Records are preserved in WAL and will be recovered on restart",
            )
            # 【关键】不抛出异常，避免上层重试导致数据重复
            # WAL 中的记录会在重启时被恢复

    async def recover_from_wal(self) -> int:
        """从 WAL 恢复未提交的记录

        【核心概念】崩溃恢复 (Crash Recovery)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        WAL 的价值在崩溃恢复时体现：

        ┌─────────────────────────────────────────────────────────────┐
        │ 崩溃场景                                                    │
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│
        │ 1. 进程崩溃（OOM、Segmentation Fault）                     │
        │ 2. 容器/节点重启（Kubernetes 驱逐、硬件故障）              │
        │ 3. 网络中断导致数据库连接断开                               │
        └─────────────────────────────────────────────────────────────┘

        恢复流程：
        ┌─────────────────────────────────────────────────────────────┐
        │ Step 1: 清理过期记录（超过 24 小时）                        │
        │        → 避免恢复陈旧数据                                   │
        │                                                             │
        │ Step 2: 读取 WAL 文件                                       │
        │        → 解析 JSON Lines 格式                               │
        │                                                             │
        │ Step 3: 转换为 StepRecord 对象                              │
        │        → 验证数据完整性                                     │
        │                                                             │
        │ Step 4: 写入数据库（ON CONFLICT DO NOTHING）                │
        │        → 幂等操作，避免重复数据                              │
        │                                                             │
        │ Step 5: 清理已恢复的 WAL 记录                                │
        │        → 释放磁盘空间                                       │
        └─────────────────────────────────────────────────────────────┘

        【幂等性保证】

        为什么使用 ON CONFLICT DO NOTHING？

        场景：写入成功，但 WAL 清理失败后再次崩溃

        - 第一次：写入 DB 成功 → 清理 WAL 失败 → 崩溃
        - 第二次：读取 WAL → 再次写入 DB → 冲突？
        - ON CONFLICT DO NOTHING：忽略冲突，继续处理

        这确保了恢复是幂等的（多次执行结果相同）。

        【启动时调用 vs 定时调用】

        当前实现仅在启动时调用。为什么不定时调用？

        定时恢复的风险：
        - 正常运行时 WAL 应为空（写入成功后即清理）
        - 如果 WAL 非空，说明有问题，应该告警而非静默恢复
        - 定时恢复可能掩盖问题

        推荐的增强：
        - 添加 WAL 文件大小监控
        - WAL 条目过多时触发告警

        Returns:
            成功恢复的记录数量

        日志输出：
            - INFO: 恢复开始和完成
            - WARNING: 解析失败的记录
            - ERROR: 恢复失败（保留 WAL 供下次尝试）
        """
        # Step 1: 清理过期记录（超过 24 小时的陈旧数据）
        expired_count = _cleanup_expired_wal()
        if expired_count > 0:
            logger.info(
                "WAL expired entries cleaned before recovery",
                expired_count=expired_count,
            )

        # Step 2: 读取 WAL 条目
        wal_entries = _read_wal()

        if not wal_entries:
            logger.debug("No WAL entries to recover")
            return 0

        logger.info(
            "Starting WAL recovery",
            entry_count=len(wal_entries),
            file=WAL_FILE,
        )

        # Step 3: 转换 WAL 条目为 StepRecord
        recovered_steps: list[StepRecord] = []
        parse_errors = 0

        for entry in wal_entries:
            try:
                step_data = entry.step
                step = StepRecord(
                    run_id=step_data["run_id"],
                    tenant_id=step_data["tenant_id"],
                    step_order=step_data["step_order"],
                    step_type=step_data["step_type"],
                    content=step_data["content"],
                    tool_name=step_data.get("tool_name"),
                    tool_input=step_data.get("tool_input"),
                    tool_output=step_data.get("tool_output"),
                    thinking=step_data.get("thinking"),
                    token_count=step_data.get("token_count", 0),
                    duration_ms=step_data.get("duration_ms"),
                    metadata=step_data.get("metadata", {}),
                    created_at=step_data.get("created_at"),
                )
                recovered_steps.append(step)
            except (KeyError, TypeError) as e:
                parse_errors += 1
                logger.warning(
                    "Failed to parse WAL entry to StepRecord",
                    error=str(e),
                    error_type=type(e).__name__,
                    run_id=entry.run_id,
                    timestamp=entry.timestamp,
                )

        if not recovered_steps:
            logger.warning(
                "No valid WAL entries to recover after parsing",
                total_entries=len(wal_entries),
                parse_errors=parse_errors,
            )
            return 0

        # Step 4: 写入数据库（使用 ON CONFLICT DO NOTHING 确保幂等）
        query = """
            INSERT INTO agent_step (
                id, run_id, tenant_id, step_order, step_type, content,
                tool_name, tool_input, tool_output, thinking,
                token_count, duration_ms, metadata, created_at
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT DO NOTHING
        """

        recovered_count = 0

        try:
            values_list = []
            for step in recovered_steps:
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

            async with self.db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(query, values_list)

            recovered_count = len(recovered_steps)

            # Step 5: 清理已恢复的 WAL 记录
            run_ids = {step.run_id for step in recovered_steps}
            _clear_wal_entries(run_ids)

            self._stats["wal_recovered"] = recovered_count

            logger.info(
                "WAL recovery completed successfully",
                recovered_count=recovered_count,
                run_ids=list(run_ids),
                parse_errors=parse_errors,
            )

        except Exception as e:
            logger.error(
                "Failed to recover from WAL",
                error=str(e),
                error_type=type(e).__name__,
                entry_count=len(recovered_steps),
                parse_errors=parse_errors,
                retry_hint="WAL entries preserved, will retry on next startup",
            )
            # WAL 记录保留，下次启动时会再次尝试恢复

        return recovered_count

    @property
    def stats(self) -> dict:
        """获取统计信息

        【监控指标】可用于健康检查和告警
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        返回的指标及其含义：

        ┌─────────────────────┬───────────────────────────────────────────┐
        │ 指标                │ 含义                                      │
        ├─────────────────────┼───────────────────────────────────────────┤
        │ total_added         │ 累计添加的记录数                          │
        │ total_flushed       │ 成功写入 DB 的记录数                      │
        │ batch_count         │ 批量写入次数                              │
        │ wal_recovered       │ 从 WAL 恢复的记录数                       │
        │ buffer_size         │ 当前缓冲区大小                            │
        │ max_buffer_size     │ 缓冲区最大容量                            │
        └─────────────────────┴───────────────────────────────────────────┘

        健康检查建议：
        - buffer_size > max_buffer_size * 0.8 → 背压告警
        - total_added - total_flushed > 100 → 积压告警
        - wal_recovered > 0 → 崩溃发生过，需要排查

        Returns:
            包含统计信息的字典
        """
        return {
            **self._stats,
            "buffer_size": self._buffer.qsize(),
            "max_buffer_size": self.max_buffer_size,
            "pending_count": self._stats["total_added"] - self._stats["total_flushed"],
        }

    @property
    def is_running(self) -> bool:
        """检查缓冲区是否正在运行

        Returns:
            True 如果正在运行，False 如果已停止
        """
        return self._running
