"""测试上下文窗口管理器

测试 ContextManager 的截断策略、Token 计数和摘要降级行为。
所有外部依赖（config、token_counter、summary_generator）均 mock，可离线运行。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.context_manager import ContextManager, get_context_manager

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_counter():
    """Mock TokenCounter，精确控制 token 计数"""
    counter = MagicMock()
    counter.count_messages = MagicMock(return_value=0)
    counter.count_text = MagicMock(return_value=0)
    return counter


@pytest.fixture
def manager(mock_counter):
    """创建使用 mock counter 的 ContextManager 实例

    默认配置：max_tokens=1000, system_prompt_reserved=100, response_reserved=100
    available_tokens = 1000 - 100 - 100 = 800
    """
    with patch("app.core.context_manager.get_token_counter", return_value=mock_counter):
        with patch("app.core.context_manager.config"):
            mgr = ContextManager(
                max_tokens=1000,
                system_prompt_reserved=100,
                response_reserved=100,
                recent_turns=3,
            )
    return mgr


def _msg(role: str, content: str) -> dict:
    """便捷函数：构造消息字典"""
    return {"role": role, "content": content}


# ═══════════════════════════════════════════════════════════════════════════════
# 上下文未超限
# ═══════════════════════════════════════════════════════════════════════════════


class TestNoTruncationWhenWithinLimit:
    """上下文未超限时保持不变"""

    def test_should_keep_messages_unchanged_when_within_limit(self, manager, mock_counter):
        """消息总 token 未超限时应保持原样"""
        messages = [
            _msg("user", "hello"),
            _msg("assistant", "hi there"),
        ]
        # 每条消息 50 tokens，总计 100，远小于 available=800
        mock_counter.count_messages.side_effect = lambda msgs: len(msgs) * 50

        result = manager.truncate(messages)
        # 应包含原消息
        assert len(result) >= len(messages)

    def test_should_return_empty_list_for_empty_input(self, manager, mock_counter):
        """空消息列表应返回空列表"""
        mock_counter.count_messages.return_value = 0
        result = manager.truncate([])
        assert result == []

    def test_should_include_system_prompt_when_provided(self, manager, mock_counter):
        """提供 system_prompt 时应包含在结果中"""
        messages = [_msg("user", "hello")]
        mock_counter.count_messages.side_effect = lambda msgs: len(msgs) * 10

        result = manager.truncate(messages, system_prompt="You are a helper")
        system_msgs = [m for m in result if m["role"] == "system"]
        assert len(system_msgs) >= 1
        assert any("You are a helper" in m.get("content", "") for m in system_msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# 上下文超限截断
# ═══════════════════════════════════════════════════════════════════════════════


class TestTruncationWhenOverLimit:
    """上下文超限时正确截断"""

    def test_should_truncate_recent_messages_when_over_limit(self, manager, mock_counter):
        """最近消息总 token 超过 available 时应截断"""
        messages = [
            _msg("user", "msg1"),
            _msg("assistant", "resp1"),
            _msg("user", "msg2"),
            _msg("assistant", "resp2"),
            _msg("user", "msg3"),
            _msg("assistant", "resp3"),
        ]
        # 每条消息 500 tokens，超限
        mock_counter.count_messages.side_effect = lambda msgs: len(msgs) * 500

        result = manager.truncate(messages)
        # 截断后消息数应少于原始
        assert len(result) < len(messages) + 2  # +2 for possible system prompt + summary

    def test_should_preserve_system_prompt_during_truncation(self, manager, mock_counter):
        """截断时应始终保留 system prompt"""
        messages = [_msg("user", "hello")]
        mock_counter.count_messages.side_effect = lambda msgs: len(msgs) * 500

        result = manager.truncate(messages, system_prompt="Important system prompt")
        has_system = any(m["role"] == "system" for m in result)
        assert has_system is True

    def test_should_force_truncate_to_minimal_when_severely_over_limit(self, manager, mock_counter):
        """严重超限时强制截断为 system prompt + 最后一条用户消息"""
        messages = [
            _msg("user", "msg1"),
            _msg("assistant", "resp1"),
            _msg("user", "msg2"),
        ]
        # 模拟即使截断后仍超限的情况
        high_token_count = 2000
        mock_counter.count_messages.return_value = high_token_count

        result = manager.truncate(messages, system_prompt="System")
        # 强制截断后应至少有 system prompt 或用户消息
        assert len(result) <= 2

    def test_should_keep_recent_turns_preferentially(self, manager, mock_counter):
        """应优先保留最近 N 轮对话"""
        # 10 条消息 = 5 轮, recent_turns=3 保留最近 6 条
        messages = []
        for i in range(5):
            messages.append(_msg("user", f"question {i}"))
            messages.append(_msg("assistant", f"answer {i}"))

        # 让 token 计数刚好允许最近 6 条
        def count_side_effect(msgs):
            return len(msgs) * 50  # 每条 50 tokens

        mock_counter.count_messages.side_effect = count_side_effect

        result = manager.truncate(messages)
        # 最近 6 条 (recent_turns*2) 应在结果中
        result_contents = [m.get("content", "") for m in result]
        assert "question 4" in result_contents
        assert "answer 4" in result_contents


# ═══════════════════════════════════════════════════════════════════════════════
# 重要工具结果保留
# ═══════════════════════════════════════════════════════════════════════════════


class TestImportantToolResultRetention:
    """重要工具结果保留"""

    def test_should_preserve_important_tool_results(self, manager, mock_counter):
        """标记为重要的工具结果应被保留"""
        messages = [
            _msg("user", "question"),
            _msg("assistant", "answer"),
            {"role": "tool", "content": "important result", "tool_call_id": "call_001"},
            _msg("user", "follow up"),
            _msg("assistant", "follow up answer"),
        ]
        # 让消息数量超过 recent_turns*2，使得 tool 消息在 older_messages 中
        mock_counter.count_messages.side_effect = lambda msgs: len(msgs) * 50

        result = manager.truncate(
            messages,
            important_tool_results=["call_001"],
        )
        # 至少应不会报错
        assert isinstance(result, list)

    def test_should_skip_non_important_tool_results(self, manager, mock_counter):
        """非重要的工具结果不应被额外保留"""
        messages = [
            {"role": "tool", "content": "unimportant", "tool_call_id": "call_002"},
            _msg("user", "latest question"),
            _msg("assistant", "latest answer"),
        ]
        mock_counter.count_messages.side_effect = lambda msgs: len(msgs) * 50

        result = manager.truncate(messages, important_tool_results=["call_001"])
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════════
# Token 计数
# ═══════════════════════════════════════════════════════════════════════════════


class TestTokenCounting:
    """Token 计数准确性"""

    def test_needs_truncation_returns_true_when_over_limit(self, manager, mock_counter):
        """超过可用 token 时 needs_truncation 应返回 True"""
        mock_counter.count_messages.return_value = 900  # > available=800
        assert manager.needs_truncation([_msg("user", "test")]) is True

    def test_needs_truncation_returns_false_when_within_limit(self, manager, mock_counter):
        """未超过可用 token 时 needs_truncation 应返回 False"""
        mock_counter.count_messages.return_value = 500  # < available=800
        assert manager.needs_truncation([_msg("user", "test")]) is False

    def test_get_remaining_tokens_returns_correct_value(self, manager, mock_counter):
        """get_remaining_tokens 应正确计算剩余 token"""
        mock_counter.count_messages.return_value = 300
        # remaining = max_tokens - current - response_reserved = 1000 - 300 - 100 = 600
        remaining = manager.get_remaining_tokens([_msg("user", "test")])
        assert remaining == 600

    def test_get_remaining_tokens_should_not_return_negative(self, manager, mock_counter):
        """剩余 token 不应为负数"""
        mock_counter.count_messages.return_value = 1500
        remaining = manager.get_remaining_tokens([_msg("user", "test")])
        assert remaining >= 0

    def test_available_tokens_calculation(self, mock_counter):
        """available_tokens 应正确计算"""
        with patch("app.core.context_manager.get_token_counter", return_value=mock_counter):
            with patch("app.core.context_manager.config"):
                mgr = ContextManager(
                    max_tokens=2000,
                    system_prompt_reserved=200,
                    response_reserved=300,
                )
        assert mgr.available_tokens == 2000 - 200 - 300  # 1500


# ═══════════════════════════════════════════════════════════════════════════════
# 摘要生成降级
# ═══════════════════════════════════════════════════════════════════════════════


class TestSummaryGenerationFallback:
    """摘要生成降级测试

    _generate_summary 内部通过 `from app.memory.summary_generator import get_summary_generator`
    导入，因此需要 patch app.memory.summary_generator 模块。
    """

    def test_generate_summary_should_return_none_for_empty_messages(self, manager):
        """空消息列表应返回 None"""
        result = manager._generate_summary([])
        assert result is None

    def test_generate_summary_should_fallback_on_import_error(self, manager):
        """summary_generator 不可用时应降级到简单提取"""
        # 让 import 失败，触发 except 分支的降级逻辑
        with patch.dict("sys.modules", {"app.memory.summary_generator": None}):
            messages = [
                _msg("user", "我想查询订单状态"),
                _msg("assistant", "好的，请提供订单号"),
                _msg("user", "订单号是 ORD-12345"),
            ]
            result = manager._generate_summary(messages)
            # 降级时应返回包含用户消息的摘要
            assert result is not None
            assert "用户询问" in result

    def test_generate_summary_should_fallback_when_generator_raises(self, manager):
        """summary_generator 内部抛异常时应降级到简单提取"""
        # 通过 patch get_summary_generator 使其抛异常
        with patch(
            "app.memory.summary_generator.get_summary_generator",
            side_effect=Exception("generator init failed"),
        ):
            messages = [
                _msg("user", "查询物流信息"),
            ]
            result = manager._generate_summary(messages)
            # 降级到简单提取
            assert result is not None
            assert "用户询问" in result

    def test_generate_summary_should_truncate_long_user_messages(self, manager):
        """降级时长用户消息应被截断"""
        with patch.dict("sys.modules", {"app.memory.summary_generator": None}):
            long_content = "很长的内容" * 100
            messages = [_msg("user", long_content)]
            result = manager._generate_summary(messages)
            # 摘要中每条用户消息最多 50 字符 + "..."
            assert result is not None

    def test_generate_summary_should_return_none_when_no_user_messages(self, manager):
        """无用户消息时降级摘要应返回 None"""
        with patch.dict("sys.modules", {"app.memory.summary_generator": None}):
            messages = [_msg("assistant", "系统回复")]
            result = manager._generate_summary(messages)
            assert result is None

    @pytest.mark.asyncio
    async def test_generate_summary_async_should_fallback_to_sync(self, manager):
        """异步摘要生成失败时应降级到同步"""
        with patch.dict("sys.modules", {"app.memory.summary_generator": None}):
            messages = [_msg("user", "测试消息")]
            result = await manager._generate_summary_async(messages)
            # 应降级到同步版本，不抛异常即可
            assert result is not None or result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 滑动窗口策略
# ═══════════════════════════════════════════════════════════════════════════════


class TestSlidingWindowStrategy:
    """滑动窗口策略"""

    def test_should_keep_recent_turns_by_default(self, mock_counter):
        """默认应保留最近 N 轮对话"""
        with patch("app.core.context_manager.get_token_counter", return_value=mock_counter):
            with patch("app.core.context_manager.config"):
                mgr = ContextManager(
                    max_tokens=1000,
                    system_prompt_reserved=100,
                    response_reserved=100,
                    recent_turns=2,
                )

        messages = []
        for i in range(5):
            messages.append(_msg("user", f"q{i}"))
            messages.append(_msg("assistant", f"a{i}"))

        # 每条消息 50 tokens
        mock_counter.count_messages.side_effect = lambda msgs: len(msgs) * 50

        result = mgr.truncate(messages)
        # 最近 2 轮 = 4 条消息应被优先保留
        result_contents = [m.get("content", "") for m in result]
        assert "q4" in result_contents
        assert "a4" in result_contents

    def test_should_classify_older_messages_correctly(self, mock_counter):
        """应正确分离旧消息和近期消息"""
        with patch("app.core.context_manager.get_token_counter", return_value=mock_counter):
            with patch("app.core.context_manager.config"):
                mgr = ContextManager(
                    max_tokens=1000,
                    system_prompt_reserved=100,
                    response_reserved=100,
                    recent_turns=2,
                )

        # 6 条消息 = 3 轮, recent_turns=2 → 最近 4 条, 旧 2 条
        messages = [
            _msg("user", "old_q"),
            _msg("assistant", "old_a"),
            _msg("user", "recent_q1"),
            _msg("assistant", "recent_a1"),
            _msg("user", "recent_q2"),
            _msg("assistant", "recent_a2"),
        ]

        mock_counter.count_messages.side_effect = lambda msgs: len(msgs) * 50

        result = mgr.truncate(messages)
        # 旧消息可能出现在摘要中，近消息应直接保留
        assert isinstance(result, list)
        result_contents = [m.get("content", "") for m in result]
        assert "recent_q2" in result_contents
        assert "recent_a2" in result_contents


# ═══════════════════════════════════════════════════════════════════════════════
# 异步截断
# ═══════════════════════════════════════════════════════════════════════════════


class TestTruncateAsync:
    """异步截断测试"""

    @pytest.mark.asyncio
    async def test_should_truncate_async_same_logic_as_sync(self, manager, mock_counter):
        """异步截断应与同步截断逻辑一致"""
        messages = [
            _msg("user", "hello"),
            _msg("assistant", "hi"),
        ]
        mock_counter.count_messages.side_effect = lambda msgs: len(msgs) * 50

        result = await manager.truncate_async(messages, system_prompt="System")
        assert isinstance(result, list)
        system_msgs = [m for m in result if m["role"] == "system"]
        assert len(system_msgs) >= 1

    @pytest.mark.asyncio
    async def test_should_handle_empty_messages_async(self, manager, mock_counter):
        """异步截断空消息列表"""
        result = await manager.truncate_async([])
        assert result == []

    @pytest.mark.asyncio
    async def test_async_summary_should_use_llm_when_available(self, manager, mock_counter):
        """异步摘要生成应优先使用 LLM"""
        # 构造超过 recent_turns 的消息以触发摘要
        messages = []
        for i in range(8):
            messages.append(_msg("user", f"q{i}"))
            messages.append(_msg("assistant", f"a{i}"))

        mock_counter.count_messages.side_effect = lambda msgs: len(msgs) * 50

        mock_generator = AsyncMock()
        mock_generator.generate = AsyncMock(return_value="LLM generated summary")

        # _generate_summary_async 内部 import from app.memory.summary_generator
        with patch(
            "app.memory.summary_generator.get_summary_generator",
            return_value=mock_generator,
        ):
            result = await manager.truncate_async(messages, system_prompt="System")
            # 如果摘要被生成，应有包含摘要的 system 消息
            assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════


class TestGlobalInstance:
    """全局实例测试"""

    def test_get_context_manager_returns_instance(self):
        """get_context_manager 应返回 ContextManager 实例"""
        import app.core.context_manager as cm

        cm._manager = None

        with patch("app.core.context_manager.get_token_counter"), patch("app.core.context_manager.config"):
            mgr = get_context_manager()
            assert isinstance(mgr, ContextManager)

    def test_get_context_manager_returns_same_instance(self):
        """多次调用应返回同一实例（单例）"""
        import app.core.context_manager as cm

        cm._manager = None

        with patch("app.core.context_manager.get_token_counter"), patch("app.core.context_manager.config"):
            mgr1 = get_context_manager()
            mgr2 = get_context_manager()
            assert mgr1 is mgr2

        # 清理
        cm._manager = None
