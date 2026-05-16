"""提供商基类

【核心概念】LLM Provider 抽象层
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

在多模型平台中，Provider 抽象层用于：
1. 统一接口：不同 LLM 提供商的 API 差异很大，需要统一抽象
2. 模型切换：支持在不改业务代码的情况下切换模型
3. 成本优化：根据模型能力选择性价比最优的模型

【问题背景】
- OpenAI、Azure OpenAI、国内模型（通义千问、DeepSeek）API 格式各异
- 需要支持模型 A/B 测试和灰度切换
- 需要跟踪每个模型的成本和性能

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

【技术选型】Provider 抽象方案对比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬───────────────┬───────────────┬───────────────┐
│ 方案               │ 扩展性        │ 维护成本      │ 类型安全      │
├────────────────────┼───────────────┼───────────────┼───────────────┤
│ 硬编码适配         │ 低           │ 高            │ 低           │
│ ✓ ABC 抽象基类    │ 高           │ 中            │ ✅ 强类型    │
│ Protocol 协议     │ 高           │ 低            │ 中           │
│ 配置驱动          │ 中           │ 低            │ 低           │
└────────────────────┴───────────────┴───────────────┴───────────────┘

【决策依据】选择 ABC 抽象基类：
1. 强类型约束：子类必须实现所有抽象方法，IDE 提示友好
2. 共享实现：基类可提供通用方法（如 health_check）
3. 易于扩展：新增 Provider 只需继承基类

【为什么使用 OpenAI 兼容格式？】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 格式               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 各家原生格式       │ • 完整功能                  │ • 需要多套客户端代码        │
│                    │ • 无功能损失                │ • 维护成本高                │
│                    │                             │ • 无法切换 Provider         │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ OpenAI 兼容 (选择) │ • 统一接口                  │ • 部分功能不兼容            │
│                    │ • 生态丰富                  │  （如视觉、函数调用）       │
│                    │ • 无需修改下游代码          │                              │
│                    │ • Provider 可替换           │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ LangChain 抽象     │ • 抽象完善                  │ • 依赖重（10MB+）           │
│                    │ • 功能丰富                  │ • 学习曲线                  │
│                    │                             │ • 性能开销                  │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择 OpenAI 兼容格式的原因】
1. Orchestrator 和 Model Gateway 可独立演进
2. 某个 Provider 故障时，可快速切换到备用 Provider
3. OpenAI SDK 生态完善，调试方便

【设计原则】抽象方法 vs 可选覆写
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────────────────────────┐
│ 抽象方法（必须实现）│ chat_completion, stream_chat_completion         │
│                    │ provider_name, supported_models, health_check   │
├────────────────────┼─────────────────────────────────────────────────┤
│ 可选覆写           │ validate_request, normalize_response            │
│                    │ get_model_info, supports_model                  │
├────────────────────┼─────────────────────────────────────────────────┤
│ 基类提供           │ _model_infos, provider_info                     │
└────────────────────┴─────────────────────────────────────────────────┘

【适配器模式实现】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

每个 Provider 实现 BaseLLMProvider 接口：

class QwenProvider(BaseLLMProvider):
    async def chat_completion(self, request):
        # 1. 转换请求格式（OpenAI → Qwen）
        qwen_request = self._convert_request(request)

        # 2. 调用 Qwen API
        response = await self._http_client.post(qwen_request)

        # 3. 转换响应格式（Qwen → OpenAI）
        return self._convert_response(response)

【Provider 职责】
- API 调用（HTTP 请求）
- 格式转换（原生 → OpenAI 兼容）
- 错误处理（重试、超时）
- Token 统计
- 健康检查
- 模型信息查询

【演进历史】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- v1.0: 硬编码适配各模型，维护困难
- v2.0: 添加 BaseLLMProvider 抽象基类
- v2.1: 添加 ModelInfo 和 health_check（当前版本）
- v2.2: 增加详细的成本计算说明和日志规范

【最佳实践】参考
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- LangChain Provider 设计: https://python.langchain.com/docs/integrations/llms/
- LiteLLM 统一接口: https://github.com/BerriAI/litellm
- OpenAI API 文档: https://platform.openai.com/docs/api-reference/chat
- 国内模型 API 对比: 见 docs/model-providers-comparison.md
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """模型元信息

    【用途】
    - 成本计算：根据 input/output token 数量计算费用
    - 能力查询：判断模型是否支持流式输出、工具调用
    - 路由决策：根据上下文窗口选择合适的模型

    【成本计算公式】
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    total_cost = (input_tokens / 1000) * input_cost_per_1k
               + (output_tokens / 1000) * output_cost_per_1k

    【不同模型的成本对比示例】
    ┌────────────────┬─────────────────┬──────────────────┬────────────────┐
    │ 模型           │ 输入价格        │ 输出价格         │ 上下文窗口     │
    │                │ (元/千token)    │ (元/千token)      │ (token)        │
    ├────────────────┼─────────────────┼──────────────────┼────────────────┤
    │ qwen-max       │ ¥0.02           │ ¥0.06            │ 32,768         │
    │ qwen-plus      │ ¥0.004          │ ¥0.012           │ 131,072        │
    │ qwen-turbo     │ ¥0.002          │ ¥0.006           │ 131,072        │
    │ deepseek-chat  │ ¥0.001          │ ¥0.002           │ 64,000         │
    │ gpt-4-turbo    │ $0.01           │ $0.03            │ 128,000        │
    └────────────────┴─────────────────┴──────────────────┴────────────────┘

    【成本计算示例】
    假设调用 qwen-max，输入 2000 tokens，输出 500 tokens：

    >>> model = ModelInfo(
    ...     name="qwen-max",
    ...     provider="qwen",
    ...     input_cost_per_1k=0.02,
    ...     output_cost_per_1k=0.06,
    ...     context_window=32768,
    ...     max_output_tokens=2000,
    ...     supports_streaming=True,
    ...     supports_tools=True,
    ... )
    >>> cost = model.estimate_cost(2000, 500)
    >>> print(f"成本: ¥{cost:.4f}")  # 成本: ¥0.0700
    >>> # 计算过程: (2000/1000)*0.02 + (500/1000)*0.06 = 0.04 + 0.03 = 0.07

    【路由决策示例】
    - 长文档处理：选择 context_window > 100000 的模型
    - 工具调用场景：选择 supports_tools=True 的模型
    - 成本敏感场景：优先选择 deepseek-chat

    【示例】
    >>> model = ModelInfo(
    ...     name="qwen-max",
    ...     provider="qwen",
    ...     input_cost_per_1k=0.02,
    ...     output_cost_per_1k=0.06,
    ...     context_window=32768,
    ...     max_output_tokens=2000,
    ...     supports_streaming=True,
    ...     supports_tools=True,
    ... )
    >>> model.supports_tools
    True
    >>> model.estimate_cost(1000, 500)  # 1k 输入 + 500 输出
    0.05
    """

    name: str = Field(..., description="模型名称，如 qwen-max、deepseek-chat")
    provider: str = Field(..., description="提供商名称，如 qwen、deepseek")
    input_cost_per_1k: float = Field(
        ...,
        ge=0.0,
        description="输入成本（元/千token）",
    )
    output_cost_per_1k: float = Field(
        ...,
        ge=0.0,
        description="输出成本（元/千token）",
    )
    context_window: int = Field(
        ...,
        gt=0,
        description="上下文窗口大小（token 数）",
    )
    max_output_tokens: int = Field(
        ...,
        gt=0,
        description="最大输出 token 数",
    )
    supports_streaming: bool = Field(
        default=True,
        description="是否支持流式输出",
    )
    supports_tools: bool = Field(
        default=False,
        description="是否支持工具调用（Function Calling）",
    )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算调用成本

        【计算公式】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        total_cost = (input_tokens / 1000) * input_cost_per_1k
                   + (output_tokens / 1000) * output_cost_per_1k

        【计算示例】
        qwen-max: input=2000, output=500
        cost = (2000/1000)*0.02 + (500/1000)*0.06
              = 0.04 + 0.03
              = 0.07 元

        【注意事项】
        - 输出 token 价格通常是输入的 2-3 倍
        - 实际计费可能有最小单位（如按次或按 1K token）
        - 某些模型有最低消费限制

        Args:
            input_tokens: 输入 token 数（包括 system prompt + 历史消息 + 用户输入）
            output_tokens: 输出 token 数（模型生成的回复）

        Returns:
            预估成本（元），精确到小数点后 6 位
        """
        input_cost = (input_tokens / 1000) * self.input_cost_per_1k
        output_cost = (output_tokens / 1000) * self.output_cost_per_1k
        total_cost = input_cost + output_cost

        # 【日志】成本估算（调试用）
        # logger.debug(
        #     "Cost estimation",
        #     extra={
        #         "model": self.name,
        #         "input_tokens": input_tokens,
        #         "output_tokens": output_tokens,
        #         "input_cost": input_cost,
        #         "output_cost": output_cost,
        #         "total_cost": total_cost,
        #     }
        # )

        return total_cost


class ProviderInfo(BaseModel):
    """提供商元信息

    【用途】
    - 服务发现：获取健康检查端点
    - 模型枚举：列出该提供商支持的所有模型
    - 路由决策：根据模型可用性选择提供商

    【示例】
    >>> provider_info = ProviderInfo(
    ...     name="qwen",
    ...     models=[model_info_1, model_info_2],
    ...     health_check_url="https://dashscope.aliyuncs.com/health",
    ... )
    >>> len(provider_info.models)
    2
    """

    name: str = Field(..., description="提供商名称，如 qwen、deepseek")
    models: list[ModelInfo] = Field(
        default_factory=list,
        description="该提供商支持的模型列表",
    )
    health_check_url: str = Field(
        ...,
        description="健康检查端点 URL",
    )

    def get_model(self, model_name: str) -> ModelInfo | None:
        """根据名称获取模型信息

        Args:
            model_name: 模型名称

        Returns:
            ModelInfo 或 None（未找到）
        """
        for model in self.models:
            if model.name == model_name:
                return model
        return None


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

    【抽象方法一览】
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ┌────────────────────────┬─────────────────────────────────────────────┐
    │ 抽象方法               │ 用途                                        │
    ├────────────────────────┼─────────────────────────────────────────────┤
    │ provider_name          │ 返回提供商名称（如 qwen、deepseek）         │
    │ supported_models       │ 返回支持的模型列表                          │
    │ chat_completion        │ 同步对话补全                                │
    │ stream_chat_completion │ 流式对话补全                                │
    │ health_check           │ 健康检查                                    │
    └────────────────────────┴─────────────────────────────────────────────┘

    【使用示例】
        provider = QwenProvider(api_key="...", base_url="...")
        response = await provider.chat_completion(request)

    【扩展新提供商】
    1. 创建新类继承 BaseLLMProvider
    2. 实现 chat_completion 和 stream_chat_completion
    3. 在 provider_factory 中注册

    【日志规范】
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    所有 Provider 应使用结构化日志：

    import structlog
    logger = structlog.get_logger()

    # 模型调用开始
    logger.info(
        "model_call_started",
        provider=self.provider_name,
        model=request.model,
        message_count=len(request.messages),
        stream=request.stream,
    )

    # 模型调用完成
    logger.info(
        "model_call_completed",
        provider=self.provider_name,
        model=response.model,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
        latency_ms=elapsed_ms,
        estimated_cost=model_info.estimate_cost(
            response.usage.prompt_tokens,
            response.usage.completion_tokens
        ),
    )

    # 模型调用失败
    logger.error(
        "model_call_failed",
        provider=self.provider_name,
        model=request.model,
        error=str(e),
        error_type=type(e).__name__,
        will_retry=should_retry,
    )
    """

    def __init__(self, api_key: str, base_url: str):
        """初始化提供商

        Args:
            api_key: API 密钥（从配置读取，禁止硬编码）
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
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        1. 构建提供商特定的请求格式
           - 将 OpenAI 格式转换为目标 Provider 格式
           - 处理特殊字段映射（如 tool_calls → functions）

        2. 发送 HTTP 请求（带超时和重试）
           - 设置合理的超时（建议 30-60 秒）
           - 实现指数退避重试（最多 3 次）
           - 仅对可重试错误重试（网络错误、5xx）

        3. 解析响应并转换为 OpenAI 格式
           - 提取 token 使用量
           - 处理 stop_reason 的差异

        4. 处理错误（内容过滤、限流等）
           - 内容过滤：返回特殊 finish_reason
           - 限流：抛出 RateLimitError
           - 服务不可用：抛出 ServiceUnavailableError

        【请求生命周期日志】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        import structlog
        import time

        logger = structlog.get_logger()

        async def chat_completion(self, request: ChatCompletionRequest):
            start_time = time.time()
            request_id = request.id or str(uuid.uuid4())

            # 【日志】请求开始
            logger.info(
                "chat_completion_started",
                request_id=request_id,
                provider=self.provider_name,
                model=request.model,
                message_count=len(request.messages),
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            try:
                response = await self._call_api(request)
                elapsed_ms = (time.time() - start_time) * 1000

                # 【日志】请求成功
                logger.info(
                    "chat_completion_completed",
                    request_id=request_id,
                    provider=self.provider_name,
                    model=response.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                    finish_reason=response.choices[0].finish_reason if response.choices else None,
                    latency_ms=round(elapsed_ms, 2),
                )

                return response

            except RateLimitError as e:
                # 【日志】限流
                logger.warning(
                    "chat_completion_rate_limited",
                    request_id=request_id,
                    provider=self.provider_name,
                    retry_after=e.retry_after,
                )
                raise

            except Exception as e:
                # 【日志】请求失败
                elapsed_ms = (time.time() - start_time) * 1000
                logger.error(
                    "chat_completion_failed",
                    request_id=request_id,
                    provider=self.provider_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    latency_ms=round(elapsed_ms, 2),
                )
                raise

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
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        ┌────────────────────┬─────────────────────────────────────────────────┐
        │ 指标               │ 流式输出 vs 同步输出                            │
        ├────────────────────┼─────────────────────────────────────────────────┤
        │ 首字响应时间(TTFT) │ 200-500ms vs 2-10s（大幅改善用户体验）          │
        │ 内存占用           │ 低（边生成边发送）vs 高（全量缓存）             │
        │ 用户体验           │ 打字机效果，可提前中断                          │
        │ 错误处理           │ 复杂（需要处理中断流）vs 简单                   │
        │ 适用场景           │ 长文本生成、实时对话 vs 批量处理、后端调用      │
        └────────────────────┴─────────────────────────────────────────────────┘

        【SSE（Server-Sent Events）格式】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"你"},"index":0}]}

        data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"好"},"index":0}]}

        data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"！"},"index":0}]}

        data: [DONE]

        【实现要点】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        1. 使用 httpx 的流式请求
           async with client.stream("POST", url, json=data) as response:
               async for line in response.aiter_lines():
                   if line.startswith("data: "):
                       yield line

        2. 处理连接中断
           - 记录已发送的 token 数
           - 支持断点续传（部分 Provider 支持）

        3. 错误处理
           - 网络中断：抛出 StreamInterruptedError
           - 内容过滤：在流中返回 finish_reason: "content_filter"

        【日志规范】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # 流式开始
        logger.info(
            "stream_started",
            request_id=request_id,
            provider=self.provider_name,
            model=request.model,
        )

        # 流式完成
        logger.info(
            "stream_completed",
            request_id=request_id,
            provider=self.provider_name,
            total_tokens=total_tokens,
            latency_ms=elapsed_ms,
        )

        # 流式中断
        logger.warning(
            "stream_interrupted",
            request_id=request_id,
            provider=self.provider_name,
            tokens_sent=tokens_sent,
            error=str(e),
        )

        Yields:
            SSE 格式的数据块（data: {...} 格式）
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

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查

        【用途】
        - 路由策略：判断 Provider 是否可用
        - 监控告警：持续不可用时触发告警
        - 负载均衡：优先路由到健康的 Provider

        【实现要点】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        1. 检测策略选择：
        ┌────────────────────┬─────────────────┬─────────────────────────────┐
        │ 策略               │ 延迟            │ 准确性                      │
        ├────────────────────┼─────────────────┼─────────────────────────────┤
        │ GET /models        │ 低 (~100ms)     │ 中（API 可用但可能限流）    │
        │ 简单补全请求       │ 高 (~500ms)     │ 高（实际测试推理能力）      │
        │ TCP connect only   │ 极低 (~10ms)    │ 低（无法检测 API 异常）     │
        │ ✓ 推荐策略        │ 低延迟 + 准确   │ GET /models + 短超时       │
        └────────────────────┴─────────────────┴─────────────────────────────┘

        2. 超时设置：
        - 建议超时: 3-5 秒（生产环境）
        - 重试次数: 0（健康检查不应重试）

        3. 失败判定条件：
        - HTTP 状态码 >= 500: 服务端错误，判定为不健康
        - HTTP 状态码 429: 限流，仍判定为健康（服务可用）
        - HTTP 状态码 401/403: 认证问题，需告警但服务可能正常
        - 连接超时: 网络问题，判定为不健康
        - SSL 错误: 证书问题，判定为不健康

        【熔断器集成】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        健康检查结果应与熔断器联动：

        from resilience import CircuitBreaker

        class QwenProvider(BaseLLMProvider):
            def __init__(self, ...):
                self._circuit_breaker = CircuitBreaker(
                    failure_threshold=5,
                    recovery_timeout=60,
                )

            async def health_check(self) -> bool:
                # 如果熔断器处于 OPEN 状态，直接返回 False
                if self._circuit_breaker.is_open:
                    return False

                try:
                    result = await self._do_health_check()
                    if result:
                        self._circuit_breaker.record_success()
                    else:
                        self._circuit_breaker.record_failure()
                    return result
                except Exception:
                    self._circuit_breaker.record_failure()
                    return False

        【日志规范】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        健康检查应记录结构化日志：

        import structlog
        logger = structlog.get_logger()

        # 成功
        logger.info(
            "health_check_passed",
            provider=self.provider_name,
            latency_ms=elapsed_ms,
        )

        # 失败
        logger.warning(
            "health_check_failed",
            provider=self.provider_name,
            error=str(e),
            error_type=type(e).__name__,
            consecutive_failures=self._consecutive_failures,
        )

        【告警阈值】
        - 连续失败 3 次: 发送告警
        - 连续失败 5 次: 触发熔断
        - 恢复后: 发送恢复通知

        Returns:
            True 表示健康，False 表示不健康
        """
        pass

    def get_model_info(self, model_name: str) -> ModelInfo | None:
        """获取模型元信息

        【用途】
        - 成本预估：根据 token 数量计算费用
        - 能力查询：判断模型是否支持特定功能
        - 参数校验：检查 max_tokens 是否超出限制

        【查找策略】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        1. 精确匹配：model_name == model.name
        2. 前缀匹配：model_name.startswith(model.name)

        前缀匹配用于处理带版本号的模型名：
        - qwen-max-0403 → 匹配 qwen-max
        - gpt-4-0125-preview → 匹配 gpt-4

        【使用示例】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        >>> provider = QwenProvider(...)
        >>> model_info = provider.get_model_info("qwen-max")
        >>> if model_info:
        ...     cost = model_info.estimate_cost(1000, 500)
        ...     print(f"Estimated cost: ¥{cost}")
        Estimated cost: ¥0.05

        【成本监控集成】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        每次获取模型信息后，建议记录成本估算：

        model_info = provider.get_model_info(model)
        if model_info:
            logger.debug(
                "model_info_retrieved",
                model=model,
                provider=self.provider_name,
                input_cost_per_1k=model_info.input_cost_per_1k,
                output_cost_per_1k=model_info.output_cost_per_1k,
                context_window=model_info.context_window,
                supports_tools=model_info.supports_tools,
            )

        Args:
            model_name: 模型名称（如 qwen-max）

        Returns:
            ModelInfo 或 None（未找到）
        """
        for model in self._model_infos:
            if model.name == model_name or model_name.startswith(model.name):
                return model
        return None

    def validate_request(self, request: ChatCompletionRequest) -> list[str]:
        """校验请求参数

        【用途】
        - 提前发现问题，避免无效 API 调用
        - 减少错误成本（某些 Provider 按请求计费）

        【校验项】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        ┌────────────────────┬─────────────────────────────────────────────────┐
        │ 校验项             │ 错误信息示例                                    │
        ├────────────────────┼─────────────────────────────────────────────────┤
        │ 模型支持           │ Model 'gpt-4' is not supported by provider      │
        │ max_tokens 限制    │ max_tokens (4096) exceeds model limit (2048)    │
        │ 温度参数范围       │ temperature (3.0) must be between 0.0 and 2.0   │
        │ 消息非空           │ messages cannot be empty                        │
        └────────────────────┴─────────────────────────────────────────────────┘

        【提前校验的价值】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        1. 成本节约：
           - 某些 Provider 即使请求失败也会计费
           - 提前校验可以避免无效请求

        2. 用户体验：
           - 更快的错误反馈（无需等待 API 超时）
           - 更清晰的错误信息

        3. 系统稳定性：
           - 减少无效请求对下游服务的压力
           - 避免错误请求触发限流

        【日志规范】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        errors = self.validate_request(request)
        if errors:
            logger.warning(
                "request_validation_failed",
                provider=self.provider_name,
                model=request.model,
                errors=errors,
            )

        Args:
            request: 待校验的请求

        Returns:
            错误信息列表，空列表表示校验通过
        """
        errors: list[str] = []

        # 校验模型
        if request.model and not self.supports_model(request.model):
            errors.append(
                f"Model '{request.model}' is not supported by provider '{self.provider_name}'"
            )

        # 校验 max_tokens
        if request.model:
            model_info = self.get_model_info(request.model)
            if model_info and request.max_tokens > model_info.max_output_tokens:
                errors.append(
                    f"max_tokens ({request.max_tokens}) exceeds model limit ({model_info.max_output_tokens})"
                )

        # 校验温度
        if not 0.0 <= request.temperature <= 2.0:
            errors.append(f"temperature ({request.temperature}) must be between 0.0 and 2.0")

        # 校验消息
        if not request.messages:
            errors.append("messages cannot be empty")

        return errors

    def normalize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """标准化响应格式

        【用途】
        - 统一不同 Provider 的响应格式
        - 填充缺失字段
        - 确保下游可以统一处理

        【标准化处理流程】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        ┌────────────────────┬─────────────────────────────────────────────────┐
        │ 处理步骤           │ 说明                                            │
        ├────────────────────┼─────────────────────────────────────────────────┤
        │ 1. 确保 id 存在    │ 缺失时生成 chatcmpl-{timestamp}                 │
        │ 2. 确保 object     │ 固定为 "chat.completion"                        │
        │ 3. 确保 created    │ 缺失时使用当前时间戳                            │
        │ 4. 确保 usage 完整 │ 填充缺失的 token 统计字段                       │
        │ 5. 规范化 finish_reason │ 统一为 stop/length/tool_calls/content_filter │
        └────────────────────┴─────────────────────────────────────────────────┘

        【不同 Provider 的响应差异】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
        │ Provider           │ 特殊字段                    │ 标准化处理                  │
        ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
        │ 通义千问           │ output.finish_reason        │ 映射到 choices[].finish_reason│
        │ 智谱 GLM           │ created 为字符串            │ 转换为整数时间戳            │
        │ DeepSeek           │ usage 可能为空              │ 填充默认值 0                │
        └────────────────────┴─────────────────────────────┴─────────────────────────────┘

        【finish_reason 规范化】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        ┌────────────────────┬─────────────────────────────────────────────────┐
        │ 标准值             │ 含义                                            │
        ├────────────────────┼─────────────────────────────────────────────────┤
        │ stop               │ 正常结束（遇到 stop 序列或完整回复）            │
        │ length             │ 达到 max_tokens 限制                            │
        │ tool_calls         │ 模型调用了工具                                  │
        │ content_filter     │ 内容被安全过滤                                  │
        └────────────────────┴─────────────────────────────────────────────────┘

        其他值统一转换为 "stop" 以保证兼容性。

        Args:
            response: 原始响应字典

        Returns:
            标准化后的响应字典
        """
        import time

        normalized = response.copy()

        # 确保 id 存在
        if "id" not in normalized or not normalized["id"]:
            normalized["id"] = f"chatcmpl-{int(time.time() * 1000)}"

        # 确保 object 字段
        if "object" not in normalized:
            normalized["object"] = "chat.completion"

        # 确保 created 存在
        if "created" not in normalized:
            normalized["created"] = int(time.time())

        # 确保 usage 完整
        if "usage" in normalized:
            usage = normalized["usage"]
            usage.setdefault("prompt_tokens", 0)
            usage.setdefault("completion_tokens", 0)
            usage.setdefault("total_tokens", usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))

        # 规范化 finish_reason
        if "choices" in normalized:
            for choice in normalized["choices"]:
                if "finish_reason" in choice:
                    # 统一 finish_reason 格式
                    finish_reason = choice["finish_reason"]
                    if finish_reason not in ("stop", "length", "tool_calls", "content_filter"):
                        choice["finish_reason"] = "stop"

        return normalized

    @property
    def _model_infos(self) -> list[ModelInfo]:
        """模型信息列表（子类需要覆盖）

        【默认实现】
        使用 supported_models 生成基础 ModelInfo，
        子类应覆盖此属性以提供完整信息。

        Returns:
            模型信息列表
        """
        # 默认实现：使用通用参数
        return [
            ModelInfo(
                name=model,
                provider=self.provider_name,
                input_cost_per_1k=0.0,  # 子类应覆盖
                output_cost_per_1k=0.0,
                context_window=8192,
                max_output_tokens=4096,
            )
            for model in self.supported_models
        ]

    @property
    def provider_info(self) -> ProviderInfo:
        """获取提供商元信息

        Returns:
            ProviderInfo 实例
        """
        return ProviderInfo(
            name=self.provider_name,
            models=self._model_infos,
            health_check_url=f"{self.base_url}/models",
        )
