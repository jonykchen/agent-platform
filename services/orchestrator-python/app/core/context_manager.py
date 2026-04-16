"""上下文窗口管理器

实现智能截断策略，防止 token 超限：
1. 滑动窗口：保留最近 N 轮对话
2. 摘要压缩：当超过阈值时生成摘要
3. 优先级保留：System > 重要工具结果 > 最近对话

【核心概念】上下文窗口限制
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LLM 有上下文窗口限制：
- GPT-4: 8K/32K/128K tokens
- Qwen-Max: 32K tokens
- GLM-4: 128K tokens

超出限制会导致：
1. API 错误（400 Bad Request）
2. 部分内容被截断（导致信息丢失）
3. 成本增加（大量无效 token）

【技术选型】上下文截断策略对比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 策略               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 滑动窗口 (选择)    │ • 简单高效                  │ • 丢失早期对话              │
│                    │ • 实现成本低                │ • 可能丢失关键信息          │
│                    │ • 保留最近上下文            │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 摘要压缩           │ • 保留关键信息              │ • 需额外 LLM 调用           │
│                    │ • 信息不丢失                │ • 增加延迟和成本            │
│                    │                             │ • 摘要可能不准确            │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 语义检索           │ • 保留相关对话              │ • 需向量数据库              │
│ (RAG 方式)        │ • 动态选择                  │ • 实现复杂                  │
│                    │                             │ • 性能开销                  │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 优先级队列         │ • 关键信息优先              │ • 需定义优先级规则          │
│                    │ • 可定制                    │ • 规则维护复杂              │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择滑动窗口 + 摘要压缩混合的原因】
1. 滑动窗口是第一道防线，快速处理简单超限
2. 摘要压缩作为第二道防线，处理严重超限（如 100+ 轮对话）
3. 两者结合：性能 + 信息保留

【截断优先级】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

优先级从高到低：
1. System Prompt（必须保留，定义 Agent 行为）
2. 最近 N 轮对话（用户期望连贯）
3. 重要工具结果（标记为 important 的）
4. 早期对话摘要

WHY 这个顺序？
- System Prompt 是 Agent 的"大脑"，丢失会导致行为失控
- 最近对话是用户当前关注的，丢失会导致语境断裂
- 工具结果可能包含关键数据（如订单号）
- 早期对话可通过摘要替代

【设计原则】
- 先保留 system prompt（必须）
- 再保留最近 N 轮对话
- 超出部分生成摘要
- 最后保留重要工具结果

【参考】
- S-AGENT-03: 输入长度限制
- S-AGENT-04: 输出完整性校验
"""

from __future__ import annotations

import structlog
from typing import Any

from app.core.config import config
from app.core.token_counter import get_token_counter

logger = structlog.get_logger()


class ContextManager:
    """上下文窗口管理器

    管理对话历史，确保不超过模型上下文窗口限制。

    截断策略优先级：
    1. System Prompt - 始终保留
    2. 最近 N 轮对话 - 滑动窗口
    3. 工具调用结果 - 标记重要的保留
    4. 早期对话 - 压缩为摘要

    使用示例：
        manager = ContextManager(max_tokens=120000)
        truncated = manager.truncate(messages)
    """

    def __init__(
        self,
        max_tokens: int | None = None,
        system_prompt_reserved: int = 4000,
        response_reserved: int = 8000,
        recent_turns: int = 5,
    ):
        """初始化上下文管理器

        Args:
            max_tokens: 最大上下文窗口（默认从 config 读取）
            system_prompt_reserved: System Prompt 预留空间
            response_reserved: 模型响应预留空间
            recent_turns: 保留最近 N 轮对话
        """
        self.max_tokens = max_tokens or getattr(config, "max_context_window_tokens", 128000)
        self.system_prompt_reserved = system_prompt_reserved
        self.response_reserved = response_reserved
        self.recent_turns = recent_turns
        self.counter = get_token_counter()

        # 可用空间
        self.available_tokens = self.max_tokens - self.system_prompt_reserved - self.response_reserved

    def truncate(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        important_tool_results: list[str] | None = None,
    ) -> list[dict]:
        """截断消息列表以适应上下文窗口

        Args:
            messages: 原始消息列表
            system_prompt: 可选的 system prompt
            important_tool_results: 重要工具结果的 call_id 列表

        Returns:
            截断后的消息列表
        """
        if not messages:
            return messages

        # 构建结果列表
        result: list[dict] = []

        # 1. 始终保留 system prompt
        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        # 计算当前 token 数
        current_tokens = self.counter.count_messages(result)

        # 如果只有 system prompt，直接返回
        if len(messages) == 0:
            return result

        # 2. 分离消息类型
        recent_messages = messages[-(self.recent_turns * 2) :]  # 每轮包含 user + assistant
        older_messages = messages[:-(self.recent_turns * 2)] if len(messages) > self.recent_turns * 2 else []

        # 3. 添加最近对话
        for msg in recent_messages:
            msg_tokens = self.counter.count_messages([msg])
            if current_tokens + msg_tokens <= self.available_tokens:
                result.append(msg)
                current_tokens += msg_tokens
            else:
                break

        # 4. 如果仍有空间，添加重要工具结果
        if important_tool_results and current_tokens < self.available_tokens:
            for msg in older_messages:
                if msg.get("role") == "tool" and msg.get("tool_call_id") in important_tool_results:
                    msg_tokens = self.counter.count_messages([msg])
                    if current_tokens + msg_tokens <= self.available_tokens:
                        result.append(msg)
                        current_tokens += msg_tokens

        # 5. 如果仍有空间且有旧消息，生成摘要占位
        if older_messages and current_tokens < self.available_tokens - 500:
            summary = self._generate_summary(older_messages)
            if summary:
                result.insert(1, {  # 插入到 system prompt 之后
                    "role": "system",
                    "content": f"[历史对话摘要]\n{summary}",
                })

        # 检查是否需要截断
        total_tokens = self.counter.count_messages(result)
        if total_tokens > self.max_tokens - self.response_reserved:
            logger.warning(
                "context_still_too_long",
                total_tokens=total_tokens,
                max_tokens=self.max_tokens,
                message_count=len(result),
            )
            # 强制截断：只保留 system prompt 和最后一条用户消息
            result = [result[0]] if result else []
            if messages:
                last_user_msg = next(
                    (m for m in reversed(messages) if m.get("role") == "user"),
                    None,
                )
                if last_user_msg:
                    result.append(last_user_msg)

        logger.info(
            "context_truncated",
            original_count=len(messages),
            truncated_count=len(result),
            original_tokens=self.counter.count_messages(messages),
            truncated_tokens=self.counter.count_messages(result),
        )

        return result

    def _generate_summary(self, messages: list[dict]) -> str | None:
        """生成对话摘要（简单版本）

        生产环境应调用 LLM 生成摘要。
        当前实现为简单的关键信息提取。

        Args:
            messages: 需要摘要的消息列表

        Returns:
            摘要文本
        """
        if not messages:
            return None

        # 提取用户消息中的关键词
        user_messages = [m.get("content", "") for m in messages if m.get("role") == "user"]

        if not user_messages:
            return None

        # 简单摘要：用户提问了什么
        summary_parts = []
        for i, msg in enumerate(user_messages[:5]):  # 最多 5 条
            preview = msg[:50] + "..." if len(msg) > 50 else msg
            summary_parts.append(f"{i+1}. 用户询问: {preview}")

        return "\n".join(summary_parts)

    def get_remaining_tokens(self, messages: list[dict]) -> int:
        """获取剩余可用 token 数

        Args:
            messages: 当前消息列表

        Returns:
            剩余 token 数
        """
        current = self.counter.count_messages(messages)
        remaining = self.max_tokens - current - self.response_reserved
        return max(remaining, 0)

    def needs_truncation(self, messages: list[dict]) -> bool:
        """检查是否需要截断

        Args:
            messages: 当前消息列表

        Returns:
            是否需要截断
        """
        current = self.counter.count_messages(messages)
        return current > self.available_tokens


# 全局实例
_manager: ContextManager | None = None


def get_context_manager() -> ContextManager:
    """获取上下文管理器实例"""
    global _manager
    if _manager is None:
        _manager = ContextManager()
    return _manager


def truncate_context(
    messages: list[dict],
    system_prompt: str | None = None,
) -> list[dict]:
    """便捷函数：截断上下文"""
    return get_context_manager().truncate(messages, system_prompt)
