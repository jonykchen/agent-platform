"""测试 Chat API - 模型路由和调用"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.chat import ChatRequest, ChatResponse, chat_completion
from app.providers.base import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionUsage,
    ChatMessage,
)
from app.core.exceptions import AllProvidersDownError


@pytest.fixture
def mock_chat_request():
    """创建对话请求"""
    return ChatRequest(
        messages=[
            {"role": "user", "content": "查询订单 ORD-12345 的状态"},
        ],
        model="qwen-max",
        temperature=0.7,
        max_tokens=2000,
        stream=False,
    )


@pytest.fixture
def mock_provider_response():
    """创建提供商响应"""
    return ChatCompletionResponse(
        id="chat-001",
        created=1704067200,
        model="qwen-max",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(
                    role="assistant",
                    content="订单 ORD-12345 已发货，预计明天到达。",
                ),
                finish_reason="stop",
            ),
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        ),
    )


class TestChatCompletion:
    """对话补全 API 测试"""

    @pytest.mark.asyncio
    async def test_chat_completion_success(self, mock_chat_request, mock_provider_response):
        """测试成功的对话补全"""
        mock_router = MagicMock()
        mock_provider = AsyncMock()
        mock_provider.chat_completion = AsyncMock(return_value=mock_provider_response)
        mock_circuit_breaker = MagicMock()
        mock_circuit_breaker.is_available = MagicMock(return_value=True)
        mock_circuit_breaker.record_success = MagicMock()

        mock_router.route = AsyncMock(
            return_value=(mock_provider, "qwen-max", mock_circuit_breaker)
        )

        with patch("app.api.v1.chat.get_model_router", return_value=mock_router):
            response = await chat_completion(mock_chat_request)

            assert isinstance(response, ChatResponse)
            assert response.model == "qwen-max"
            assert len(response.choices) == 1
            assert "ORD-12345" in response.choices[0]["message"]["content"]
            mock_circuit_breaker.record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_completion_with_fallback(self, mock_chat_request):
        """测试模型降级"""
        mock_router = MagicMock()

        # 主模型熔断
        mock_primary_provider = AsyncMock()
        mock_primary_cb = MagicMock()
        mock_primary_cb.is_available = MagicMock(return_value=False)

        # 备用模型可用
        mock_fallback_provider = AsyncMock()
        mock_fallback_response = ChatCompletionResponse(
            id="chat-002",
            created=1704067200,
            model="qwen-plus",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="备用模型回答"),
                    finish_reason="stop",
                ),
            ],
            usage=ChatCompletionUsage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
        )
        mock_fallback_provider.chat_completion = AsyncMock(return_value=mock_fallback_response)
        mock_fallback_cb = MagicMock()
        mock_fallback_cb.is_available = MagicMock(return_value=True)
        mock_fallback_cb.record_success = MagicMock()

        # 路由到备用模型
        mock_router.route = AsyncMock(
            return_value=(mock_fallback_provider, "qwen-plus", mock_fallback_cb)
        )

        with patch("app.api.v1.chat.get_model_router", return_value=mock_router):
            response = await chat_completion(mock_chat_request)

            assert response.model == "qwen-plus"
            mock_fallback_cb.record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_completion_all_providers_down(self, mock_chat_request):
        """测试所有提供商不可用"""
        mock_router = MagicMock()
        mock_router.route = AsyncMock(side_effect=AllProvidersDownError())

        with patch("app.api.v1.chat.get_model_router", return_value=mock_router):
            with pytest.raises(AllProvidersDownError):
                await chat_completion(mock_chat_request)

    @pytest.mark.asyncio
    async def test_chat_completion_records_failure(self, mock_chat_request):
        """测试记录失败"""
        mock_router = MagicMock()
        mock_provider = AsyncMock()
        mock_provider.chat_completion = AsyncMock(side_effect=Exception("Provider error"))
        mock_circuit_breaker = MagicMock()
        mock_circuit_breaker.is_available = MagicMock(return_value=True)
        mock_circuit_breaker.record_failure = MagicMock()

        mock_router.route = AsyncMock(
            return_value=(mock_provider, "qwen-max", mock_circuit_breaker)
        )

        with patch("app.api.v1.chat.get_model_router", return_value=mock_router):
            with pytest.raises(Exception):
                await chat_completion(mock_chat_request)

            mock_circuit_breaker.record_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_completion_without_model_specified(self):
        """测试未指定模型时使用默认路由"""
        request = ChatRequest(
            messages=[{"role": "user", "content": "你好"}],
            model="qwen-max",
        )

        mock_response = ChatCompletionResponse(
            id="chat-003",
            created=1704067200,
            model="qwen-max",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="你好！"),
                    finish_reason="stop",
                ),
            ],
            usage=ChatCompletionUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        mock_router = MagicMock()
        mock_provider = AsyncMock()
        mock_provider.chat_completion = AsyncMock(return_value=mock_response)
        mock_cb = MagicMock()
        mock_cb.is_available = MagicMock(return_value=True)
        mock_cb.record_success = MagicMock()

        mock_router.route = AsyncMock(return_value=(mock_provider, "qwen-max", mock_cb))

        with patch("app.api.v1.chat.get_model_router", return_value=mock_router):
            response = await chat_completion(request)

            assert response.model == "qwen-max"

    @pytest.mark.asyncio
    async def test_chat_completion_with_tool_calls(self, mock_chat_request):
        """测试带工具调用的响应"""
        mock_response = ChatCompletionResponse(
            id="chat-004",
            created=1704067200,
            model="qwen-max",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="",
                    ),
                    finish_reason="tool_calls",
                ),
            ],
            usage=ChatCompletionUsage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
        )

        mock_router = MagicMock()
        mock_provider = AsyncMock()
        mock_provider.chat_completion = AsyncMock(return_value=mock_response)
        mock_cb = MagicMock()
        mock_cb.is_available = MagicMock(return_value=True)
        mock_cb.record_success = MagicMock()

        mock_router.route = AsyncMock(return_value=(mock_provider, "qwen-max", mock_cb))

        with patch("app.api.v1.chat.get_model_router", return_value=mock_router):
            response = await chat_completion(mock_chat_request)

            assert response.choices[0]["finish_reason"] == "tool_calls"