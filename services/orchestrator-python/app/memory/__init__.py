"""记忆模块 - 会话存储、摘要生成、长时记忆

该模块提供三层记忆架构：

┌────────────────┬─────────────────────────┬─────────────────────────────┐
│ 记忆类型       │ 作用                    │ 实现方式                    │
├────────────────┼─────────────────────────┼─────────────────────────────┤
│ 会话存储       │ 当前会话的对话历史      │ Redis List                  │
│ (SessionStore) │ • 支持多轮对话上下文    │                             │
│                │ • 滑动窗口限制长度      │                             │
│                │ • 摘要压缩早期对话      │                             │
├────────────────┼─────────────────────────┼─────────────────────────────┤
│ 摘要生成       │ 压缩对话历史            │ LLM / 提取式                │
│ (SummaryGen)   │ • 保留关键信息          │                             │
│                │ • 节省 token            │                             │
├────────────────┼─────────────────────────┼─────────────────────────────┤
│ 长时记忆       │ 跨会话的历史记忆        │ pgvector                    │
│ (LongTerm)     │ • 语义检索相关对话      │                             │
│                │ • 时间衰减权重          │                             │
│                │ • 持久化存储            │                             │
└────────────────┴─────────────────────────┴─────────────────────────────┘

协作关系：
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
                └──> Chat API
                        │
                        ▼
                    retrieve_relevant_memories()  ← 长时记忆召回
                        │
                        ▼
                    Agent 执行
                        │
                        ▼
                    save_to_long_term_memory()  ← 长时记忆存储
"""

from app.memory.session_store import (
    SessionStore,
    get_session_store,
)
from app.memory.summary_generator import (
    SummaryGenerator,
    SummaryConfig,
    get_summary_generator,
    create_summary_message,
)
from app.memory.long_term_memory import (
    LongTermMemoryStore,
    MemoryEntry,
    get_long_term_memory,
)
from app.memory.memory_manager import (
    save_to_long_term_memory,
    retrieve_relevant_memories,
    format_memories_for_context,
    extract_key_entities_from_tool_results,
)
from app.memory.checkpoint_store import (
    CheckpointStore,
    get_checkpoint_store,
)

__all__ = [
    # 会话存储
    "SessionStore",
    "get_session_store",
    # 摘要生成
    "SummaryGenerator",
    "SummaryConfig",
    "get_summary_generator",
    "create_summary_message",
    # 长时记忆
    "LongTermMemoryStore",
    "MemoryEntry",
    "get_long_term_memory",
    # 记忆管理器
    "save_to_long_term_memory",
    "retrieve_relevant_memories",
    "format_memories_for_context",
    "extract_key_entities_from_tool_results",
    # Checkpoint
    "CheckpointStore",
    "get_checkpoint_store",
]