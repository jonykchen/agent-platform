"""
【核心概念】LangGraph Checkpoint 机制
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LangGraph 的 Checkpoint 用于实现：
1. 暂停/恢复：Agent 执行可以暂停（如等待审批），之后恢复继续
2. 状态持久化：防止进程崩溃导致任务丢失
3. 时间旅行：可以回退到历史状态重新执行

【问题背景】
- Agent 任务可能需要等待人工审批（数小时甚至数天）
- 服务重启时需要恢复未完成的任务
- 需要支持任务的中断和恢复

【技术选型】Checkpoint 存储方案对比
┌────────────────────┬───────────────┬───────────────┬───────────────┐
│ 方案               │ 持久性        │ 性能          │ TTL 支持      │
├────────────────────┼───────────────┼───────────────┼───────────────┤
│ 内存 MemorySaver   │ ❌ 重启丢失   │ 最快          │ ❌ 无         │
│ ✓ Redis            │ ✅ 持久化     │ 快            │ ✅ 自动过期   │
│ PostgreSQL         │ ✅ 强持久化   │ 中            │ ❌ 需手动清理 │
│ 文件系统           │ ✅ 持久化     │ 慢            │ ❌ 需手动清理 │
└────────────────────┴───────────────┴───────────────┴───────────────┘

【决策依据】选择 Redis 的原因：
1. TTL 自动过期：审批超时的 Checkpoint 自动清理，无需维护定时任务
2. 高性能：读写延迟 <1ms，适合高频状态更新
3. 简单：无需数据库表设计，直接使用 key-value 结构
4. 项目已有 Redis：复用现有基础设施，无额外运维成本

【心跳续期机制】
┌─────────────────────────────────────────────────────────────────────┐
│ 场景：审批等待时间 > Checkpoint TTL（默认 2 小时）                    │
│                                                                     │
│ 问题：如果审批需要 3 小时，Checkpoint 会过期丢失                      │
│ 解决：后台心跳任务定期续期 TTL                                        │
│                                                                     │
│ 流程：                                                              │
│   1. 任务进入 approval_wait 节点                                    │
│   2. start_heartbeat() 启动后台心跳任务                              │
│   3. 每 60s 执行 Redis EXPIRE 续期 TTL                              │
│   4. 审批完成后 stop_heartbeat() 停止心跳                            │
│   5. Checkpoint 继续执行后续步骤                                     │
│                                                                     │
│ 时序图：                                                            │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐                   │
│   │ Agent    │     │ Redis    │     │ 心跳任务  │                   │
│   └────┬─────┘     └────┬─────┘     └────┬─────┘                   │
│        │                │                │                          │
│        │ save(checkpoint, TTL=2h)       │                          │
│        │───────────────>│                │                          │
│        │                │                │                          │
│        │ start_heartbeat()              │                          │
│        │───────────────────────────────>│                          │
│        │                │                │                          │
│        │                │   EXPIRE +2h   │ (每 60s)                 │
│        │                │<───────────────│                          │
│        │                │                │                          │
│        │ stop_heartbeat()               │                          │
│        │───────────────────────────────>│                          │
│        │                │                │                          │
└─────────────────────────────────────────────────────────────────────┘

【参数推荐】
- 默认 TTL: 7200s（2小时）→ 审批通常在 2 小时内完成
- 心跳间隔: 60s → 平衡性能和可靠性，避免频繁 Redis 操作
- 心跳超时: 10s → Redis 操作通常 <100ms，10s 是安全裕量

【演进历史】
- v1.0: 使用 MemorySaver，服务重启任务丢失
- v2.0: 切换到 RedisSaver，支持持久化
- v2.1: 添加心跳续期机制（当前版本）

【注意事项】
- Checkpoint 数据包含完整的 Agent 状态，可能较大（KB 级别）
- Redis 内存成本：假设每个 Checkpoint 10KB，1 万个待处理任务约 100MB
- 心跳任务存储在内存中，服务重启需要重新启动心跳

【相关文件】
- app/graph/nodes/approval_wait.py: 审批等待节点，调用心跳方法
- app/api/approval_callback.py: 审批回调处理，恢复 Checkpoint
"""

import asyncio
import json
from datetime import datetime

import redis.asyncio as redis
import structlog

from app.core.config import config

logger = structlog.get_logger()


class CheckpointStore:
    """Redis Checkpoint 存储

    【职责边界】
    本类专注于 Checkpoint 的存储和生命周期管理，不负责：
    - 业务逻辑（如审批流程判断）→ 由 LangGraph 节点处理
    - 序列化格式设计 → 由调用方决定 checkpoint dict 结构

    【核心功能】
    1. 持久化 LangGraph 状态 → save() / load()
    2. 支持审批流程 → update_approval_status() / list_pending()
    3. 心跳续期机制 → start_heartbeat() / stop_heartbeat()

    【线程安全】
    - _client: 延迟初始化，一旦创建后只读，线程安全
    - _heartbeat_tasks: 使用 asyncio 协程，同一事件循环内线程安全
    - 如果需要在多事件循环中使用，应创建多个 CheckpointStore 实例

    【Redis 键设计】
    - Checkpoint 数据: checkpoint:{run_id}
    - 命名空间: 无前缀区分（单租户设计）
    - 未来扩展: 可添加 tenant_id 前缀支持多租户隔离
    """

    def __init__(self, redis_url: str | None = None):
        """初始化 Checkpoint 存储

        Args:
            redis_url: Redis 连接 URL，格式：redis://[:password@]host:port/db
                      默认从配置读取 config.redis_url

        Note:
            实际连接延迟到第一次调用 _get_client() 时建立，
            避免初始化时就阻塞等待网络连接。
        """
        self.redis_url = redis_url or config.redis_url
        self._client: redis.Redis | None = None
        # 心跳任务字典：{checkpoint_id: asyncio.Task}
        # 存储所有活跃的心跳任务，用于：
        # 1. stop_heartbeat() 时快速取消
        # 2. close() 时批量清理
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}

    async def _get_client(self) -> redis.Redis:
        """获取 Redis 客户端（延迟初始化）

        【延迟初始化的原因】
        1. 避免导入时阻塞：模块导入不应触发网络连接
        2. 容错性：即使 Redis 启动失败，应用可以启动（健康检查再报错）
        3. 连接复用：单例模式，整个实例生命周期内复用同一连接

        Returns:
            redis.Redis: 已连接的 Redis 客户端
        """
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,  # 自动解码为 str，避免 bytes 处理
            )
        return self._client

    async def close(self):
        """关闭连接并停止所有心跳任务

        【清理顺序】
        1. 先停止心跳任务（避免后续操作）
        2. 再关闭 Redis 连接

        【调用时机】
        - 应用关闭时（FastAPI shutdown 事件）
        - 单元测试 tear down
        - 优雅关闭信号处理
        """
        # 停止所有心跳任务
        await self._stop_all_heartbeats()

        if self._client:
            await self._client.aclose()
            self._client = None

    def _key(self, run_id: str) -> str:
        """生成 Redis 键

        【键命名规范】
        格式: checkpoint:{run_id}

        为什么使用冒号分隔？
        - Redis 官方推荐的命名约定
        - 支持 SCAN 命令按前缀查找（如 checkpoint:*）
        - 便于理解和管理

        Args:
            run_id: 运行实例 ID（Agent 执行的唯一标识）

        Returns:
            str: Redis 键名
        """
        return f"checkpoint:{run_id}"

    async def save(self, run_id: str, checkpoint: dict, ttl_seconds: int = 7200) -> None:
        """保存 Checkpoint

        【数据结构设计】
        checkpoint_data = {
            "run_id": str,           # 冗余存储，方便调试和扫描
            "checkpoint": dict,      # LangGraph 状态快照
            "created_at": ISO8601,   # 创建时间，用于审计和监控
        }

        为什么不直接存储 checkpoint？
        - 添加元数据便于运维（如查看创建时间）
        - scan 时无需反序列化完整 checkpoint

        Args:
            run_id: 运行实例 ID，全局唯一
            checkpoint: LangGraph 状态快照，结构由调用方定义
            ttl_seconds: 过期时间，默认 7200s（2 小时）

        【TTL 选择依据】
        - 审批流程通常 2 小时内完成
        - 超时未审批的任务由心跳续期
        - 过期自动清理，避免无限堆积
        """
        client = await self._get_client()
        key = self._key(run_id)

        checkpoint_data = {
            "run_id": run_id,
            "checkpoint": checkpoint,
            "created_at": datetime.utcnow().isoformat(),
        }

        await client.set(key, json.dumps(checkpoint_data), ex=ttl_seconds)

        logger.info(
            "Checkpoint saved",
            run_id=run_id,
            ttl=ttl_seconds,
        )

    async def load(self, run_id: str) -> dict | None:
        """加载 Checkpoint

        【使用场景】
        1. 服务重启后恢复未完成任务
        2. 审批回调后继续执行
        3. 调试时查看任务状态

        【返回值】
        - 存在：返回 checkpoint dict
        - 不存在：返回 None（调用方需处理 None 情况）

        Args:
            run_id: 运行实例 ID

        Returns:
            dict | None: Checkpoint 数据，不存在返回 None

        Note:
            此方法会重置 TTL（读取不影响过期时间）
        """
        client = await self._get_client()
        key = self._key(run_id)

        data = await client.get(key)
        if not data:
            return None

        checkpoint_data = json.loads(data)

        logger.info(
            "Checkpoint loaded",
            run_id=run_id,
            created_at=checkpoint_data.get("created_at"),
        )

        return checkpoint_data.get("checkpoint")

    async def delete(self, run_id: str) -> None:
        """删除 Checkpoint

        【使用场景】
        1. 任务完成后清理（避免占用 Redis 内存）
        2. 任务取消时清理
        3. 测试清理

        【幂等性】
        删除不存在的 key 不会报错，Redis DEL 命令返回 0

        Args:
            run_id: 运行实例 ID
        """
        client = await self._get_client()
        key = self._key(run_id)
        await client.delete(key)
        logger.info("Checkpoint deleted", run_id=run_id)

    async def exists(self, run_id: str) -> bool:
        """检查 Checkpoint 是否存在

        【使用场景】
        1. 审批回调前验证 run_id 有效
        2. 恢复任务前检查是否过期
        3. 防止重复处理

        Args:
            run_id: 运行实例 ID

        Returns:
            bool: True 表示存在且未过期
        """
        client = await self._get_client()
        key = self._key(run_id)
        return await client.exists(key) > 0

    async def list_pending(self, session_id: str | None = None) -> list[dict]:
        """列出待恢复的 Checkpoint

        【使用场景】
        1. 管理后台展示待审批任务
        2. 服务启动时检查未完成任务
        3. 监控告警：待处理任务过多

        【性能注意】
        此方法使用 SCAN 遍历所有 checkpoint 键：
        - 时间复杂度: O(N)，N 为 checkpoint 数量
        - 适用场景: checkpoint 数量 < 1 万
        - 如果数量过大，考虑使用专门的索引（如 Redis Set）

        【过滤条件】
        1. session_id: 可选，按会话过滤
        2. approval_status == "pending": 只返回待审批任务

        Args:
            session_id: 可选，过滤特定会话

        Returns:
            list[dict]: Checkpoint 简要信息列表

        Example:
            >>> store = CheckpointStore()
            >>> pending = await store.list_pending()
            >>> for item in pending:
            ...     print(f"Run {item['run_id']} waiting for approval")
        """
        client = await self._get_client()

        # 扫描所有 checkpoint 键
        pattern = "checkpoint:*"
        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)

        checkpoints = []
        for key in keys:
            data = await client.get(key)
            if data:
                checkpoint_data = json.loads(data)
                checkpoint = checkpoint_data.get("checkpoint", {})

                # 过滤会话
                if session_id and checkpoint.get("session_id") != session_id:
                    continue

                # 检查是否在等待审批
                approval_status = checkpoint.get("approval_status")
                if approval_status == "pending":
                    checkpoints.append({
                        "run_id": checkpoint_data.get("run_id"),
                        "session_id": checkpoint.get("session_id"),
                        "approval_id": checkpoint.get("approval_id"),
                        "created_at": checkpoint_data.get("created_at"),
                    })

        return checkpoints

    async def update_approval_status(
        self,
        run_id: str,
        status: str,
        reviewer_id: str | None = None,
        comment: str | None = None,
    ) -> None:
        """更新审批状态

        【业务流程】
        1. 用户在审批界面点击"通过"或"拒绝"
        2. 前端调用审批回调 API
        3. API 调用此方法更新状态
        4. LangGraph 从 approval_wait 节点恢复执行

        【状态转换】
        pending → approved: 审批通过，任务继续
        pending → rejected: 审批拒绝，任务终止

        【幂等性】
        多次更新同一状态不会报错，但会产生多条日志

        Args:
            run_id: 运行实例 ID
            status: 新状态 (approved/rejected)
            reviewer_id: 审批人 ID，用于审计
            comment: 审批备注，如"风险操作已确认"
        """
        checkpoint = await self.load(run_id)
        if not checkpoint:
            logger.warning("Checkpoint not found for approval update", run_id=run_id)
            return

        checkpoint["approval_status"] = status
        checkpoint["approval_reviewer"] = reviewer_id
        checkpoint["approval_comment"] = comment
        checkpoint["approval_updated_at"] = datetime.utcnow().isoformat()

        await self.save(run_id, checkpoint)

        logger.info(
            "Approval status updated",
            run_id=run_id,
            status=status,
            reviewer_id=reviewer_id,
        )

    async def start_heartbeat(
        self,
        checkpoint_id: str,
        ttl_seconds: int = 7200,
        interval_seconds: int = 60,
    ) -> None:
        """启动 Checkpoint 心跳续期任务

        【核心原理】
        ┌─────────────────────────────────────────────────────────────────┐
        │ 问题：Redis TTL 从 set 时间开始计算，不是从最后访问时间        │
        │                                                                │
        │ 解决：后台任务定期执行 EXPIRE 命令重置 TTL                     │
        │                                                                │
        │ 效果：只要心跳任务存活，Checkpoint 就不会过期                   │
        └─────────────────────────────────────────────────────────────────┘

        【使用场景】
        1. 任务进入 approval_wait 节点时启动
        2. 审批可能需要数小时，远超默认 TTL
        3. 审批完成后停止心跳

        【参数选择】
        - ttl_seconds=7200: 每次续期 2 小时，足够管理员干预
        - interval_seconds=60: 每分钟续期一次，即使错过几次也不会过期
          （最坏情况：连续错过 119 次心跳 = 2 小时后过期）

        【设计权衡】
        为什么不在 load() 时自动续期？
        - load() 可能用于只读场景（如调试），不应改变 TTL
        - 心跳机制显式启动/停止，语义更清晰

        Args:
            checkpoint_id: Checkpoint ID（即 run_id）
            ttl_seconds: TTL 过期时间（秒），默认 7200（2 小时）
            interval_seconds: 心跳间隔（秒），默认 60 秒

        Note:
            - 如果已存在相同 checkpoint_id 的心跳任务，会先停止旧任务
            - 心跳任务在后台异步运行，不阻塞主流程
            - 服务重启后需要重新启动心跳（心跳状态存储在内存）
        """
        # 如果已存在心跳任务，先停止（幂等性保证）
        if checkpoint_id in self._heartbeat_tasks:
            await self.stop_heartbeat(checkpoint_id)

        # 创建心跳任务：后台协程，不阻塞主流程
        task = asyncio.create_task(
            self._heartbeat_loop(checkpoint_id, ttl_seconds, interval_seconds),
            name=f"heartbeat-{checkpoint_id}",  # 任务命名，便于调试
        )
        self._heartbeat_tasks[checkpoint_id] = task

        logger.info(
            "Heartbeat started",
            checkpoint_id=checkpoint_id,
            ttl_seconds=ttl_seconds,
            interval_seconds=interval_seconds,
        )

    async def stop_heartbeat(self, checkpoint_id: str) -> None:
        """停止指定 Checkpoint 的心跳续期任务

        【清理逻辑】
        ┌─────────────────────────────────────────────────────────────────┐
        │ 1. 从 _heartbeat_tasks 字典中移除                               │
        │ 2. 取消 asyncio.Task                                            │
        │ 3. 等待任务结束（捕获 CancelledError）                           │
        │                                                                │
        │ 为什么要等待任务结束？                                           │
        │ - 确保资源释放（如 Redis 连接引用）                              │
        │ - 避免任务在后台继续执行产生副作用                               │
        └─────────────────────────────────────────────────────────────────┘

        【幂等性】
        - 停止不存在的任务：无操作
        - 多次停止同一任务：无副作用

        【调用时机】
        1. 审批完成后（任务继续执行）
        2. 任务取消时
        3. 服务关闭时

        Args:
            checkpoint_id: Checkpoint ID（即 run_id）

        Note:
            如果心跳任务不存在，此方法无操作（幂等性）。
        """
        task = self._heartbeat_tasks.pop(checkpoint_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task  # 等待任务响应取消
            except asyncio.CancelledError:
                pass  # 预期的取消，忽略异常
            logger.info("Heartbeat stopped", checkpoint_id=checkpoint_id)

    async def _heartbeat_loop(
        self,
        checkpoint_id: str,
        ttl_seconds: int,
        interval_seconds: int,
    ) -> None:
        """内部心跳循环

        【执行流程】
        ┌─────────────────────────────────────────────────────────────────┐
        │ while True:                                                     │
        │     await sleep(interval_seconds)  # 先等待，避免立即续期        │
        │     if not exists(key): break     # Checkpoint 被删除，退出     │
        │     await expire(key, ttl)        # 续期 TTL                   │
        │     log.debug("tick")                                          │
        └─────────────────────────────────────────────────────────────────┘

        【为什么先 sleep 再续期？】
        - save() 已设置 TTL，不需要立即续期
        - 避免第一次心跳与 save() 时间太近（浪费资源）

        【异常处理策略】
        ┌────────────────────┬─────────────────────────────────────────────┐
        │ 异常类型           │ 处理方式                                    │
        ├────────────────────┼─────────────────────────────────────────────┤
        │ CancelledError     │ 正常退出（任务被取消）                       │
        │ Checkpoint 不存在  │ 正常退出（任务已删除）                       │
        │ RedisError         │ 记录日志，继续尝试（可能是暂时网络问题）       │
        │ 其他异常           │ 记录日志，继续尝试（避免心跳意外终止）         │
        └────────────────────┴─────────────────────────────────────────────┘

        【为什么不重试 Redis 错误？】
        - 下一次循环会自动重试（interval_seconds 后）
        - 避免复杂的重试逻辑
        - 如果 Redis 持续不可用，Checkpoint 会自然过期

        Args:
            checkpoint_id: Checkpoint ID（即 run_id）
            ttl_seconds: 每次续期的 TTL（秒）
            interval_seconds: 心跳间隔（秒）

        Note:
            此方法为内部实现，不应对外暴露。
        """
        key = self._key(checkpoint_id)

        while True:
            try:
                # 先等待，再续期（save() 已设置初始 TTL）
                await asyncio.sleep(interval_seconds)

                client = await self._get_client()

                # 检查 key 是否存在
                # 场景：任务被删除或已过期，心跳应停止
                if not await client.exists(key):
                    logger.warning(
                        "Heartbeat stopped: checkpoint no longer exists",
                        checkpoint_id=checkpoint_id,
                    )
                    break

                # 续期 TTL：重置过期时间
                await client.expire(key, ttl_seconds)

                logger.debug(
                    "Heartbeat tick: TTL renewed",
                    checkpoint_id=checkpoint_id,
                    ttl_seconds=ttl_seconds,
                )

            except asyncio.CancelledError:
                # 任务被取消（正常退出）
                logger.debug(
                    "Heartbeat cancelled",
                    checkpoint_id=checkpoint_id,
                )
                break

            except redis.RedisError as e:
                # Redis 错误：可能是暂时网络问题，继续尝试
                logger.error(
                    "Heartbeat Redis error, will retry",
                    checkpoint_id=checkpoint_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # 不 break，继续下一次循环

            except Exception as e:
                # 未预期的异常：记录日志，继续尝试
                # 避免心跳意外终止导致 Checkpoint 过期
                logger.exception(
                    "Heartbeat unexpected error, will retry",
                    checkpoint_id=checkpoint_id,
                    error=str(e),
                )
                # 不 break，继续下一次循环

    async def _stop_all_heartbeats(self) -> None:
        """停止所有心跳任务（内部方法）

        【调用时机】
        - close() 方法调用时（服务关闭）
        - 测试 tear down 时

        【实现细节】
        1. 复制 keys 列表（避免遍历时修改字典）
        2. 逐个调用 stop_heartbeat()（利用其幂等性）
        3. 记录日志
        """
        checkpoint_ids = list(self._heartbeat_tasks.keys())
        for checkpoint_id in checkpoint_ids:
            await self.stop_heartbeat(checkpoint_id)

        logger.info("All heartbeats stopped", count=len(checkpoint_ids))


# 全局实例
# 【单例模式】
# - 整个应用共享一个 CheckpointStore 实例
# - 复用 Redis 连接，避免频繁创建连接
# - 心跳任务存储在实例中，单例确保状态一致
_store = None


def get_checkpoint_store() -> CheckpointStore:
    """获取 Checkpoint 存储实例（单例）

    【为什么使用单例？】
    1. Redis 连接复用：避免每个请求创建新连接
    2. 心跳任务管理：心跳状态存储在实例中，需要全局访问
    3. 简化代码：无需在每个地方传递实例

    【线程安全】
    - Python GIL 保护简单的单例初始化
    - 如需更严格的线程安全，可使用 threading.Lock

    Returns:
        CheckpointStore: 全局 Checkpoint 存储实例

    Example:
        >>> store = get_checkpoint_store()
        >>> await store.save("run_123", {"step": 1})
    """
    global _store
    if _store is None:
        _store = CheckpointStore()
    return _store