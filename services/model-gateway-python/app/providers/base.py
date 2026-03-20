"""提供商基类"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """对话消息"""

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """对话补全请求"""

    messages: list[ChatMessage]
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2000
    stream: bool = False
    stop: list[str] | None = None


class ChatCompletionChoice(BaseModel):
    """对话补全选项"""

    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionUsage(BaseModel):
    """Token 使用统计"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """对话补全响应 - OpenAI 兼容格式"""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


class BaseLLMProvider(ABC):
    """LLM 提供商基类"""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称"""
        pass

    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """支持的模型列表"""
        pass

    @abstractmethod
    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """对话补全"""
        pass

    @abstractmethod
    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """流式对话补全"""
        pass

    def supports_model(self, model: str) -> bool:
        """检查是否支持指定模型"""
        return model in self.supported_models or any(m in model for m in self.supported_models)
