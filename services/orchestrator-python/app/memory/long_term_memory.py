"""长时记忆存储

使用向量数据库（pgvector）存储对话记忆，支持语义检索。
实现跨会话记忆召回，增强 Agent 的对话能力。

【核心概念】长时记忆的作用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Agent 需要记住用户的历史交互，以提供连贯体验：
- 用户上次问了什么？（订单 ORD-12345 的状态）
- Agent 之前做了什么？（推荐了产品 A）
- 用户偏好是什么？（喜欢简洁回复）

【技术选型】向量存储方案
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ pgvector (选择)    │ • 利用现有 PostgreSQL       │ • 性能不如专业向量库        │
│                    │ • 运维简单                  │ • 百万级以上性能下降        │
│                    │ • 支持混合查询              │                              │
│                    │ • ACID 事务支持             │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Pinecone           │ • 托管服务，无运维          │ • 商业服务，成本高          │
│                    │ • 性能最优                  │ • 数据不在本地              │
│                    │ • 自动扩展                  │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Milvus/Weaviate    │ • 开源自托管                │ • 需要额外部署              │
│                    │ • 性能好                    │ • 运维复杂                  │
│                    │                             │ • 增加系统复杂度            │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 内存存储           │ • 最快                      │ • 无持久化                  │
│                    │ • 开发简单                  │ • 进程重启丢失              │
│                    │                             │ • 不适合生产                │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择 pgvector 的原因】
1. 项目已有 PostgreSQL，无需新增组件
2. 客服场景记忆量有限（用户维度），百万级足够
3. 支持向量 + 结构化数据混合查询（如按 tenant_id 过滤）

【记忆检索策略】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

检索流程：召回 → 时间衰减 → 排序

1. 召回（向量相似度）：
   SELECT * FROM agent_memory
   WHERE tenant_id = :tenant_id
   ORDER BY embedding <=> :query_embedding
   LIMIT 10

2. 时间衰减：
   decayed_score = importance * decay_factor^(days_passed)
   - decay_factor = 0.95（每过一天，权重降 5%）
   - 近期记忆权重更高

3. 排序：
   按 decayed_score 降序返回

【设计原则】
- 记忆粒度：按对话轮次存储，而非单条消息
- 检索策略：语义相似度 + 时间衰减
- 存储内容：用户问题 + Agent 回答摘要 + 关键实体

【参考】
- RAG 设计原则：召回 → 精排 → 重排
- 时间衰减因子：近期记忆权重更高
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class MemoryEntry:
    """记忆条目

    存储单轮对话的记忆，包含：
    - 用户问题
    - Agent 回答摘要
    - 关键实体（订单号、用户ID等）
    - 时间戳和重要性分数
    """

    entry_id: str
    session_id: str
    tenant_id: str
    user_id: str
    user_query: str
    agent_response_summary: str
    key_entities: dict[str, str] = field(default_factory=dict)  # {"order_id": "ORD-123", "user_id": "U001"}
    timestamp: datetime = field(default_factory=datetime.utcnow)
    importance_score: float = 0.5  # 0.0-1.0，由 LLM 评估或规则计算
    embedding: list[float] | None = None  # 向量嵌入（可选）

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "user_query": self.user_query,
            "agent_response_summary": self.agent_response_summary,
            "key_entities": self.key_entities,
            "timestamp": self.timestamp.isoformat(),
            "importance_score": self.importance_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        return cls(
            entry_id=data["entry_id"],
            session_id=data["session_id"],
            tenant_id=data["tenant_id"],
            user_id=data["user_id"],
            user_query=data["user_query"],
            agent_response_summary=data["agent_response_summary"],
            key_entities=data.get("key_entities", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            importance_score=data.get("importance_score", 0.5),
            embedding=data.get("embedding"),
        )


class LongTermMemoryStore:
    """长时记忆存储

    使用 PostgreSQL + pgvector 存储对话记忆，支持：
    1. 向量检索：语义相似度匹配
    2. 时间衰减：近期记忆权重更高
    3. 实体检索：按关键实体查找

    使用示例：
        store = LongTermMemoryStore()
        await store.save(entry)
        memories = await store.retrieve("查询订单状态", tenant_id="tenant_001")
    """

    def __init__(
        self,
        db_url: str | None = None,
        embedding_dim: int = 1536,
        decay_factor: float = 0.95,  # 时间衰减系数
        max_retrieve: int = 10,
    ):
        """初始化长时记忆存储

        Args:
            db_url: 数据库连接 URL
            embedding_dim: 向量维度（与模型匹配）
            decay_factor: 时间衰减因子（每过一天乘以此系数）
            max_retrieve: 最大检索数量
        """
        self.db_url = db_url
        self.embedding_dim = embedding_dim
        self.decay_factor = decay_factor
        self.max_retrieve = max_retrieve
        self._pool = None
        self._embedding_client = None

    async def _get_pool(self):
        """获取数据库连接池"""
        if self._pool is None:
            try:
                from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
                from sqlalchemy.orm import sessionmaker

                engine = create_async_engine(self.db_url or "postgresql+asyncpg://localhost/agent_platform")
                self._pool = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            except ImportError:
                logger.warning("sqlalchemy_not_available", fallback="in_memory")
                self._pool = "in_memory"

        return self._pool

    async def save(self, entry: MemoryEntry) -> str:
        """保存记忆条目

        Args:
            entry: 记忆条目

        Returns:
            保存的条目 ID
        """
        pool = await self._get_pool()

        if pool == "in_memory":
            # 内存存储（开发测试）
            return await self._save_in_memory(entry)

        # PostgreSQL 存储
        async with pool() as session:
            try:
                from sqlalchemy import text

                # 插入记忆
                await session.execute(
                    text("""
                        INSERT INTO agent_memory (
                            entry_id, session_id, tenant_id, user_id,
                            user_query, agent_response_summary, key_entities,
                            timestamp, importance_score, embedding
                        ) VALUES (
                            :entry_id, :session_id, :tenant_id, :user_id,
                            :user_query, :agent_response_summary, :key_entities,
                            :timestamp, :importance_score,
                            :embedding::vector(:dim)
                        )
                    """),
                    {
                        "entry_id": entry.entry_id,
                        "session_id": entry.session_id,
                        "tenant_id": entry.tenant_id,
                        "user_id": entry.user_id,
                        "user_query": entry.user_query,
                        "agent_response_summary": entry.agent_response_summary,
                        "key_entities": json.dumps(entry.key_entities),
                        "timestamp": entry.timestamp,
                        "importance_score": entry.importance_score,
                        "embedding": entry.embedding or [],
                        "dim": self.embedding_dim,
                    },
                )
                await session.commit()

                logger.info(
                    "memory_saved",
                    entry_id=entry.entry_id,
                    session_id=entry.session_id,
                )

                return entry.entry_id

            except Exception as e:
                logger.error("memory_save_failed", error=str(e))
                raise

    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        user_id: str | None = None,
        top_k: int = 10,
        time_decay: bool = True,
    ) -> list[MemoryEntry]:
        """检索相关记忆

        检索策略：
        1. 向量相似度匹配（语义检索）
        2. 时间衰减（近期权重更高）
        3. 租户隔离

        Args:
            query: 用户查询
            tenant_id: 租户 ID
            user_id: 可选，按用户过滤
            top_k: 返回数量
            time_decay: 是否应用时间衰减

        Returns:
            相关记忆列表
        """
        pool = await self._get_pool()

        if pool == "in_memory":
            return await self._retrieve_in_memory(query, tenant_id, user_id, top_k)

        # 获取查询向量
        query_embedding = await self._get_embedding(query)

        async with pool() as session:
            try:
                from sqlalchemy import text

                # 向量检索 + 时间衰减
                sql = text("""
                    SELECT
                        entry_id, session_id, tenant_id, user_id,
                        user_query, agent_response_summary, key_entities,
                        timestamp, importance_score, embedding,
                        1 - (embedding <=> :query_embedding::vector(:dim)) as similarity
                    FROM agent_memory
                    WHERE tenant_id = :tenant_id
                    ORDER BY embedding <=> :query_embedding::vector(:dim)
                    LIMIT :limit
                """)

                if user_id:
                    sql = text("""
                        SELECT
                            entry_id, session_id, tenant_id, user_id,
                            user_query, agent_response_summary, key_entities,
                            timestamp, importance_score, embedding,
                            1 - (embedding <=> :query_embedding::vector(:dim)) as similarity
                        FROM agent_memory
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        ORDER BY embedding <=> :query_embedding::vector(:dim)
                        LIMIT :limit
                    """)

                result = await session.execute(
                    sql,
                    {
                        "query_embedding": query_embedding or [],
                        "dim": self.embedding_dim,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "limit": top_k,
                    },
                )

                entries = []
                for row in result:
                    entry = MemoryEntry(
                        entry_id=row.entry_id,
                        session_id=row.session_id,
                        tenant_id=row.tenant_id,
                        user_id=row.user_id,
                        user_query=row.user_query,
                        agent_response_summary=row.agent_response_summary,
                        key_entities=json.loads(row.key_entities) if row.key_entities else {},
                        timestamp=row.timestamp,
                        importance_score=row.importance_score,
                        embedding=row.embedding,
                    )
                    entries.append(entry)

                # 应用时间衰减
                if time_decay:
                    entries = self._apply_time_decay(entries)

                logger.info(
                    "memory_retrieved",
                    query=query[:50],
                    count=len(entries),
                    tenant_id=tenant_id,
                )

                return entries

            except Exception as e:
                logger.error("memory_retrieve_failed", error=str(e))
                return []

    async def _get_embedding(self, text: str) -> list[float] | None:
        """获取文本的向量嵌入

        Args:
            text: 输入文本

        Returns:
            向量列表
        """
        # 尝试调用 embedding 服务
        try:
            import httpx

            # 使用配置的服务地址（支持动态配置）
            embedding_url = getattr(
                self,
                "_embedding_service_url",
                "http://localhost:8001",
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{embedding_url}/embeddings",
                    json={"input": text, "model": "text-embedding-ada-002"},
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("embedding", [])
        except Exception as e:
            logger.warning("embedding_failed", error=str(e), fallback="zero_vector")

        # 回退：返回零向量（用于开发测试）
        return [0.0] * self.embedding_dim

    def _apply_time_decay(self, entries: list[MemoryEntry]) -> list[MemoryEntry]:
        """应用时间衰减

        按时间重新计算重要性分数：
        importance * decay_factor^(days_passed)

        Args:
            entries: 记忆列表

        Returns:
            排序后的记忆列表
        """
        now = datetime.utcnow()

        for entry in entries:
            days_passed = (now - entry.timestamp).days
            decayed_score = entry.importance_score * (self.decay_factor ** days_passed)
            entry.importance_score = decayed_score

        # 按衰减后分数排序
        entries.sort(key=lambda e: e.importance_score, reverse=True)
        return entries

    # 内存存储（开发测试）
    _in_memory_store: dict[str, list[MemoryEntry]] = {}

    async def _save_in_memory(self, entry: MemoryEntry) -> str:
        """内存存储（开发测试）"""
        tenant_key = f"{entry.tenant_id}:{entry.user_id}"
        if tenant_key not in self._in_memory_store:
            self._in_memory_store[tenant_key] = []
        self._in_memory_store[tenant_key].append(entry)
        return entry.entry_id

    async def _retrieve_in_memory(
        self,
        query: str,
        tenant_id: str,
        user_id: str | None,
        top_k: int,
    ) -> list[MemoryEntry]:
        """内存检索（开发测试）"""
        # 简单关键词匹配
        results = []
        for tenant_key, entries in self._in_memory_store.items():
            if tenant_key.startswith(tenant_id):
                for entry in entries:
                    if query.lower() in entry.user_query.lower():
                        results.append(entry)

        return results[:top_k]


# 全局实例
_store: LongTermMemoryStore | None = None


def get_long_term_memory() -> LongTermMemoryStore:
    """获取长时记忆存储实例（注入依赖）

    自动从配置读取数据库连接、向量维度、衰减系数等参数，
    并设置 embedding 服务地址。
    """
    global _store
    if _store is None:
        from app.core.config import config

        _store = LongTermMemoryStore(
            db_url=config.database_url,
            embedding_dim=config.embedding_dim,
            decay_factor=config.memory_decay_factor,
            max_retrieve=config.memory_retrieve_top_k,
        )
        # 设置 embedding 服务地址（从配置读取）
        _store._embedding_service_url = config.embedding_service_url
    return _store