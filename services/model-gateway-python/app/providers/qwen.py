"""Qwen (通义千问) 提供商实现"""

from typing import AsyncIterator

import httpx
import structlog

from app.providers.base import (
    BaseLLMProvider,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionUsage,
    ChatMessage,
)

logger = structlog.get_logger()


class QwenProvider(BaseLLMProvider):
    """Qwen 提供商"""

    PROVIDER_MODELS = [
        "qwen-max",
        "qwen-plus",
        "qwen-turbo",
        "qwen-long",
    ]

    def __init__(self, api_key: str, base_url: str):
        super().__init__(api_key, base_url)
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @property
    def provider_name(self) -> str:
        return "qwen"

    @property
    def supported_models(self) -> list[str]:
        return self.PROVIDER_MODELS

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """对话补全"""
        model = request.model or "qwen-max"

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return ChatCompletionResponse(
            id=data.get("id", ""),
            created=data.get("created", 0),
            model=data.get("model", model),
            choices=[
                ChatCompletionChoice(
                    index=c.get("index", 0),
                    message=ChatMessage(
                        role=c["message"]["role"],
                        content=c["message"]["content"],
                    ),
                    finish_reason=c.get("finish_reason", "stop"),
                )
                for c in data.get("choices", [])
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
                total_tokens=data.get("usage", {}).get("total_tokens", 0),
            ),
        )

    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """流式对话补全"""
        model = request.model or "qwen-max"

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield line
