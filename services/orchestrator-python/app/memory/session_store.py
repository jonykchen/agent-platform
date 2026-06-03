"""Redis 会话存储

管理用户会话历史，支持滑动窗口和摘要压缩。

【核心概念】会话存储 vs 长时记忆
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Agent 平台有两层记忆架构：

┌────────────────┬─────────────────────────┬─────────────────────────────┐
│ 记忆类型       │ 作用                    │ 实现方式                    │
├────────────────┼─────────────────────────┼─────────────────────────────┤
│ 会话存储       │ 当前会话的对话历史      │ Redis List (本模块)         │
│ (SessionStore) │ • 支持多轮对话上下文    │                             │
│                │ • 滑动窗口限制长度      │                             │
│                │ • 24 小时 TTL 自动清理  │                             │
├────────────────┼─────────────────────────┼─────────────────────────────┤
│ 长时记忆       │ 跨会话的历史记忆        │ pgvector (long_term_memory) │
│ (LongTerm)     │ • 语义检索相关对话      │                             │
│                │ • 时间衰减权重          │                             │
│                │ • 持久化存储            │                             │
└────────────────┴─────────────────────────┴─────────────────────────────┘

【为什么需要两层记忆？】
1. 会话存储：短期上下文，保证当前对话连贯（用户刚说了什么）
2. 长时记忆：长期关联，支持跨会话召回（用户上周问了什么）

【协作关系】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

会话存储与摘要生成器协作流程：

    用户消息 ──┬──> SessionStore.append_message()
                │        │
                │        ▼
                │    检查消息数量
                │        │
                │        ▼ (超过阈值)
                │    SummaryGenerator.generate()
                │        │
                │        ▼
                │    替换早期消息为摘要
                │
                └──> thinking 节点处理

协作点：
1. SessionStore 检测消息数量超过阈值
2. 调用 SummaryGenerator 生成摘要
3. 用摘要消息替换早期对话
4. 保持滑动窗口内的消息数量稳定

【技术选型】存储方案对比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Redis List (选择)  │ • O(1) 追加/获取            │ • 无语义检索能力            │
│                    │ • 原生支持 LTRIM 滑动窗口   │ • 单会话数据量有限          │
│                    │ • 自动过期管理              │                             │
│                    │ • 跨进程共享（多 Pod）      │                             │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Redis Stream       │ • 支持消费者组              │ • 复杂度高                  │
│                    │ • 消息 ID 有序              │ • 会话场景不需要消费组      │
│                    │ • 支持消息确认              │ • 过期管理不如 List 简单    │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 数据库存储         │ • 支持复杂查询              │ • 延迟高（磁盘 IO）         │
│ (PostgreSQL)       │ • 数据持久化                │ • 并发压力大                │
│                    │ • 关联业务表                │ • 需要定期清理              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 内存存储           │ • 最快                      │ • 无持久化                  │
│                    │ • 开发简单                  │ • 多 Pod 不共享             │
│                    │                             │ • 重启丢失                  │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择 Redis List 的原因】
1. 会话历史是追加型数据，List 天然适合（RPUSH/LRANGE）
2. LTRIM 一行命令实现滑动窗口，无需额外逻辑
3. TTL 自动过期，无需定时清理任务
4. 多 Pod 共享存储，支持水平扩展

【滑动窗口策略】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

参数配置：
- max_turns = 20（最大保留 20 轮对话）
- TTL = 24 小时（会话自动过期）

【为什么是 20 轮？】
1. Token 预算：
   - 每轮对话约 200-500 tokens
   - 20 轮 = 4000-10000 tokens
   - 加上 System Prompt (4000)、工具定义 (2000)、响应预留 (8000)
   - 总计约 18000-24000 tokens，远低于 128K 上下文窗口

2. 信息密度：
   - 20 轮覆盖大部分客服场景
   - 超过 20 轮时，早期信息对当前决策影响较小
   - 配合摘要压缩可进一步扩展有效窗口

3. 性能考量：
   - 20 轮消息序列化/反序列化开销可忽略
   - Redis 单 Key 存储 40 条消息（20轮 × 2消息）无压力

【为什么是 24 小时 TTL？】
1. 用户行为：大部分客服会话在 1 小时内完成
2. 安全合规：24 小时后自动清理，减少数据留存
3. 存储成本：避免无效会话长期占用内存

【Key 设计原理】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Key 格式：session:{session_id}:history

设计原则：
1. 命名空间隔离：session: 前缀区分其他业务 Key
2. 会话维度：以 session_id 为粒度，支持多会话并行
3. 用途后缀：:history 明确存储内容，便于扩展其他属性

扩展示例：
- session:{session_id}:history    → 对话历史
- session:{session_id}:context    → 会话上下文（用户信息、偏好）
- session:{session_id}:state      → Agent 状态（当前步骤、工具调用）

【参考】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- S-AGENT-03: 输入长度限制（MAX_USER_INPUT_TOKENS = 8000）
- S-AGENT-10: 步数上限（MAX_AGENT_STEPS = 10）
- summary_generator.py: 对话摘要生成
- long_term_memory.py: 跨会话长时记忆
"""

import json
from datetime import datetime, timezone

import redis.asyncio as redis
import structlog

from app.core.config import config

logger = structlog.get_logger()


class SessionStore:
    """Redis 会话存储

    管理用户会话的对话历史，提供：
    - 消息追加（RPUSH）
    - 滑动窗口截断（LTRIM）
    - 自动过期（EXPIRE）

    使用示例：
        store = SessionStore()
        await store.append_message(session_id, "user", "你好")
        history = await store.get_history(session_id)
    """

    def __init__(self, redis_url: str | None = None):
        """初始化会话存储

        Args:
            redis_url: Redis 连接 URL，未提供时使用配置值
        """
        self.redis_url = redis_url or config.redis_url
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        """获取 Redis 客户端（懒加载）"""
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def close(self):
        """关闭 Redis 连接"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _key(self, session_id: str) -> str:
        """生成 Redis 键

        Key 格式：session:{session_id}:history

        Args:
            session_id: 会话 ID

        Returns:
            Redis 键名
        """
        return f"session:{session_id}:history"

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        max_turns: int = 20,
    ) -> None:
        """追加消息到会话历史（集成摘要生成）

        执行流程：
        1. RPUSH 追加新消息
        2. 检查并触发摘要生成（如果超过阈值）
        3. LTRIM 保持滑动窗口（如果摘要未触发）
        4. EXPIRE 设置过期时间

        Args:
            session_id: 会话 ID
            role: 消息角色 (user/assistant/system)
            content: 消息内容
            max_turns: 最大保留轮数（默认 20 轮）
        """
        client = await self._get_client()
        key = self._key(session_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 追加消息
        await client.rpush(key, json.dumps(message))

        # 检查并触发摘要生成（在 LTRIM 之前）
        summary_triggered = await self._trigger_summary_if_needed(session_id, max_turns)

        # 如果摘要未触发，使用传统滑动窗口截断
        if not summary_triggered:
            length = await client.llen(key)
            if length > max_turns * 2:
                await client.ltrim(key, -(max_turns * 2), -1)

        # 设置过期时间（24 小时）
        await client.expire(key, 86400)

        logger.debug(
            "Message appended to session",
            session_id=session_id,
            role=role,
            content_length=len(content),
            summary_triggered=summary_triggered,
        )

    async def _trigger_summary_if_needed(
        self,
        session_id: str,
        max_turns: int,
    ) -> bool:
        """检查并触发摘要生成（内部方法）

        【触发条件】
        1. 消息数量超过 trigger_turns
        2. 每追加一条消息检查一次（避免遗漏）

        【执行流程】
        1. 获取当前消息列表
        2. 检查是否需要摘要
        3. 分离需要摘要和保留的消息
        4. 调用 SummaryGenerator 生成摘要
        5. 用摘要替换早期消息
        6. 重新写入 Redis

        Args:
            session_id: 会话 ID
            max_turns: 最大保留轮数

        Returns:
            是否触发了摘要生成
        """
        try:
            from app.core.config import config
            from app.memory.summary_generator import (
                get_summary_generator,
                create_summary_message,
            )

            if not config.summary_enabled:
                return False

            client = await self._get_client()
            key = self._key(session_id)

            # 获取所有消息
            messages_raw = await client.lrange(key, 0, -1)
            messages = [json.loads(m) for m in messages_raw]

            # 检查是否需要摘要
            generator = get_summary_generator()
            if not generator.should_generate_summary(messages):
                return False

            # 分离需要摘要和保留的消息
            to_summarize, to_preserve = generator.get_messages_to_summarize(messages)

            if not to_summarize:
                return False

            # 生成摘要（带上下文信息）
            context = {
                "session_id": session_id,
                "message_count": len(messages),
            }
            summary_text = await generator.generate(to_summarize, context)

            if not summary_text:
                return False

            # 创建摘要消息
            summary_msg = create_summary_message(summary_text)
            summary_msg["timestamp"] = datetime.now(timezone.utc).isoformat()

            # 重新写入：摘要 + 保留的消息
            # 先删除旧数据
            await client.delete(key)

            # 写入摘要
            await client.rpush(key, json.dumps(summary_msg))

            # 写入保留的消息
            for msg in to_preserve:
                await client.rpush(key, json.dumps(msg))

            # 恢复 TTL
            await client.expire(key, 86400)

            logger.info(
                "summary_generated",
                session_id=session_id,
                summarized_count=len(to_summarize),
                preserved_count=len(to_preserve),
                summary_length=len(summary_text),
            )

            return True

        except Exception as e:
            # 摘要生成失败不影响主流程，记录警告日志
            logger.warning(
                "summary_generation_failed",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    async def get_history(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[dict]:
        """获取会话历史

        Args:
            session_id: 会话 ID
            limit: 限制消息数量（从最新开始）

        Returns:
            消息列表，格式：[{"role": "user/assistant", "content": "..."}]
        """
        client = await self._get_client()
        key = self._key(session_id)

        # 获取消息列表
        if limit:
            messages_raw = await client.lrange(key, -limit, -1)
        else:
            messages_raw = await client.lrange(key, 0, -1)

        messages = [json.loads(m) for m in messages_raw]

        # 移除 timestamp 字段，只返回 role 和 content
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    async def clear(self, session_id: str) -> None:
        """清空会话历史

        用于用户主动结束会话或重置对话。

        Args:
            session_id: 会话 ID
        """
        client = await self._get_client()
        key = self._key(session_id)
        await client.delete(key)
        logger.info("Session cleared", session_id=session_id)

    async def exists(self, session_id: str) -> bool:
        """检查会话是否存在

        Args:
            session_id: 会话 ID

        Returns:
            会话是否存在
        """
        client = await self._get_client()
        key = self._key(session_id)
        return await client.exists(key) > 0

    async def get_session_info(self, session_id: str) -> dict:
        """获取会话信息

        返回会话的元数据，用于监控和调试。

        Args:
            session_id: 会话 ID

        Returns:
            会话信息字典：
            {
                "exists": True,
                "message_count": 10,
                "ttl_seconds": 86400
            }
        """
        client = await self._get_client()
        key = self._key(session_id)

        exists = await client.exists(key) > 0
        if not exists:
            return {"exists": False}

        length = await client.llen(key)
        ttl = await client.ttl(key)

        return {
            "exists": True,
            "message_count": length,
            "ttl_seconds": ttl,
        }


# 全局实例
_store = None


def get_session_store() -> SessionStore:
    """获取会话存储实例（单例）"""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
