"""数据库连接池管理

【核心概念】异步数据库连接池
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

企业级应用需要高效的数据库连接管理：
1. 连接池：避免频繁创建/销毁连接的开销
2. 异步：与 FastAPI/LangGraph 配合，不阻塞事件循环
3. 健康检查：自动检测和剔除失效连接
4. 事务管理：支持分布式事务

【技术选型】为什么使用 asyncpg？
┌─────────────────────────────────────────────────────────────────────────┐
│  驱动              │  优点                    │  缺点                  │
├────────────────────┼──────────────────────────┼────────────────────────┤
│  psycopg2         │  成熟稳定                │  同步阻塞、性能受限    │
│  psycopg3        │  支持异步                │  依赖 libpq、部署复杂  │
│  ✓ asyncpg        │  纯Python、高性能异步    │  不支持同步模式        │
│  SQLAlchemy async│  ORM 抽象               │  性能开销、学习曲线    │
└─────────────────────────────────────────────────────────────────────────┘

asyncpg 的优势：
- 性能：比 psycopg2 快 3-5 倍
- 原生异步：与 asyncio 完美配合
- 纯 Python：无需编译 C 扩展
- 类型支持：PostgreSQL 原生类型自动转换

【连接池配置指南】
- min_size: 最小连接数（通常为 CPU 核心数）
- max_size: 最大连接数（通常为 CPU 核心数 * 2-4）
- max_queries: 单连接最大查询数（避免内存泄漏）
- max_inactive_connection_lifetime: 空闲连接超时

【参考】
- asyncpg 文档: https://magicstack.github.io/asyncpg/current/
- PostgreSQL 连接池最佳实践: https://pganalyze.com/blog/connections
"""

from __future__ import annotations

import asyncio
import structlog
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from asyncpg import Pool, Connection
from asyncpg.exceptions import PostgresError, InterfaceError

from app.core.config import config
from app.core.exceptions import DatabaseError, DatabaseConnectionError

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════════════════
# 全局连接池实例
# ═══════════════════════════════════════════════════════════════════════════

_pool: Pool | None = None


async def init_database_pool() -> Pool:
    """初始化数据库连接池

    【启动流程】
    1. 解析数据库 URL
    2. 创建连接池
    3. 执行健康检查
    4. 注册类型编解码器（如需）

    【配置参数】
    - min_size: 最小连接数，建议设为 CPU 核心数
    - max_size: 最大连接数，根据并发需求调整
    - command_timeout: 单次查询超时（秒）
    - max_inactive_connection_lifetime: 空闲连接存活时间（秒）

    Returns:
        asyncpg.Pool: 连接池实例

    Raises:
        DatabaseConnectionError: 连接失败
    """
    global _pool

    if _pool is not None:
        return _pool

    try:
        # 解析连接 URL
        # 格式: postgresql+asyncpg://user:password@host:port/database
        db_url = config.database_url.replace("+asyncpg", "")

        logger.info(
            "database_pool_initializing",
            pool_size=config.database_pool_size,
        )

        _pool = await asyncpg.create_pool(
            dsn=db_url,
            min_size=max(1, config.database_pool_size // 4),
            max_size=config.database_pool_size,
            command_timeout=30.0,
            max_inactive_connection_lifetime=300.0,
            # 连接初始化回调
            init=_init_connection,
        )

        # 健康检查
        async with _pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            logger.info(
                "database_pool_initialized",
                pool_size=_pool.get_size(),
                postgres_version=version[:50],
            )

        return _pool

    except Exception as e:
        logger.error(
            "database_pool_init_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise DatabaseConnectionError(f"数据库连接失败: {e}")


async def _init_connection(conn: Connection) -> None:
    """连接初始化回调

    【用途】
    - 设置会话参数（时区、编码等）
    - 注册自定义类型编解码器
    - 预编译常用语句

    Args:
        conn: 数据库连接
    """
    # 设置时区
    await conn.execute("SET TIME ZONE 'Asia/Shanghai'")
    # 设置客户端编码
    await conn.execute("SET client_encoding = 'UTF8'")
    # 设置搜索路径（如需）
    # await conn.execute("SET search_path TO app_schema, public")


async def close_database_pool() -> None:
    """关闭数据库连接池

    【关闭流程】
    1. 等待所有活跃查询完成（最多 10 秒）
    2. 关闭所有连接
    3. 清理资源
    """
    global _pool

    if _pool is None:
        return

    logger.info("database_pool_closing", pool_size=_pool.get_size())

    try:
        # 等待活跃连接完成，最多等待 10 秒
        await asyncio.wait_for(_pool.close(), timeout=10.0)
        logger.info("database_pool_closed")
    except asyncio.TimeoutError:
        logger.warning("database_pool_close_timeout")
        # 强制终止
        _pool.terminate()
    finally:
        _pool = None


def get_database_pool() -> Pool:
    """获取数据库连接池

    【使用方式】
        pool = get_database_pool()
        async with pool.acquire() as conn:
            result = await conn.fetch("SELECT * FROM users")

    Returns:
        asyncpg.Pool: 连接池实例

    Raises:
        RuntimeError: 连接池未初始化
    """
    if _pool is None:
        raise RuntimeError("数据库连接池未初始化，请先调用 init_database_pool()")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncGenerator[Connection, None]:
    """获取数据库连接（上下文管理器）

    【使用方式】
        async with get_connection() as conn:
            result = await conn.fetch("SELECT * FROM users")

    【自动管理】
    - 自动归还连接到池中
    - 异常时自动回滚事务
    """
    pool = get_database_pool()
    async with pool.acquire() as conn:
        try:
            yield conn
        except PostgresError as e:
            logger.error(
                "database_query_error",
                error=str(e),
                sqlstate=e.sqlstate,
            )
            raise DatabaseError(f"数据库查询失败: {e}")


@asynccontextmanager
async def transaction() -> AsyncGenerator[Connection, None]:
    """事务上下文管理器

    【使用方式】
        async with transaction() as conn:
            await conn.execute("INSERT INTO orders (...) VALUES (...)")
            await conn.execute("UPDATE inventory SET stock = stock - 1")
            # 自动提交或回滚

    【事务特性】
    - 自动提交（正常退出时）
    - 自动回滚（异常退出时）
    - 支持嵌套事务（SAVEPOINT）
    """
    async with get_connection() as conn:
        async with conn.transaction():
            yield conn


async def execute_query(
    query: str,
    *args: Any,
    timeout: float = 30.0,
) -> str:
    """执行单条 SQL（无返回值）

    【使用场景】
    - INSERT / UPDATE / DELETE
    - DDL 语句
    - SET 命令

    Args:
        query: SQL 语句
        *args: 参数（使用 $1, $2 占位符）
        timeout: 超时时间（秒）

    Returns:
        状态字符串（如 "INSERT 0 1"）
    """
    async with get_connection() as conn:
        return await conn.execute(query, *args, timeout=timeout)


async def fetch_one(
    query: str,
    *args: Any,
    timeout: float = 30.0,
) -> asyncpg.Record | None:
    """查询单行

    Args:
        query: SQL 查询语句
        *args: 参数
        timeout: 超时时间（秒）

    Returns:
        单行记录，或 None（无结果）
    """
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args, timeout=timeout)


async def fetch_all(
    query: str,
    *args: Any,
    timeout: float = 30.0,
) -> list[asyncpg.Record]:
    """查询多行

    Args:
        query: SQL 查询语句
        *args: 参数
        timeout: 超时时间（秒）

    Returns:
        记录列表
    """
    async with get_connection() as conn:
        return await conn.fetch(query, *args, timeout=timeout)


async def fetch_val(
    query: str,
    *args: Any,
    timeout: float = 30.0,
) -> Any:
    """查询单个值

    Args:
        query: SQL 查询语句
        *args: 参数
        timeout: 超时时间（秒）

    Returns:
        单个值，或 None
    """
    async with get_connection() as conn:
        return await conn.fetchval(query, *args, timeout=timeout)


async def execute_many(
    query: str,
    args_list: list[tuple],
    timeout: float = 60.0,
) -> None:
    """批量执行（高效批量插入/更新）

    【性能优势】
    - 单次网络往返
    - 服务端预编译
    - 比循环 execute 快 10-100 倍

    Args:
        query: SQL 语句
        args_list: 参数列表
        timeout: 超时时间（秒）
    """
    async with get_connection() as conn:
        await conn.executemany(query, args_list, timeout=timeout)


# ═══════════════════════════════════════════════════════════════════════════
# 健康检查
# ═══════════════════════════════════════════════════════════════════════════


async def check_database_health() -> dict[str, Any]:
    """数据库健康检查

    【检查项】
    1. 连接可用性
    2. 响应延迟
    3. 连接池状态
    4. 数据库负载

    Returns:
        健康状态字典
    """
    if _pool is None:
        return {
            "status": "unhealthy",
            "error": "连接池未初始化",
        }

    try:
        start = asyncio.get_event_loop().time()
        async with get_connection() as conn:
            await conn.fetchval("SELECT 1")
        latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)

        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "pool_size": _pool.get_size(),
            "pool_idle": _pool.get_idle_size(),
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
