"""Chat API - 对话补全"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.providers.base import ChatCompletionRequest, ChatCompletionResponse

router = APIRouter()


class ChatRequest(BaseModel):
    """对话请求"""

    messages: list[dict] = Field(..., min_length=1)
    model: str = "qwen-max"
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(2000, ge=1, le=8000)
    stream: bool = False


class ChatResponse(BaseModel):
    """对话响应"""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[dict]
    usage: dict


@router.post("/chat/completions", response_model=ChatResponse)
async def chat_completion(request: ChatRequest):
    """对话补全 - OpenAI 兼容接口"""
    # TODO: 实现模型路由和调用逻辑
    import time
    import uuid

    return ChatResponse(
        id=f"chat-{uuid.uuid4().hex[:8]}",
        created=int(time.time()),
        model=request.model,
        choices=[
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "收到您的消息，Model Gateway 服务待实现。",
                },
                "finish_reason": "stop",
            }
        ],
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    )
