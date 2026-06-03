"""记忆管理器 - 协调摘要生成和长时记忆

核心职责：
1. 长时记忆存储：每轮对话结束后保存到向量数据库
2. 长时记忆检索：新对话时检索相关历史记忆
3. 记忆格式化：将记忆转换为 Agent 可理解的上下文

【核心概念】长时记忆的作用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Agent 需要记住用户的历史交互，以提供连贯体验：
- 用户上次问了什么？（订单 ORD-12345 的状态）
- Agent 之前做了什么？（推荐了产品 A）
- 用户偏好是什么？（喜欢简洁回复）

【技术选型】记忆存储方案
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
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 内存存储           │ • 最快                      │ • 无持久化                  │
│                    │ • 开发简单                  │ • 进程重启丢失              │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

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

【设计原则】
- 记忆粒度：按对话轮次存储，而非单条消息
- 检索策略：语义相似度 + 时间衰减
- 存储内容：用户问题 + Agent 回答摘要 + 关键实体
- 错误隔离：记忆功能失败不影响主流程

【参考】
- RAG 设计原则：召回 → 精排 → 重排
- 时间衰减因子：近期记忆权重更高
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

import structlog

from app.core.config import config
from app.memory.long_term_memory import (
    MemoryEntry,
    get_long_term_memory,
)

logger = structlog.get_logger()


async def save_to_long_term_memory(
    session_id: str,
    tenant_id: str,
    user_id: str,
    user_query: str,
    agent_response: str,
    key_entities: dict[str, str] | None = None,
) -> str | None:
    """将对话保存到长时记忆

    【触发时机】
    每轮对话结束后（assistant 消息保存时）

    【存储内容】
    - 用户问题
    - Agent 回答摘要（截断过长内容）
    - 关键实体（从上下文提取）
    - 重要性分数（可根据规则计算）

    Args:
        session_id: 会话 ID
        tenant_id: 租户 ID
        user_id: 用户 ID
        user_query: 用户问题
        agent_response: Agent 回复
        key_entities: 关键实体（可选）

    Returns:
        记忆条目 ID（失败返回 None）

    Note:
        存储失败不影响主流程，仅记录警告日志。
    """
    if not config.long_term_memory_enabled:
        return None

    try:
        memory_store = get_long_term_memory()

        # 生成条目 ID
        entry_id = f"mem_{uuid.uuid4().hex[:16]}"

        # 截断过长的响应（保留关键信息）
        response_summary = (
            agent_response[:500] if len(agent_response) > 500 else agent_response
        )

        # 计算重要性分数（基于简单规则）
        importance_score = _calculate_importance(user_query, agent_response)

        # 创建记忆条目
        entry = MemoryEntry(
            entry_id=entry_id,
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            user_query=user_query,
            agent_response_summary=response_summary,
            key_entities=key_entities or {},
            timestamp=datetime.now(timezone.utc),
            importance_score=importance_score,
        )

        # 保存记忆
        saved_id = await memory_store.save(entry)

        logger.info(
            "memory_saved_to_long_term",
            entry_id=saved_id,
            session_id=session_id,
            tenant_id=tenant_id,
            importance=importance_score,
        )

        return saved_id

    except Exception as e:
        # 存储失败不影响主流程
        logger.warning(
            "long_term_memory_save_failed",
            session_id=session_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


async def retrieve_relevant_memories(
    query: str,
    tenant_id: str,
    user_id: str | None = None,
    top_k: int | None = None,
) -> list[MemoryEntry]:
    """检索相关的历史记忆

    【检索时机】
    在 Chat API 加载历史后，注入上下文

    【检索策略】
    1. 向量相似度匹配（语义检索）
    2. 时间衰减（近期记忆权重更高）
    3. 租户隔离

    Args:
        query: 用户当前查询
        tenant_id: 租户 ID
        user_id: 用户 ID（可选，用于个性化）
        top_k: 返回数量（默认使用配置值）

    Returns:
        相关记忆列表（失败返回空列表）

    Note:
        检索失败不影响主流程，返回空列表。
    """
    if not config.long_term_memory_enabled:
        return []

    try:
        memory_store = get_long_term_memory()

        # 使用配置的 top_k 或传入值
        retrieve_count = top_k or config.memory_retrieve_top_k

        memories = await memory_store.retrieve(
            query=query,
            tenant_id=tenant_id,
            user_id=user_id,
            top_k=retrieve_count,
            time_decay=True,
        )

        logger.info(
            "memories_retrieved",
            query_preview=query[:50],
            tenant_id=tenant_id,
            count=len(memories),
        )

        return memories

    except Exception as e:
        # 检索失败不影响主流程
        logger.warning(
            "memory_retrieve_failed",
            query_preview=query[:50],
            tenant_id=tenant_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return []


def format_memories_for_context(memories: list[MemoryEntry]) -> str:
    """格式化记忆为上下文消息

    【格式设计】
    将检索到的记忆转换为系统消息格式：
    ```
    [历史相关记忆]
    1. 用户意图：查询订单 ORD-12345
       处理结果：订单已发货，预计送达时间 2026-05-15
    2. 用户意图：修改收货地址
       处理结果：地址已更新为北京市朝阳区...
    ```

    Args:
        memories: 记忆列表

    Returns:
        格式化的上下文文本
    """
    if not memories:
        return ""

    lines = ["[历史相关记忆]"]
    for i, mem in enumerate(memories[:5], 1):  # 最多显示 5 条
        query_preview = mem.user_query[:100]
        response_preview = mem.agent_response_summary[:100]
        lines.append(f"{i}. 用户意图：{query_preview}")
        lines.append(f"   处理结果：{response_preview}")
        if mem.key_entities:
            entities_str = ", ".join(
                f"{k}:{v}" for k, v in mem.key_entities.items()
            )
            lines.append(f"   关键实体：{entities_str}")

    return "\n".join(lines)


def _calculate_importance(user_query: str, agent_response: str) -> float:
    """计算记忆重要性分数（简单规则）

    【评分规则】
    - 包含订单号/金额等关键实体：+0.3
    - 涉及业务操作（修改/取消等）：+0.2
    - 用户表达强烈情绪：+0.1
    - 基础分数：0.5

    Args:
        user_query: 用户问题
        agent_response: Agent 回复

    Returns:
        重要性分数（0.0-1.0）
    """
    score = 0.5

    # 关键实体检测
    if re.search(r"ORD[-\w]+|订单号|金额|\d+元", user_query):
        score += 0.3

    # 业务操作检测
    if re.search(r"修改|取消|退款|投诉", user_query):
        score += 0.2

    # 情绪强度检测
    if re.search(r"急|快|马上|立刻|非常重要", user_query):
        score += 0.1

    # 限制在 0.0-1.0 范围
    return min(max(score, 0.0), 1.0)


def extract_key_entities_from_tool_results(tool_results: list[dict]) -> dict[str, str]:
    """从工具结果中提取关键实体

    Args:
        tool_results: 工具执行结果列表

    Returns:
        关键实体字典，如 {"order_id": "ORD-123", "amount": "100"}
    """
    entities: dict[str, str] = {}

    for result in tool_results:
        if result.get("status") != "success":
            continue

        result_json = result.get("result_json", "")
        if isinstance(result_json, str):
            try:
                import json

                data = json.loads(result_json)
                # 提取常见实体字段
                for key in ["order_id", "user_id", "amount", "product_id"]:
                    if key in data:
                        entities[key] = str(data[key])
            except json.JSONDecodeError:
                # 从文本中提取
                order_match = re.search(r"ORD[-\w]+", result_json)
                if order_match:
                    entities["order_id"] = order_match.group()

    return entities
