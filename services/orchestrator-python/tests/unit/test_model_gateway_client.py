"""测试 ModelGateway HTTP 客户端"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import AllProvidersDownError, ModelTimeoutError
from app.tools.clients.model_gateway_client import ModelGatewayClient


@pytest.fixture
def client():
    """创建客户端实例"""
    return ModelGatewayClient(base_url="http://localhost:8001")


@pytest.fixture
def mock_response():
    """创建 Mock 响应"""
    response = MagicMock()
    response.json = MagicMock(
        return_value={
            "id": "chat-001",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "你好！有什么可以帮助你的？",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }
    )
    response.raise_for_status = MagicMock()
    return response


class TestModelGatewayClient:
    """ModelGateway 客户端测试"""

    @pytest.mark.asyncio
    async def test_chat_completion(self, client, mock_response):
        """测试对话补全"""
        mock_httpx_client = AsyncMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            result = await client.chat_completion(
                messages=[{"role": "user", "content": "你好"}],
            )

            assert "choices" in result
            assert result["choices"][0]["message"]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_chat_completion_with_model(self, client, mock_response):
        """测试指定模型的对话补全"""
        mock_httpx_client = AsyncMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            await client.chat_completion(
                messages=[{"role": "user", "content": "你好"}],
                model="qwen-max",
            )

            call_args = mock_httpx_client.post.call_args
            assert call_args[1]["json"]["model"] == "qwen-max"

    @pytest.mark.asyncio
    async def test_chat_completion_with_custom_params(self, client, mock_response):
        """测试自定义参数的对话补全"""
        mock_httpx_client = AsyncMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            await client.chat_completion(
                messages=[{"role": "user", "content": "你好"}],
                temperature=0.5,
                max_tokens=1000,
            )

            call_args = mock_httpx_client.post.call_args
            assert call_args[1]["json"]["temperature"] == 0.5
            assert call_args[1]["json"]["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_chat_completion_timeout(self, client):
        """测试对话补全超时"""
        mock_httpx_client = AsyncMock()
        mock_httpx_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            with pytest.raises(ModelTimeoutError):
                await client.chat_completion(
                    messages=[{"role": "user", "content": "你好"}],
                )

    @pytest.mark.asyncio
    async def test_chat_completion_service_unavailable(self, client):
        """测试服务不可用"""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_httpx_client = AsyncMock()
        mock_httpx_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Service Unavailable",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            with pytest.raises(AllProvidersDownError):
                await client.chat_completion(
                    messages=[{"role": "user", "content": "你好"}],
                )

    @pytest.mark.asyncio
    async def test_list_models(self, client):
        """测试获取模型列表"""
        mock_response = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "data": [
                    {"id": "qwen-max", "provider": "qwen"},
                    {"id": "qwen-plus", "provider": "qwen"},
                ],
            }
        )
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            models = await client.list_models()

            assert len(models) == 2
            assert models[0]["id"] == "qwen-max"

    @pytest.mark.asyncio
    async def test_list_models_error(self, client):
        """测试获取模型列表失败 - 降级返回默认模型"""
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get = AsyncMock(side_effect=Exception("Connection error"))

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            # use_cache=True (默认) 返回 DEFAULT_MODELS 降级列表
            models = await client.list_models(use_cache=True)
            assert len(models) > 0  # 降级返回默认模型

            # use_cache=False 返回空列表
            models_no_cache = await client.list_models(use_cache=False)
            assert models_no_cache == []

    @pytest.mark.asyncio
    async def test_chat_with_tools(self, client, mock_response):
        """测试带工具调用的对话"""
        mock_httpx_client = AsyncMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "query_weather",
                    "description": "查询天气",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string"},
                        },
                    },
                },
            }
        ]

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            await client.chat_with_tools(
                messages=[{"role": "user", "content": "北京天气怎么样"}],
                tools=tools,
            )

            call_args = mock_httpx_client.post.call_args
            assert "tools" in call_args[1]["json"]
            assert call_args[1]["json"]["tool_choice"] == "auto"

    @pytest.mark.asyncio
    async def test_close(self, client):
        """测试关闭客户端"""
        mock_httpx_client = AsyncMock()
        client._client = mock_httpx_client

        await client.close()

        mock_httpx_client.aclose.assert_called_once()
        assert client._client is None
