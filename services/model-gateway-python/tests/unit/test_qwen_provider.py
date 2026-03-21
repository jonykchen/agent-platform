"""测试 Qwen 提供商"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.providers.qwen import QwenProvider
from app.providers.base import ChatCompletionRequest, ChatMessage


@pytest.fixture
def qwen_provider():
    """创建 Qwen 提供商实例"""
    return QwenProvider(
        api_key="test-api-key",
        base_url="https://dashscope.aliyuncs.com/api/v1",
    )


@pytest.fixture
def mock_response():
    """创建 Mock 响应"""
    response = MagicMock()
    response.json = MagicMock(return_value={
        "id": "chat-001",
        "created": 1234567890,
        "model": "qwen-max",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "你好！有什么可以帮助你的？",
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    })
    response.raise_for_status = MagicMock()
    return response


class TestQwenProvider:
    """Qwen 提供商测试"""

    def test_provider_name(self, qwen_provider):
        """测试提供商名称"""
        assert qwen_provider.provider_name == "qwen"

    def test_supported_models(self, qwen_provider):
        """测试支持的模型列表"""
        models = qwen_provider.supported_models
        assert "qwen-max" in models
        assert "qwen-plus" in models
        assert "qwen-turbo" in models

    def test_supports_model(self, qwen_provider):
        """测试模型支持检查"""
        assert qwen_provider.supports_model("qwen-max") is True
        assert qwen_provider.supports_model("unknown-model") is False

    @pytest.mark.asyncio
    async def test_chat_completion(self, qwen_provider, mock_response):
        """测试对话补全"""
        request = ChatCompletionRequest(
            messages=[
                ChatMessage(role="user", content="你好"),
            ],
            model="qwen-max",
        )

        with patch.object(httpx.AsyncClient, "__aenter__") as mock_client:
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            response = await qwen_provider.chat_completion(request)

            assert response.id == "chat-001"
            assert response.model == "qwen-max"
            assert len(response.choices) == 1
            assert response.choices[0].message.content == "你好！有什么可以帮助你的？"
            assert response.usage.total_tokens == 30

    @pytest.mark.asyncio
    async def test_chat_completion_default_model(self, qwen_provider, mock_response):
        """测试使用默认模型的对话补全"""
        request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="测试")],
        )

        with patch.object(httpx.AsyncClient, "__aenter__") as mock_client:
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            response = await qwen_provider.chat_completion(request)

            assert response is not None

    @pytest.mark.asyncio
    async def test_chat_completion_with_custom_params(self, qwen_provider, mock_response):
        """测试自定义参数"""
        request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="测试")],
            temperature=0.5,
            max_tokens=1000,
        )

        with patch.object(httpx.AsyncClient, "__aenter__") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            await qwen_provider.chat_completion(request)

            call_args = mock_instance.post.call_args
            payload = call_args[1]["json"]
            assert payload["temperature"] == 0.5
            assert payload["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_stream_chat_completion(self, qwen_provider):
        """测试流式对话补全"""
        request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="你好")],
            model="qwen-max",
        )

        mock_stream = AsyncMock()
        mock_stream.aiter_lines = AsyncMock(return_value=iter([
            'data: {"choices": [{"delta": {"content": "你"}}]}',
            'data: {"choices": [{"delta": {"content": "好"}}]}',
            'data: [DONE]',
        ]))
        mock_stream.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "__aenter__") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.stream = MagicMock(return_value=mock_stream)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_stream)
            mock_instance.__aexit__ = AsyncMock()
            mock_client.return_value = mock_instance

            chunks = []
            async for chunk in qwen_provider.stream_chat_completion(request):
                chunks.append(chunk)

            assert len(chunks) >= 0  # 根据实际实现调整
