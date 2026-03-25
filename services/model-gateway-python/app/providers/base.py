"""提供商基类

【核心概念】LLM 提供商抽象层
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

模型网关需要对接多个 LLM 提供商（通义千问、智谱 GLM、DeepSeek 等），
但各家 API 格式不同，需要统一抽象。

【设计模式】Strategy Pattern + Adapter Pattern

┌─────────────────────────────────────────────────────────────────────────┐
│                          模型网关架构                                    │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                     Orchestrator                                 │  │
│   │                          │                                       │  │
│   │                          │ OpenAI 兼容格式                        │  │
│   │                          ▼                                       │  │
│   │   ┌─────────────────────────────────────────────────────────┐   │  │
│   │   │               Model Gateway                              │   │  │
│   │   │                     │                                    │   │  │
│   │   │   ┌─────────────────┼─────────────────┐                │   │  │
│   │   │   │                 │                 │                │   │  │
│   │   │   ▼                 ▼                 ▼                │   │  │
│   │   │ QwenProvider   GLMProvider    DeepSeekProvider         │   │  │
│   │   │ (阿里云)        (智谱)         (深度求索)                │   │  │
│   │   └─────────────────────────────────────────────────────────┘   │  │
│   └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

【技术选型】为什么使用 OpenAI 兼容格式？
┌─────────────────────────────────────────────────────────────────────────┐
│  格式              │  优点                    │  缺点                  │
├────────────────────┼──────────────────────────┼────────────────────────┤
│  各家原生格式      │  完整功能                 │  需要多套客户端代码    │
│  ✓ OpenAI 兼容    │  统一接口、生态丰富       │  部分功能不兼容        │
│  LangChain        │  抽象完善                 │  依赖重、学习曲线      │
└─────────────────────────────────────────────────────────────────────────┘

OpenAI 兼容格式的优势：
- 统一的消息格式（messages: [{role, content}]）
- 统一的响应格式（choices, usage）
- 大量工具和库支持（如 openai SDK）

【适配器实现】
每个提供商需要实现：
1. chat_completion: 同步对话补全
2. stream_chat_completion: 流式对话补全

提供商负责：
- API 调用（HTTP 请求）
- 格式转换（原生 → OpenAI 兼容）
- 错误处理（重试、超时）
- Token 统计

【参考】
- OpenAI API 文档: https://platform.openai.com/docs/api-reference/chat
- 国内模型 API 对比: 见 docs/model-providers-comparison.md
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """对话消息 - OpenAI 兼容格式

    【消息格式】
    - role: 角色（system/user/assistant/tool）
    - content: 消息内容

    多轮对话示例：
    [
        {"role": "system", "content": "你是一个有帮助的助手"},
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么我可以帮助你的吗？"},
        {"role": "user", "content": "讲个笑话"}
    ]

    工具调用时的消息格式：
    [
        {"role": "user", "content": "查询订单 ORD-12345"},
        {"role": "assistant", "tool_calls": [...]},
        {"role": "tool", "tool_call_id": "...", "content": "{...}"}
    ]
    """

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """对话补全请求 - OpenAI 兼容格式

    【参数说明】
    - messages: 对话历史（必须）
    - model: 指定模型（可选，由路由策略决定）
    - temperature: 随机性（0-2，越高越随机）
    - max_tokens: 最大输出 token 数
    - stream: 是否流式输出
    - stop: 停止词列表

    【温度参数选择】
    - 0.0-0.3: 确定性任务（代码生成、数据提取）
    - 0.5-0.7: 平衡（通用对话）
    - 0.8-1.0: 创造性任务（写作、头脑风暴）
    """

    messages: list[ChatMessage]
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2000
    stream: bool = False
    stop: list[str] | None = None


class ChatCompletionChoice(BaseModel):
    """对话补全选项

    【响应结构】
    - index: 选项索引（通常只有一个）
    - message: 生成的消息
    - finish_reason: 结束原因（stop/length/tool_calls）
    """

    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionUsage(BaseModel):
    """Token 使用统计

    【成本计算】
    不同模型的价格不同：
    - qwen-max: ¥0.02/千token 输入, ¥0.06/千token 输出
    - qwen-plus: ¥0.004/千token 输入, ¥0.012/千token 输出

    cost = (prompt_tokens * input_price + completion_tokens * output_price) / 1000
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """对话补全响应 - OpenAI 兼容格式

    【响应字段】
    - id: 响应 ID（用于追踪）
    - object: 对象类型（固定为 "chat.completion"）
    - created: 创建时间戳
    - model: 实际使用的模型
    - choices: 生成结果列表
    - usage: Token 使用统计

    这个格式可以直接返回给前端或 Orchestrator，无需转换。
    """

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


class BaseLLMProvider(ABC):
    """LLM 提供商基类

    【设计模式】Template Method

    基类定义接口规范，子类实现具体逻辑：

    class QwenProvider(BaseLLMProvider):
        async def chat_completion(self, request):
            # 1. 调用通义千问 API
            # 2. 转换为 OpenAI 格式
            # 3. 返回响应

    【使用示例】
        provider = QwenProvider(api_key="...", base_url="...")
        response = await provider.chat_completion(request)

    【扩展新提供商】
    1. 创建新类继承 BaseLLMProvider
    2. 实现 chat_completion 和 stream_chat_completion
    3. 在 provider_factory 中注册
    """

    def __init__(self, api_key: str, base_url: str):
        """初始化提供商

        Args:
            api_key: API 密钥（从配置读取）
            base_url: API 基础 URL（支持私有部署）
        """
        self.api_key = api_key
        self.base_url = base_url

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称（如 "qwen", "glm", "deepseek"）"""
        pass

    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """支持的模型列表

        用于路由策略判断提供商是否支持指定模型。
        示例：["qwen-max", "qwen-plus", "qwen-turbo"]
        """
        pass

    @abstractmethod
    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """对话补全（同步模式）

        【实现要点】
        1. 构建提供商特定的请求格式
        2. 发送 HTTP 请求（带超时和重试）
        3. 解析响应并转换为 OpenAI 格式
        4. 处理错误（内容过滤、限流等）

        Args:
            request: OpenAI 兼容格式的请求

        Returns:
            OpenAI 兼容格式的响应
        """
        pass

    @abstractmethod
    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """流式对话补全

        【流式输出的优势】
        - 更快的首字响应时间（TTFT）
        - 更好的用户体验（打字机效果）
        - 支持长文本生成（边生成边显示）

        【SSE 格式】
        data: {"id":"...","choices":[{"delta":{"content":"你"}}]}

        data: {"id":"...","choices":[{"delta":{"content":"好"}}]}

        data: [DONE]

        Yields:
            SSE 格式的数据块
        """
        pass

    def supports_model(self, model: str) -> bool:
        """检查是否支持指定模型

        【匹配规则】
        - 精确匹配：model in supported_models
        - 前缀匹配：any(m in model for m in supported_models)

        支持带版本号的模型名：qwen-max-0403 → 匹配 qwen-max
        """
        return model in self.supported_models or any(m in model for m in self.supported_models)
