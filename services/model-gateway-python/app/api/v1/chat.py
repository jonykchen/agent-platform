"""Chat API - 对话补全

核心职责：
1. 接收 OpenAI 兼容格式的对话请求
2. 调用模型路由器选择最优模型
3. 执行模型调用并返回结果

请求处理流程：
┌─────────────────────────────────────────────────────────┐
│                HTTP POST /v1/chat/completions           │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 请求参数解析    │                     │
│                  │ messages        │                     │
│                  │ model (可选)    │                     │
│                  │ temperature     │                     │
│                  │ max_tokens      │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 调用模型路由器  │                     │
│                  │ route(request)   │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 执行模型调用    │                     │
│                  │ provider.chat() │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                    │
│                  │ 构建响应        │                     │
│                  │ ChatResponse    │                     │
│                  └─────────────────┘                    │
│                           │                             │
│                           ▼                             │
│                    返回 HTTP 响应                       │
└─────────────────────────────────────────────────────────┘

OpenAI 兼容接口：
- 请求格式与 OpenAI API 一致
- 支持 messages 数组格式
- 支持 model, temperature, max_tokens 参数
- 流式输出暂不支持

"""

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
    """对话补全 - OpenAI 兼容接口

    处理流程：
    1. 解析请求参数
    2. 调用模型路由器选择最优模型
    3. 执行模型调用
    4. 返回 OpenAI 格式的响应

    Args:
        request: ChatRequest 对话请求
            - messages: 对话消息列表
            - model: 可选的指定模型
            - temperature: 温度参数 (0-2)
            - max_tokens: 最大生成 token 数
            - stream: 是否流式输出（暂不支持）

    Returns:
        ChatResponse OpenAI 格式的对话响应
            - id: 响应唯一标识
            - model: 实际使用的模型
            - choices: 生成结果列表
            - usage: Token 使用统计
    """
    import time
    import uuid
    import structlog

    logger = structlog.get_logger()

    request_id = f"chat-{uuid.uuid4().hex[:8]}"
    start_time = time.time()

    logger.info(
        "request_received",
        endpoint="/v1/chat/completions",
        request_id=request_id,
        model=requested := request.model,
        message_count=len(request.messages),
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=request.stream,
    )

    # TODO: 实现模型路由和调用逻辑
    # 当前返回 Mock 响应

    latency_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "request_completed",
        endpoint="/v1/chat/completions",
        request_id=request_id,
        model=request.model,
        latency_ms=latency_ms,
        status="mock_response",
    )

    return ChatResponse(
        id=request_id,
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
