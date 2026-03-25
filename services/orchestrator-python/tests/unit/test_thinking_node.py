"""测试 Thinking 节点 - 模型推理调用"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.graph.nodes.thinking import thinking_node
from app.graph.state import create_initial_state
from app.core.exceptions import ModelTimeoutError, AllProvidersDownError


@pytest.fixture
def mock_state():
    """创建 Mock 状态"""
    return create_initial_state(
        input="查询订单 ORD-12345 的状态",
        session_id="sess_001",
        tenant_id="tenant_001",
        user_id="user_001",
        request_id="req_001",
        max_steps=10,
    )


@pytest.fixture
def mock_model_response():
    """创建 Mock 模型响应"""
    return {
        "id": "chat-001",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_001",
                    "type": "function",
                    "function": {
                        "name": "query_order_status",
                        "arguments": '{"order_id": "ORD-12345"}',
                    },
                }],
            },
            "finish_reason": "tool_calls",
        }],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 20,
            "total_tokens": 70,
        },
    }


class TestThinkingNodeWithModel:
    """Thinking 节点模型调用测试"""

    @pytest.mark.asyncio
    async def test_thinking_with_tool_call_response(self, mock_state, mock_model_response):
        """测试模型返回工具调用"""
        mock_client = AsyncMock()
        mock_client.chat_completion = AsyncMock(return_value=mock_model_response)

        with patch(
            "app.graph.nodes.thinking.get_model_gateway_client",
            return_value=mock_client,
        ):
            result = await thinking_node(mock_state)

            assert result["current_step"] == "tool_call"
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["tool_name"] == "query_order_status"
            assert result["step_count"] == 1

    @pytest.mark.asyncio
    async def test_thinking_with_direct_answer(self, mock_state):
        """测试模型返回直接回答"""
        mock_response = {
            "id": "chat-002",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "订单 ORD-12345 已发货，预计明天到达。",
                },
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45},
        }

        mock_client = AsyncMock()
        mock_client.chat_completion = AsyncMock(return_value=mock_response)

        with patch(
            "app.graph.nodes.thinking.get_model_gateway_client",
            return_value=mock_client,
        ):
            result = await thinking_node(mock_state)

            assert result["current_step"] == "final_answer"
            assert "ORD-12345" in result["output"]
            assert result["step_count"] == 1

    @pytest.mark.asyncio
    async def test_thinking_max_steps_exceeded(self, mock_state):
        """测试超过最大步骤数"""
        mock_state["step_count"] = 10

        result = await thinking_node(mock_state)

        assert result["current_step"] == "max_steps_exceeded"
        assert result["error_code"] == "ERR_AGENT_MAX_STEPS_EXCEEDED"

    @pytest.mark.asyncio
    async def test_thinking_model_timeout(self, mock_state):
        """测试模型调用超时"""
        mock_client = AsyncMock()
        mock_client.chat_completion = AsyncMock(
            side_effect=ModelTimeoutError(timeout_s=30)
        )

        with patch(
            "app.graph.nodes.thinking.get_model_gateway_client",
            return_value=mock_client,
        ):
            result = await thinking_node(mock_state)

            assert result["current_step"] == "error"
            assert result["error_code"] == "ERR_MODEL_TIMEOUT"

    @pytest.mark.asyncio
    async def test_thinking_all_providers_down(self, mock_state):
        """测试所有提供商不可用"""
        mock_client = AsyncMock()
        mock_client.chat_completion = AsyncMock(
            side_effect=AllProvidersDownError()
        )

        with patch(
            "app.graph.nodes.thinking.get_model_gateway_client",
            return_value=mock_client,
        ):
            result = await thinking_node(mock_state)

            assert result["current_step"] == "error"
            assert result["error_code"] == "ERR_MODEL_ALL_PROVIDERS_DOWN"

    @pytest.mark.asyncio
    async def test_thinking_with_tool_results(self, mock_state):
        """测试处理工具返回结果"""
        mock_state["tool_results"] = [{
            "call_id": "call_001",
            "status": "success",
            "result_json": '{"status": "已发货", "eta": "2024-01-15"}',
        }]
        mock_state["step_count"] = 1

        mock_response = {
            "id": "chat-003",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "根据查询结果，您的订单 ORD-12345 已发货，预计 2024-01-15 到达。",
                },
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
        }

        mock_client = AsyncMock()
        mock_client.chat_completion = AsyncMock(return_value=mock_response)

        with patch(
            "app.graph.nodes.thinking.get_model_gateway_client",
            return_value=mock_client,
        ):
            result = await thinking_node(mock_state)

            assert result["current_step"] == "final_answer"

    @pytest.mark.asyncio
    async def test_thinking_builds_correct_messages(self, mock_state):
        """测试构建正确的消息结构"""
        mock_client = AsyncMock()
        mock_client.chat_completion = AsyncMock(return_value={
            "id": "chat-004",
            "choices": [{
                "message": {"role": "assistant", "content": "测试回答"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })

        with patch(
            "app.graph.nodes.thinking.get_model_gateway_client",
            return_value=mock_client,
        ):
            await thinking_node(mock_state)

            call_args = mock_client.chat_completion.call_args
            messages = call_args[1]["messages"]

            assert len(messages) >= 1
            assert messages[0]["role"] == "user"
            assert "ORD-12345" in messages[0]["content"]