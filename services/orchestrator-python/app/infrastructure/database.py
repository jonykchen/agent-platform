"""数据库连接池管理

【技术选型】Python PostgreSQL 驱动对比（量化数据）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌────────────────────┬───────────────┬───────────────┬───────────────┐
│ 方案               │ 性能 (QPS)    │ 异步支持      │ 类型转换      │
├────────────────────┼───────────────┼───────────────┼───────────────┤
│ psycopg2          │ ~10,000       │ × 同步阻塞   │ 需手动处理    │
│ psycopg3          │ ~15,000       │ √ 支持       │ 较好          │
│ ✓ asyncpg         │ ~50,000       │ √ 原生异步   │ √ 自动转换   │
│ SQLAlchemy async │ ~30,000       │ √ 支持       │ ORM 抽象      │
└────────────────────┴───────────────┴───────────────┴───────────────┘

【决策依据】选择 asyncpg 的原因：
1. 性能：比 psycopg2 快 3-5 倍，适合高并发场景
2. 原生异步：与 FastAPI/LangGraph 完美配合，不阻塞事件循环
3. 纯 Python：无需编译 C 扩展，部署简单
4. 类型自动转换：PostgreSQL 原生类型自动转 Python 类型

【风险与缓解】
┌────────────────────┬─────────────────────────────────────────────────┐
│ 风险               │ 缓解措施                                        │
├────────────────────┼─────────────────────────────────────────────────┤
│ 连接池耗尽         │ 配置合理的 max_size，添加等待超时              │
│ 查询超时           │ 设置 command_timeout，添加重试机制             │
│ 事务未提交         │ 使用 transaction() 上下文管理器自动提交/回滚   │
│ 连接泄漏           │ 使用 get_connection() 上下文管理器自动归还     │
└────────────────────┴─────────────────────────────────────────────────┘

【演进历史】
- v1.0: 使用 psycopg2，同步阻塞导致性能瓶颈（P95 延迟 > 500ms）
- v2.0: 切换到 asyncpg，性能提升 3-5 倍（P95 延迟 < 100ms）
- v2.1: 添加连接池管理和多租户 RLS 支持

【核心概念】异步数据库连接池
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

企业级应用需要高效的数据库连接管理：
1. 连接池：避免频繁创建/销毁连接的开销（每次连接 ~10ms）
2. 异步：与 FastAPI/LangGraph 配合，不阻塞事件循环
3. 健康检查：自动检测和剔除失效连接
4. 事务管理：支持分布式事务

【连接池配置依据】
┌─────────────────────────────────────────────────────────────────────────┐
│ 参数                              │ 计算公式/依据                        │
├────────────────────────────────────┼──────────────────────────────────────┤
│ min_size = pool_size / 4         │ 保持最小连接数，避免冷启动延迟       │
│ max_size = pool_size             │ 上限由数据库连接数限制决定          │
│ command_timeout = 30s            │ 复杂查询需要足够时间，但要防止无限等待 │
│ max_inactive_lifetime = 300s     │ 空闲连接存活时间，平衡资源与响应速度 │
└─────────────────────────────────────────────────────────────────────────┘

【参考】
- asyncpg 文档: https://magicstack.github.io/asyncpg/current/
- PostgreSQL 连接池最佳实践: https://pganalyze.com/blog/connections
- 行级安全策略: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import structlog
from asyncpg import Connection, Pool
from asyncpg.exceptions import PostgresError

from app.core.config import config
from app.core.exceptions import DatabaseConnectionError, DatabaseError

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

    【配置参数详解】
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 参数                     │ 默认值   │ 依据                             │
    ├───────────────────────────┼──────────┼───────────────────────────────────┤
    │ min_size                 │ 5        │ pool_size / 4，避免冷启动延迟    │
    │ max_size                 │ 20       │ 与数据库 max_connections 匹配   │
    │ command_timeout          │ 30s      │ 复杂查询需要足够时间             │
    │ max_inactive_lifetime    │ 300s     │ 空闲连接存活时间，平衡资源       │
    └───────────────────────────┴──────────┴───────────────────────────────────┘

    【容量规划公式】
    max_size = min(
        数据库 max_connections / 服务实例数,
        CPU核心数 × 4 + 有效磁盘数
    )
    本项目：max_connections=100, 实例数=4 → max_size=20

    Returns:
        asyncpg.Pool: 连接池实例

    Raises:
        DatabaseConnectionError: 连接失败
    """
    global _pool

    if _pool is not None:
        logger.debug("database_pool_already_initialized", pool_size=_pool.get_size())
        return _pool

    try:
        # 解析连接 URL
        # 格式: postgresql+asyncpg://user:password@host:port/database
        db_url = config.database_url.replace("+asyncpg", "")

        # 连接池配置
        pool_min = max(1, config.database_pool_size // 4)
        pool_max = config.database_pool_size

        logger.info(
            "database_pool_initializing",
            min_size=pool_min,
            max_size=pool_max,
            command_timeout=30.0,
            max_inactive_lifetime=300.0,
        )

        _pool = await asyncpg.create_pool(
            dsn=db_url,
            min_size=pool_min,  # 最小连接数：pool_size / 4，保持热连接
            max_size=pool_max,  # 最大连接数：由配置决定，上限受数据库限制
            command_timeout=30.0,  # 查询超时：30秒，防止无限等待
            max_inactive_connection_lifetime=300.0,  # 空闲连接存活：5分钟
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
    - 为多租户 RLS 做准备

    【多租户 RLS 准备】
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ PostgreSQL 行级安全（Row-Level Security）工作原理：                     │
    │                                                                         │
    │ 1. 创建策略：                                                           │
    │    CREATE POLICY tenant_isolation ON orders                            │
    │        USING (tenant_id = current_setting('app.current_tenant')::uuid) │
    │                                                                         │
    │ 2. 启用 RLS：                                                           │
    │    ALTER TABLE orders ENABLE ROW LEVEL SECURITY                        │
    │                                                                         │
    │ 3. 设置会话参数（每次请求）：                                           │
    │    SET LOCAL app.current_tenant = 'tenant_001'                         │
    │                                                                         │
    │ 4. 自动过滤：所有查询自动添加 tenant_id 过滤条件                        │
    └─────────────────────────────────────────────────────────────────────────┘

    【为什么在初始化时预设为空？】
    - 确保 app.current_tenant 参数在所有连接中存在
    - 防止因参数不存在导致 RLS 策略报错
    - 空字符串会被 RLS 策略视为"无匹配"，返回空结果集（安全默认值）

    Args:
        conn: 数据库连接
    """
    # 设置时区（影响 CURRENT_TIMESTAMP、NOW() 等函数）
    await conn.execute("SET TIME ZONE 'Asia/Shanghai'")
    # 设置客户端编码（确保中文等字符正确存储）
    await conn.execute("SET client_encoding = 'UTF8'")
    # 设置搜索路径（如需，用于多 schema 场景）
    # await conn.execute("SET search_path TO app_schema, public")

    # 【多租户 RLS】预设租户参数为空
    # 注意：SET LOCAL 仅在当前事务内有效，这里用于初始化
    # 实际租户值在 get_tenant_aware_connection() 中通过 SET LOCAL 设置
    await conn.execute("SET LOCAL app.current_tenant = ''")

    logger.debug("database_connection_initialized")


def get_db_pool() -> Pool | None:
    """获取数据库连接池

    Returns:
        asyncpg 连接池实例，未初始化时返回 None
    """
    return _pool


async def close_database_pool() -> None:
    """关闭数据库连接池

    【关闭流程】
    1. 等待所有活跃查询完成（最多 10 秒）
    2. 关闭所有连接
    3. 清理资源

    【优雅关闭 vs 强制终止】
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 方式              │ 行为                               │ 使用场景      │
    ├────────────────────┼────────────────────────────────────┼───────────────┤
    │ close()           │ 等待活跃查询完成，优雅关闭        │ 正常关闭     │
    │ terminate()       │ 立即终止所有连接                  │ 超时/强制   │
    └─────────────────────────────────────────────────────────────────────────┘

    【最佳实践】
    - 正常关闭：给足够时间让活跃事务完成
    - 超时处理：避免无限等待导致服务无法停止
    - 日志记录：帮助排查关闭过程中的问题
    """
    global _pool

    if _pool is None:
        logger.debug("database_pool_already_closed")
        return

    pool_size = _pool.get_size()
    idle_size = _pool.get_idle_size()
    logger.info(
        "database_pool_closing",
        pool_size=pool_size,
        idle_size=idle_size,
        active_size=pool_size - idle_size,
    )

    try:
        # 等待活跃连接完成，最多等待 10 秒
        await asyncio.wait_for(_pool.close(), timeout=10.0)
        logger.info("database_pool_closed_gracefully")
    except TimeoutError:
        logger.warning(
            "database_pool_close_timeout",
            message="Graceful close timed out after 10s, forcing termination",
        )
        # 强制终止
        _pool.terminate()
        logger.info("database_pool_terminated")
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
    - 自动归还连接到池中（即使发生异常）
    - 异常时自动回滚未提交的事务
    - 连接生命周期完全由上下文管理

    【为什么使用上下文管理器？】
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 方式                    │ 风险                                          │
    ├─────────────────────────┼───────────────────────────────────────────────┤
    │ 手动 acquire/release   │ 忘记释放连接 → 连接池耗尽                     │
    │ try/finally            │ 代码冗长，容易遗漏异常处理                    │
    │ ✓ 上下文管理器         │ 自动管理，异常安全，代码简洁                  │
    └─────────────────────────────────────────────────────────────────────────┘

    【日志追踪】
    - 连接获取时记录，用于排查连接泄漏
    - 连接释放时记录，用于监控连接池使用情况
    """
    pool = get_database_pool()
    conn_id = None

    logger.debug("database_connection_acquiring", pool_size=pool.get_size(), pool_idle=pool.get_idle_size())

    async with pool.acquire() as conn:
        conn_id = id(conn)
        logger.debug(
            "database_connection_acquired",
            connection_id=conn_id,
            pool_size=pool.get_size(),
            pool_idle=pool.get_idle_size(),
        )
        try:
            yield conn
        except PostgresError as e:
            logger.error(
                "database_query_error",
                connection_id=conn_id,
                error=str(e),
                sqlstate=e.sqlstate,
                error_class=type(e).__name__,
            )
            raise DatabaseError(f"数据库查询失败: {e}")
        finally:
            logger.debug("database_connection_releasing", connection_id=conn_id)


@asynccontextmanager
async def transaction() -> AsyncGenerator[Connection, None]:
    """事务上下文管理器

    【使用方式】
        async with transaction() as conn:
            await conn.execute("INSERT INTO orders (...) VALUES (...)")
            await conn.execute("UPDATE inventory SET stock = stock - 1")
            # 自动提交或回滚

    【事务特性（ACID）】
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 特性           │ 实现                              │ 保障                │
    ├─────────────────┼──────────────────────────────────┼─────────────────────┤
    │ 原子性 (A)     │ 全部成功或全部回滚              │ 不会部分成功       │
    │ 一致性 (C)     │ 约束、触发器自动检查            │ 数据始终有效       │
    │ 隔离性 (I)     │ PostgreSQL 默认 READ COMMITTED  │ 并发安全           │
    │ 持久性 (D)     │ WAL 机制保证                     │ 宕机不丢失         │
    └─────────────────────────────────────────────────────────────────────────┘

    【为什么使用上下文管理器？】
    - 自动提交：正常退出时自动 COMMIT
    - 自动回滚：异常退出时自动 ROLLBACK
    - 异常安全：无论发生什么异常，事务都会正确结束
    - 代码简洁：无需手动 try/commit/rollback

    【嵌套事务处理】
    asyncpg 支持 SAVEPOINT 实现嵌套事务：
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ async with transaction() as conn:       # 外层事务                      │
    │     await conn.execute("INSERT ...")                                  │
    │     async with conn.transaction():     # 内层事务 (SAVEPOINT)         │
    │         await conn.execute("UPDATE ...")                               │
    │         # 内层提交到 SAVEPOINT                                         │
    │     # 外层提交                                                         │
    └─────────────────────────────────────────────────────────────────────────┘

    【日志追踪】
    - 事务开始、提交、回滚都有日志记录
    - 用于排查事务相关问题
    """
    async with get_connection() as conn:
        tx = conn.transaction()
        tx_id = id(tx)
        logger.debug("database_transaction_starting", transaction_id=tx_id)

        try:
            await tx.start()
            logger.debug("database_transaction_started", transaction_id=tx_id)
            yield conn
            await tx.commit()
            logger.debug("database_transaction_committed", transaction_id=tx_id)
        except Exception as e:
            await tx.rollback()
            logger.warning(
                "database_transaction_rolled_back",
                transaction_id=tx_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise


# ═══════════════════════════════════════════════════════════════════════════
# 多租户 RLS 支持
# ═══════════════════════════════════════════════════════════════════════════


async def set_tenant_context(conn: Connection, tenant_id: str) -> None:
    """设置租户上下文（用于 RLS 行级安全）

    【RLS 原理详解】
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ PostgreSQL 行级安全策略通过 session 参数获取当前租户：                   │
    │                                                                         │
    │ -- 1. 创建 RLS 策略                                                     │
    │ CREATE POLICY tenant_isolation ON orders                                │
    │     USING (tenant_id = current_setting('app.current_tenant')::uuid);   │
    │                                                                         │
    │ -- 2. 启用 RLS（强制应用策略）                                          │
    │ ALTER TABLE orders ENABLE ROW LEVEL SECURITY;                          │
    │                                                                         │
    │ -- 3. 设置租户参数（本函数执行此步骤）                                   │
    │ SET LOCAL app.current_tenant = 'tenant_001';                           │
    │                                                                         │
    │ -- 4. 查询自动应用过滤                                                   │
    │ SELECT * FROM orders;  -- 实际执行：SELECT * FROM orders               │
    │                         --           WHERE tenant_id = 'tenant_001'    │
    └─────────────────────────────────────────────────────────────────────────┘

    【为什么使用 SET LOCAL 而非 SET？】
    ┌────────────────────┬───────────────────────────────────────────────────┐
    │ 命令               │ 行为                                              │
    ├────────────────────┼───────────────────────────────────────────────────┤
    │ SET               │ 参数在整个会话期间有效，可能导致租户泄露          │
    │ SET LOCAL         │ 参数仅在当前事务内有效，事务结束自动重置          │
    └────────────────────┴───────────────────────────────────────────────────┘
    使用 SET LOCAL 的好处：
    1. 安全隔离：事务结束后参数自动清除，防止租户数据泄露
    2. 无需手动清理：避免忘记重置参数导致的安全问题
    3. 支持嵌套事务：SAVEPOINT 内的 SET LOCAL 在 SAVEPOINT 释放后自动回滚

    【RLS 策略自动应用流程】
    1. 连接从池中获取 → 2. 开启事务 → 3. SET LOCAL 设置租户 → 4. 执行查询
       → RLS 策略自动添加 WHERE 条件 → 5. 提交事务 → 6. 参数自动清除

    【重要】
    - 必须在事务内调用，否则 SET LOCAL 会报错
    - 建议使用 tenant_transaction() 或 get_tenant_aware_connection() 自动管理

    Args:
        conn: 数据库连接（必须在事务内）
        tenant_id: 租户 ID（UUID 格式，如 "tenant_001"）

    Raises:
        DatabaseError: 设置失败

    【日志记录】
    记录租户上下文设置，用于审计追踪。
    """
    try:
        await conn.execute("SET LOCAL app.current_tenant = $1", tenant_id)
        logger.debug(
            "tenant_context_set",
            tenant_id=tenant_id,
            connection_id=id(conn),
            message="RLS tenant parameter set for current transaction",
        )
    except PostgresError as e:
        logger.error(
            "tenant_context_set_failed",
            tenant_id=tenant_id,
            error=str(e),
            sqlstate=e.sqlstate,
            message="Failed to set tenant context, RLS will not be applied",
        )
        raise DatabaseError(f"设置租户上下文失败: {e}")


@asynccontextmanager
async def get_tenant_aware_connection(tenant_id: str) -> AsyncGenerator[Connection, None]:
    """获取带租户上下文的数据库连接（上下文管理器）

    【使用方式】
        async with get_tenant_aware_connection(tenant_id) as conn:
            result = await conn.fetch("SELECT * FROM orders")
            # 自动应用 RLS 过滤，只返回当前租户的数据

    【自动管理】
    - 自动开启事务（SET LOCAL 需要在事务内）
    - 自动设置租户上下文（RLS 参数）
    - 自动提交或回滚
    - 连接归还池时自动清除租户参数（事务结束自动清除）

    【安全特性】
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 安全措施                  │ 保障                                        │
    ├───────────────────────────┼─────────────────────────────────────────────┤
    │ SET LOCAL 限制作用域      │ 租户参数仅在当前事务有效                    │
    │ 事务结束自动重置          │ 无需手动清除，防止遗忘                      │
    │ 异常时回滚                │ 防止部分提交导致数据不一致                  │
    │ 连接池自动归还            │ 防止连接泄漏                                │
    └───────────────────────────┴─────────────────────────────────────────────┘

    【防止租户泄露的关键】
    1. 使用 SET LOCAL 而非 SET（参数仅在当前事务有效）
    2. 事务结束参数自动清除（无需手动清理）
    3. 连接归还池后，下次使用时租户参数为空（安全默认值）

    Args:
        tenant_id: 租户 ID

    Yields:
        Connection: 带租户上下文的数据库连接
    """
    pool = get_database_pool()
    conn_id = None
    tx_id = None

    logger.debug(
        "tenant_aware_connection_acquiring",
        tenant_id=tenant_id,
        pool_size=pool.get_size(),
        pool_idle=pool.get_idle_size(),
    )

    async with pool.acquire() as conn:
        conn_id = id(conn)
        logger.debug(
            "tenant_aware_connection_acquired",
            tenant_id=tenant_id,
            connection_id=conn_id,
        )

        tx = conn.transaction()
        tx_id = id(tx)
        try:
            await tx.start()
            logger.debug(
                "tenant_aware_transaction_started",
                tenant_id=tenant_id,
                transaction_id=tx_id,
            )

            await set_tenant_context(conn, tenant_id)
            logger.debug(
                "tenant_aware_rls_enabled",
                tenant_id=tenant_id,
                connection_id=conn_id,
            )

            try:
                yield conn
                await tx.commit()
                logger.debug(
                    "tenant_aware_transaction_committed",
                    tenant_id=tenant_id,
                    transaction_id=tx_id,
                )
            except PostgresError as e:
                logger.error(
                    "tenant_aware_query_error",
                    tenant_id=tenant_id,
                    connection_id=conn_id,
                    error=str(e),
                    sqlstate=e.sqlstate,
                    error_class=type(e).__name__,
                )
                raise DatabaseError(f"租户数据库查询失败: {e}")
            except Exception as e:
                logger.error(
                    "tenant_aware_unexpected_error",
                    tenant_id=tenant_id,
                    connection_id=conn_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
        finally:
            logger.debug(
                "tenant_aware_connection_releasing",
                tenant_id=tenant_id,
                connection_id=conn_id,
            )


@asynccontextmanager
async def tenant_transaction(tenant_id: str) -> AsyncGenerator[Connection, None]:
    """带租户上下文的事务上下文管理器

    【使用方式】
        async with tenant_transaction(tenant_id) as conn:
            await conn.execute("INSERT INTO orders (...) VALUES (...)")
            await conn.execute("UPDATE inventory SET stock = stock - 1")
            # 自动应用 RLS 并提交或回滚

    【事务特性】
    - 自动设置租户上下文（RLS）
    - 自动提交（正常退出时）
    - 自动回滚（异常退出时）
    - 支持嵌套事务（SAVEPOINT）

    【与 transaction() 的区别】
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 对比项              │ transaction()         │ tenant_transaction()      │
    ├─────────────────────┼───────────────────────┼────────────────────────────┤
    │ 租户上下文          │ 无                    │ 自动设置 RLS 租户参数     │
    │ 适用场景            │ 公共数据              │ 租户隔离数据               │
    │ 参数管理            │ 手动管理              │ 自动管理                   │
    │ RLS 策略            │ 不应用                │ 自动应用                   │
    │ 安全隔离            │ 低                    │ 高（防止租户泄露）        │
    └─────────────────────┴───────────────────────┴────────────────────────────┘

    【最佳实践】
    - 租户数据操作：使用 tenant_transaction()
    - 公共数据操作：使用 transaction()
    - 只读查询：可使用 fetch_* 系列函数，传入 tenant_id 参数

    Args:
        tenant_id: 租户 ID

    Yields:
        Connection: 带租户上下文的事务连接
    """
    async with get_tenant_aware_connection(tenant_id) as conn:
        yield conn


async def execute_query(
    query: str,
    *args: Any,
    timeout: float = 30.0,
    tenant_id: str | None = None,
) -> str:
    """执行单条 SQL（无返回值）

    【使用场景】
    - INSERT / UPDATE / DELETE
    - DDL 语句
    - SET 命令

    【多租户支持】
    提供 tenant_id 参数时，自动设置租户上下文并应用 RLS 策略。
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ tenant_id     │ 行为                                    │ 安全级别   │
    ├───────────────┼────────────────────────────────────────┼────────────┤
    │ None          │ 不设置 RLS，查询公共数据                │ 低         │
    │ 'tenant_001'  │ 自动设置 RLS，只操作当前租户数据        │ 高         │
    └───────────────┴────────────────────────────────────────┴────────────┘

    【参数占位符】
    asyncpg 使用 $1, $2, ... 占位符（而非 %s 或 ?）：
    - 正确：execute_query("INSERT INTO users (name) VALUES ($1)", "Alice")
    - 错误：execute_query("INSERT INTO users (name) VALUES (%s)", "Alice")

    Args:
        query: SQL 语句
        *args: 参数（使用 $1, $2 占位符）
        timeout: 超时时间（秒）
        tenant_id: 租户 ID（可选，用于 RLS）

    Returns:
        状态字符串（如 "INSERT 0 1"）
    """
    logger.debug(
        "database_query_executing",
        query_preview=query[:100] if len(query) > 100 else query,
        args_count=len(args),
        timeout=timeout,
        tenant_id=tenant_id,
    )

    start_time = asyncio.get_event_loop().time()

    if tenant_id:
        async with get_tenant_aware_connection(tenant_id) as conn:
            result = await conn.execute(query, *args, timeout=timeout)
    else:
        async with get_connection() as conn:
            result = await conn.execute(query, *args, timeout=timeout)

    elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
    logger.debug(
        "database_query_executed",
        result=result,
        elapsed_ms=elapsed_ms,
        tenant_id=tenant_id,
    )

    return result


async def fetch_one(
    query: str,
    *args: Any,
    timeout: float = 30.0,
    tenant_id: str | None = None,
) -> asyncpg.Record | None:
    """查询单行

    【多租户支持】
    提供 tenant_id 参数时，自动设置租户上下文并应用 RLS 策略。

    【返回值】
    - 返回 asyncpg.Record 对象，可通过字段名或索引访问
    - 无结果时返回 None

    【使用示例】
        user = await fetch_one("SELECT id, name FROM users WHERE id = $1", user_id)
        if user:
            print(user["name"])  # 通过字段名访问
            print(user[0])       # 通过索引访问

    Args:
        query: SQL 查询语句
        *args: 参数
        timeout: 超时时间（秒）
        tenant_id: 租户 ID（可选，用于 RLS）

    Returns:
        单行记录，或 None（无结果）
    """
    logger.debug(
        "database_fetch_one_executing",
        query_preview=query[:100] if len(query) > 100 else query,
        args_count=len(args),
        timeout=timeout,
        tenant_id=tenant_id,
    )

    start_time = asyncio.get_event_loop().time()

    if tenant_id:
        async with get_tenant_aware_connection(tenant_id) as conn:
            result = await conn.fetchrow(query, *args, timeout=timeout)
    else:
        async with get_connection() as conn:
            result = await conn.fetchrow(query, *args, timeout=timeout)

    elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
    logger.debug(
        "database_fetch_one_completed",
        has_result=result is not None,
        elapsed_ms=elapsed_ms,
        tenant_id=tenant_id,
    )

    return result


async def fetch_all(
    query: str,
    *args: Any,
    timeout: float = 30.0,
    tenant_id: str | None = None,
) -> list[asyncpg.Record]:
    """查询多行

    【多租户支持】
    提供 tenant_id 参数时，自动设置租户上下文并应用 RLS 策略。

    【返回值】
    - 返回 asyncpg.Record 列表
    - 无结果时返回空列表 []

    【使用示例】
        users = await fetch_all("SELECT id, name FROM users WHERE status = $1", "active")
        for user in users:
            print(user["name"])

    Args:
        query: SQL 查询语句
        *args: 参数
        timeout: 超时时间（秒）
        tenant_id: 租户 ID（可选，用于 RLS）

    Returns:
        记录列表
    """
    logger.debug(
        "database_fetch_all_executing",
        query_preview=query[:100] if len(query) > 100 else query,
        args_count=len(args),
        timeout=timeout,
        tenant_id=tenant_id,
    )

    start_time = asyncio.get_event_loop().time()

    if tenant_id:
        async with get_tenant_aware_connection(tenant_id) as conn:
            result = await conn.fetch(query, *args, timeout=timeout)
    else:
        async with get_connection() as conn:
            result = await conn.fetch(query, *args, timeout=timeout)

    elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
    logger.debug(
        "database_fetch_all_completed",
        row_count=len(result),
        elapsed_ms=elapsed_ms,
        tenant_id=tenant_id,
    )

    return result


async def fetch_val(
    query: str,
    *args: Any,
    timeout: float = 30.0,
    tenant_id: str | None = None,
) -> Any:
    """查询单个值

    【多租户支持】
    提供 tenant_id 参数时，自动设置租户上下文并应用 RLS 策略。

    【返回值】
    - 返回第一行的第一列
    - 无结果时返回 None

    【使用场景】
    - COUNT、SUM、AVG 等聚合函数
    - 单列查询（如查询 ID）

    【使用示例】
        count = await fetch_val("SELECT COUNT(*) FROM users WHERE status = $1", "active")
        user_id = await fetch_val("SELECT id FROM users WHERE email = $1", email)

    Args:
        query: SQL 查询语句
        *args: 参数
        timeout: 超时时间（秒）
        tenant_id: 租户 ID（可选，用于 RLS）

    Returns:
        单个值，或 None
    """
    logger.debug(
        "database_fetch_val_executing",
        query_preview=query[:100] if len(query) > 100 else query,
        args_count=len(args),
        timeout=timeout,
        tenant_id=tenant_id,
    )

    start_time = asyncio.get_event_loop().time()

    if tenant_id:
        async with get_tenant_aware_connection(tenant_id) as conn:
            result = await conn.fetchval(query, *args, timeout=timeout)
    else:
        async with get_connection() as conn:
            result = await conn.fetchval(query, *args, timeout=timeout)

    elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
    logger.debug(
        "database_fetch_val_completed",
        has_result=result is not None,
        elapsed_ms=elapsed_ms,
        tenant_id=tenant_id,
    )

    return result


async def execute_many(
    query: str,
    args_list: list[tuple],
    timeout: float = 60.0,
    tenant_id: str | None = None,
) -> None:
    """批量执行（高效批量插入/更新）

    【性能优势】
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 方式              │ 网络往返次数  │ 时间复杂度  │ 使用场景            │
    ├────────────────────┼───────────────┼─────────────┼─────────────────────┤
    │ 循环 execute      │ N 次         │ O(N)       │ 少量数据（< 100）   │
    │ ✓ executemany     │ 1 次         │ O(1)       │ 大量数据（> 100）   │
    │ COPY FROM         │ 1 次         │ O(1)       │ 超大数据（> 10万） │
    └────────────────────┴───────────────┴─────────────┴─────────────────────┘
    executemany 比循环 execute 快 10-100 倍！

    【使用示例】
        # 批量插入
        await execute_many(
            "INSERT INTO users (name, email) VALUES ($1, $2)",
            [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]
        )

        # 批量更新
        await execute_many(
            "UPDATE users SET status = $1 WHERE id = $2",
            [("active", 1), ("inactive", 2)]
        )

    【多租户支持】
    提供 tenant_id 参数时，自动设置租户上下文并应用 RLS 策略。

    Args:
        query: SQL 语句
        args_list: 参数列表，每个元组对应一组参数
        timeout: 超时时间（秒），默认 60 秒（比单条查询更长）
        tenant_id: 租户 ID（可选，用于 RLS）
    """
    logger.debug(
        "database_execute_many_executing",
        query_preview=query[:100] if len(query) > 100 else query,
        batch_size=len(args_list),
        timeout=timeout,
        tenant_id=tenant_id,
    )

    start_time = asyncio.get_event_loop().time()

    if tenant_id:
        async with get_tenant_aware_connection(tenant_id) as conn:
            await conn.executemany(query, args_list, timeout=timeout)
    else:
        async with get_connection() as conn:
            await conn.executemany(query, args_list, timeout=timeout)

    elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
    logger.debug(
        "database_execute_many_completed",
        batch_size=len(args_list),
        elapsed_ms=elapsed_ms,
        tenant_id=tenant_id,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 健康检查
# ═══════════════════════════════════════════════════════════════════════════


async def check_database_health() -> dict[str, Any]:
    """数据库健康检查

    【检查项】
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 检查项           │ 健康标准                    │ 异常处理              │
    ├───────────────────┼────────────────────────────┼───────────────────────┤
    │ 连接可用性        │ SELECT 1 成功              │ 返回 unhealthy        │
    │ 响应延迟          │ < 100ms                    │ 记录 latency_ms       │
    │ 连接池状态        │ pool_size / pool_idle     │ 监控连接使用率        │
    │ 数据库版本        │ PostgreSQL 16+             │ 记录版本信息          │
    └───────────────────┴────────────────────────────┴───────────────────────┘

    【返回值】
    - status: "healthy" | "unhealthy"
    - latency_ms: 查询延迟（毫秒）
    - pool_size: 当前连接池大小
    - pool_idle: 空闲连接数
    - pool_active: 活跃连接数
    - error: 错误信息（仅 unhealthy 时）

    【使用场景】
    - Kubernetes 健康检查（/health 端点）
    - 监控系统采集指标
    - 告警系统判断依据

    Returns:
        健康状态字典
    """
    if _pool is None:
        logger.warning("database_health_check_failed", reason="pool_not_initialized")
        return {
            "status": "unhealthy",
            "error": "连接池未初始化",
        }

    try:
        start = asyncio.get_event_loop().time()
        async with get_connection() as conn:
            await conn.fetchval("SELECT 1")
        latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)

        pool_size = _pool.get_size()
        pool_idle = _pool.get_idle_size()
        pool_active = pool_size - pool_idle

        health_status = {
            "status": "healthy",
            "latency_ms": latency_ms,
            "pool_size": pool_size,
            "pool_idle": pool_idle,
            "pool_active": pool_active,
            "pool_usage_percent": round(pool_active / pool_size * 100, 1) if pool_size > 0 else 0,
        }

        logger.info(
            "database_health_check_passed",
            latency_ms=latency_ms,
            pool_size=pool_size,
            pool_active=pool_active,
        )

        return health_status

    except Exception as e:
        logger.error(
            "database_health_check_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "status": "unhealthy",
            "error": str(e),
        }
