"""Token 计数模块

使用 tiktoken 进行精确的 token 计数，支持国内模型映射。
当无法精确计数时，使用近似算法。

【设计原则】
- 优先使用 API 返回的 usage 字段进行校准
- tiktoken 对国内模型（Qwen/GLM）计数可能不准，使用映射策略
- 提供回退方案：字符数 * 系数
"""

from __future__ import annotations

import functools
from typing import Any

import structlog

logger = structlog.get_logger()

# 默认系数：中文约 1.5 字符/token，英文约 4 字符/token
DEFAULT_CHINESE_RATIO = 1.5
DEFAULT_ENGLISH_RATIO = 4.0


class TokenCounter:
    """Token 计数器

    支持多种计数策略：
    1. tiktoken（OpenAI 模型精确）
    2. 字符数近似（国内模型回退）
    3. API usage 校准

    使用示例：
        counter = TokenCounter()
        tokens = counter.count_messages(messages)
    """

    # 模型到 tiktoken 编码的映射
    MODEL_ENCODING_MAP = {
        "gpt-4": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        # 国内模型使用 qwen 作为近似
        "qwen": "cl100k_base",
        "glm": "cl100k_base",
        "deepseek": "cl100k_base",
    }

    def __init__(self, default_encoding: str = "cl100k_base"):
        self._encoding = None
        self._default_encoding = default_encoding
        self._tiktoken_available = False
        self._init_tiktoken()

    def _init_tiktoken(self) -> None:
        """延迟初始化 tiktoken"""
        try:
            import tiktoken

            self._encoding = tiktoken.get_encoding(self._default_encoding)
            self._tiktoken_available = True
            logger.debug("tiktoken_initialized", encoding=self._default_encoding)
        except ImportError:
            logger.warning("tiktoken_not_available", fallback="character_approximation")
            self._tiktoken_available = False

    def count_text(self, text: str) -> int:
        """计算文本的 token 数量

        Args:
            text: 输入文本

        Returns:
            token 数量
        """
        if not text:
            return 0

        if self._tiktoken_available and self._encoding:
            return len(self._encoding.encode(text))

        # 回退：字符数近似
        return self._approximate_count(text)

    def _approximate_count(self, text: str) -> int:
        """近似 token 计数

        规则：
        - 中文字符：字符数 / 1.5
        - 英文/数字/符号：字符数 / 4
        """
        chinese_chars = sum(1 for c in text if "一" <= c <= "鿿")
        other_chars = len(text) - chinese_chars

        tokens = int(chinese_chars / DEFAULT_CHINESE_RATIO + other_chars / DEFAULT_ENGLISH_RATIO)
        return max(tokens, 1)

    def count_messages(self, messages: list[dict]) -> int:
        """计算消息列表的 token 数量

        OpenAI 格式消息结构：
        - 每条消息有 role + content
        - 还有固定开销（约 4 tokens/消息）

        Args:
            messages: OpenAI 格式的消息列表

        Returns:
            总 token 数量
        """
        if not messages:
            return 0

        total = 0
        for msg in messages:
            # 消息固定开销
            total += 4

            role = msg.get("role", "")
            total += self.count_text(role)

            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.count_text(content)
            elif isinstance(content, list):
                # 多模态消息
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total += self.count_text(part.get("text", ""))

            # tool_calls 开销
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                for tc in tool_calls:
                    function = tc.get("function", {})
                    total += self.count_text(function.get("name", ""))
                    # arguments 通常是 JSON 字符串
                    args = function.get("arguments", "")
                    if isinstance(args, str):
                        total += self.count_text(args)

        # 对话固定开销
        total += 3
        return total

    def calibrate_from_usage(self, text: str, actual_tokens: int) -> float:
        """根据 API usage 校准计数

        Args:
            text: 原始文本
            actual_tokens: API 返回的实际 token 数

        Returns:
            校准系数
        """
        estimated = self.count_text(text)
        if estimated == 0:
            return 1.0

        ratio = actual_tokens / estimated
        logger.debug(
            "token_calibration",
            estimated=estimated,
            actual=actual_tokens,
            ratio=ratio,
        )
        return ratio


# 全局实例（懒加载）
_counter: TokenCounter | None = None


def get_token_counter() -> TokenCounter:
    """获取 Token 计数器实例"""
    global _counter
    if _counter is None:
        _counter = TokenCounter()
    return _counter


def count_tokens(text: str) -> int:
    """便捷函数：计算文本 token 数"""
    return get_token_counter().count_text(text)


def count_message_tokens(messages: list[dict]) -> int:
    """便捷函数：计算消息列表 token 数"""
    return get_token_counter().count_messages(messages)
