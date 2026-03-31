"""对话摘要生成器

当对话历史超过阈值时，生成摘要替换早期对话。
减少 token 消耗，同时保留关键信息。

【设计原则】
- 摘要粒度：按轮次摘要，而非整体摘要
- 保留关键实体：订单号、用户ID、决策结果
- 触发阈值：对话超过 N 轮时触发

【参考】
- S-AGENT-03: 输入长度限制
- LLM 摘要最佳实践：提取而非压缩
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class SummaryConfig:
    """摘要配置"""

    # 触发阈值：对话超过此轮数时生成摘要
    trigger_turns: int = 10

    # 摘要轮数：每次摘要多少轮对话
    summary_turns: int = 5

    # 保留轮数：保留最近多少轮不摘要
    preserve_turns: int = 3

    # 最大摘要长度（字符）
    max_summary_length: int = 500


class SummaryGenerator:
    """对话摘要生成器

    使用 LLM 生成对话摘要，保留关键信息。

    摘要策略：
    1. 超过阈值时，对早期对话生成摘要
    2. 摘要保留：用户意图 + Agent 决策 + 关键实体
    3. 替换原对话，减少 token 消耗

    使用示例：
        generator = SummaryGenerator()
        summary = await generator.generate(messages)
    """

    def __init__(
        self,
        config: SummaryConfig | None = None,
        llm_client: Any | None = None,
    ):
        """初始化摘要生成器

        Args:
            config: 摘要配置
            llm_client: LLM 客户端（用于生成摘要）
        """
        self.config = config or SummaryConfig()
        self.llm_client = llm_client

    async def generate(self, messages: list[dict], context: dict | None = None) -> str:
        """生成对话摘要

        Args:
            messages: 需要摘要的消息列表
            context: 上下文信息（用于日志）

        Returns:
            摘要文本
        """
        if not messages:
            return ""

        # 如果有 LLM 客户端，调用 LLM 生成摘要
        if self.llm_client:
            return await self._generate_with_llm(messages, context)

        # 回退：提取关键信息
        return self._generate_extractive(messages)

    async def _generate_with_llm(self, messages: list[dict], context: dict | None) -> str:
        """使用 LLM 生成摘要

        Args:
            messages: 消息列表
            context: 上下文

        Returns:
            LLM 生成的摘要
        """
        # 构建摘要提示词
        conversation_text = self._format_messages_for_summary(messages)

        prompt = f"""请对以下对话生成简洁摘要，保留关键信息：

【对话内容】
{conversation_text}

【摘要要求】
1. 提取用户的主要意图和问题
2. 保留关键实体（订单号、用户ID、金额等）
3. 记录 Agent 的主要决策和结论
4. 使用简洁的自然语言
5. 字数控制在 200-300 字

【摘要格式】
- 用户意图：...
- 关键实体：...
- 处理结果：...
"""

        try:
            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="qwen-turbo",  # 使用低成本模型
                max_tokens=300,
                temperature=0.3,  # 低温度，保证一致性
            )

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.info(
                "llm_summary_generated",
                original_messages=len(messages),
                summary_length=len(content),
                context=context,
            )
            return content

        except Exception as e:
            logger.warning("llm_summary_failed", error=str(e), fallback="extractive")
            return self._generate_extractive(messages)

    def _generate_extractive(self, messages: list[dict]) -> str:
        """提取式摘要（回退方案）

        从对话中提取关键信息，无需 LLM。

        Args:
            messages: 消息列表

        Returns:
            提取的摘要
        """
        user_intents: list[str] = []
        key_entities: dict[str, str] = {}
        decisions: list[str] = []

        import re

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                # 提取用户意图（前 50 字符）
                intent_preview = content[:50] + "..." if len(content) > 50 else content
                user_intents.append(intent_preview)

                # 提取实体（订单号、用户ID等）
                order_matches = re.findall(r"ORD[-\w]+", content)
                for order_id in order_matches:
                    key_entities["order_id"] = order_id

                user_matches = re.findall(r"用户[号]?[:\s]?([a-zA-Z0-9]+)", content)
                for user_id in user_matches:
                    key_entities["user_id"] = user_id

            elif role == "assistant":
                # 提取决策关键词
                if "查询成功" in content or "已发货" in content:
                    decisions.append("查询成功")
                elif "审批通过" in content:
                    decisions.append("审批通过")
                elif "操作完成" in content:
                    decisions.append("操作完成")

        # 构建摘要
        parts = []
        if user_intents:
            parts.append(f"用户意图：{', '.join(user_intents[:3])}")
        if key_entities:
            entities_str = ", ".join(f"{k}:{v}" for k, v in key_entities.items())
            parts.append(f"关键实体：{entities_str}")
        if decisions:
            parts.append(f"处理结果：{', '.join(decisions[:3])}")

        summary = "\n".join(parts)
        if len(summary) > self.config.max_summary_length:
            summary = summary[:self.config.max_summary_length] + "..."

        return summary

    def _format_messages_for_summary(self, messages: list[dict]) -> str:
        """格式化消息用于摘要提示词

        Args:
            messages: 消息列表

        Returns:
            格式化的文本
        """
        lines = []
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                # 截断长内容
                preview = content[:200] + "..." if len(content) > 200 else content
                lines.append(f"[{i+1}] {role}: {preview}")

        return "\n".join(lines)

    def should_generate_summary(self, messages: list[dict]) -> bool:
        """判断是否需要生成摘要

        Args:
            messages: 当前消息列表

        Returns:
            是否需要生成摘要
        """
        # 计算对话轮数（user + assistant 对）
        turn_count = sum(1 for m in messages if m.get("role") == "user")

        return turn_count >= self.config.trigger_turns

    def get_messages_to_summarize(self, messages: list[dict]) -> tuple[list[dict], list[dict]]:
        """分离需要摘要和保留的消息

        Args:
            messages: 消息列表

        Returns:
            (需要摘要的消息, 保留的消息)
        """
        preserve_count = self.config.preserve_turns * 2  # 每轮 2 条消息

        if len(messages) <= preserve_count:
            return [], messages

        to_summarize = messages[:-preserve_count]
        to_preserve = messages[-preserve_count:]

        return to_summarize, to_preserve


def create_summary_message(summary: str) -> dict:
    """创建摘要消息

    Args:
        summary: 摘要内容

    Returns:
        系统消息格式的摘要
    """
    return {
        "role": "system",
        "content": f"[历史对话摘要]\n{summary}",
    }


# 全局实例
_generator: SummaryGenerator | None = None


def get_summary_generator() -> SummaryGenerator:
    """获取摘要生成器实例"""
    global _generator
    if _generator is None:
        _generator = SummaryGenerator()
    return _generator