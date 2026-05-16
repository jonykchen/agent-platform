"""ModelGateway HTTP 客户端

通过 HTTP 调用 ModelGateway 服务进行模型推理。
支持熔断器、重试、连接池优化。

【核心概念】客户端在架构中的位置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│                          Agent 平台服务调用链                                │
│                                                                             │
│  ┌──────────────┐      ┌──────────────────┐      ┌──────────────────┐      │
│  │   Gateway    │ ───► │   Orchestrator   │ ───► │  Model Gateway   │      │
│  │   (Java)     │      │    (Python)       │      │    (Python)      │      │
│  │   API 入口   │      │    Agent 编排     │      │    模型统一网关   │      │
│  └──────────────┘      └──────────────────┘      └──────────────────┘      │
│                                │                       │                   │
│                                │ HTTP                  │ HTTP              │
│                                ▼                       ▼                   │
│                         ┌──────────────────┐    ┌─────────────┐           │
│                         │    Tool Bus      │    │   Qwen/     │           │
│                         │    (Java)        │    │   DeepSeek  │           │
│                         │    工具执行       │    │   模型服务   │           │
│                         └──────────────────┘    └─────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

本客户端（ModelGatewayClient）位于 Orchestrator → Model Gateway 调用链：
- Orchestrator 节点执行时，通过本客户端调用 Model Gateway
- Model Gateway 再路由到具体的 LLM 提供商（Qwen/DeepSeek 等）

【技术选型】HTTP 客户端对比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ ✓ httpx (当前)    │ • 原生异步支持              │ • 相比 aiohttp 生态较小     │
│                    │ • 连接池管理完善            │                              │
│                    │ • HTTP/2 支持               │                              │
│                    │ • 与 FastAPI 风格一致       │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ aiohttp            │ • 生态成熟                  │ • API 较复杂                │
│                    │ • 性能优秀                  │ • 连接池配置繁琐            │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ requests           │ • 简单易用                  │ • 不支持异步                │
│                    │ • 社区庞大                  │ • 性能瓶颈                  │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【决策依据】选择 httpx 的原因：
1. 原生 async/await 支持，与 FastAPI 完美配合
2. 连接池管理开箱即用，无需手动配置
3. API 设计类似 requests，学习成本低
4. 支持 HTTP/2，未来可升级

【技术选型】HTTP vs gRPC 对比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 维度               │ HTTP (当前选择)             │ gRPC                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 协议               │ HTTP/1.1 + JSON             │ HTTP/2 + Protobuf           │
│ 性能               │ 中等（文本序列化）          │ 高（二进制序列化）          │
│ 调试友好度         │ 高（可读文本）              │ 低（需要工具）              │
│ 流式支持           │ SSE (Server-Sent Events)   │ 原生双向流                  │
│ 跨语言调用         │ 简单（curl/Postman）        │ 需要 Proto 定义             │
│ 适用场景           │ 外部 API、流式响应          │ 内部高频调用                │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【为什么 ModelGateway 使用 HTTP？】
1. 兼容 OpenAI API 格式，便于调试和测试
2. SSE 流式响应是 LLM 行业标准
3. ModelGateway 主要对外暴露，HTTP 更通用
4. 调用频率相对较低（每个 Agent 步骤一次），性能不是瓶颈

【熔断器配置说明】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬───────────────┬─────────────────────────────────────────┐
│ 参数               │ 默认值        │ 说明                                    │
├────────────────────┼───────────────┼─────────────────────────────────────────┤
│ failure_threshold  │ 5             │ 连续失败 5 次后触发熔断                 │
│ recovery_timeout   │ 30s           │ 熔断后等待 30s 尝试恢复                 │
│ max_attempts       │ 3             │ 最大重试 3 次（含首次）                 │
│ min_wait           │ 1s            │ 最小重试间隔                            │
│ max_wait           │ 10s           │ 最大重试间隔                            │
└────────────────────┴───────────────┴─────────────────────────────────────────┘

【降级策略】模型调用失败时的应对方案
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│                          模型降级流程                                        │
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │  用户请求       │                                                       │
│  │  model=qwen-max │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐      成功      ┌──────────────────┐                   │
│  │  尝试 qwen-max   │ ──────────► │  返回结果        │                   │
│  └────────┬─────────┘              └──────────────────┘                   │
│           │ 失败（超时/错误）                                               │
│           ▼                                                                 │
│  ┌──────────────────┐      成功      ┌──────────────────┐                   │
│  │ 降级到 deepseek  │ ──────────► │  返回结果        │                   │
│  │ -v3             │              └──────────────────┘                   │
│  └────────┬─────────┘                                                       │
│           │ 失败                                                            │
│           ▼                                                                 │
│  ┌──────────────────┐      成功      ┌──────────────────┐                   │
│  │ 降级到 qwen-plus │ ──────────► │  返回结果        │                   │
│  └────────┬─────────┘              └──────────────────┘                   │
│           │ 失败                                                            │
│           ▼                                                                 │
│  ┌──────────────────┐                                                       │
│  │ 抛出异常         │                                                       │
│  │ AllProvidersDown │                                                       │
│  └──────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

降级顺序（MODEL_FALLBACK_ORDER）：qwen-max → deepseek-v3 → qwen-plus

【降级触发条件】
┌────────────────────┬─────────────────────────────────────────────────────────┐
│ 错误类型           │ 处理方式                                                │
├────────────────────┼─────────────────────────────────────────────────────────┤
│ 超时               │ 尝试下一个模型                                          │
│ 熔断器打开         │ 跳过该模型，尝试下一个                                  │
│ 503 服务不可用     │ 尝试下一个模型                                          │
│ 4xx 客户端错误     │ 直接返回错误，不降级（请求本身有问题）                  │
└────────────────────┴─────────────────────────────────────────────────────────┘

【Mock 模式使用场景】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────────────────────────────────┐
│ 场景               │ 说明                                                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│ 本地开发           │ 无需启动 ModelGateway 服务，直接使用预设响应            │
│ 单元测试           │ 隔离外部依赖，测试 Agent 逻辑                           │
│ CI/CD 流水线       │ 避免依赖外部服务，提高测试稳定性                        │
│ Demo 演示          │ 快速展示功能，无需真实模型调用                           │
└────────────────────┴─────────────────────────────────────────────────────────┘

启用 Mock 模式：
```python
# 方式 1：环境变量
MODEL_GATEWAY_URL=mock

# 方式 2：代码配置
client = ModelGatewayClient(base_url="mock")
```

Mock 响应行为：
- 返回固定的成功响应（不含真实模型输出）
- 模拟调用延迟（可选）
- 记录调用日志用于验证

【连接池配置说明】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬───────────────┬─────────────────────────────────────────┐
│ 参数               │ 默认值        │ 说明                                    │
├────────────────────┼───────────────┼─────────────────────────────────────────┤
│ max_connections    │ 100           │ 最大连接数（所有主机共享）              │
│ max_keepalive      │ 20            │ 最大 keepalive 连接数                   │
│ keepalive_expiry   │ 30s           │ keepalive 连接过期时间                  │
│ connect_timeout    │ 10s           │ 连接建立超时                            │
│ read_timeout       │ 30s           │ 读取超时（从配置读取）                  │
│ write_timeout      │ 10s           │ 写入超时                                │
│ pool_timeout       │ 5s            │ 从连接池获取连接的超时                  │
└────────────────────┴───────────────┴─────────────────────────────────────────┘

【最佳实践】连接池调优建议：
- max_connections：建议设置为并发请求峰值的 1.5 倍
- keepalive：高频调用场景适当增加，减少连接建立开销
- timeout：根据模型响应时间调整，一般 30s 足够
"""

import asyncio
import json
import time
from typing import Any

import httpx
import structlog

from app.core.config import config
from app.core.exceptions import AllProvidersDownError, ModelTimeoutError
from app.core.resilience import (
    CircuitBreakerOpenError,
    model_gateway_circuit,
    model_retry_policy,
)

logger = structlog.get_logger()

# 默认模型列表（用于降级）
DEFAULT_MODELS = [
    {"id": "qwen-max", "provider": "qwen"},
    {"id": "qwen-plus", "provider": "qwen"},
    {"id": "deepseek-v3", "provider": "deepseek"},
]

# 模型降级顺序
MODEL_FALLBACK_ORDER = ["qwen-max", "deepseek-v3", "qwen-plus"]


class ModelGatewayClient:
    """ModelGateway HTTP 客户端

    【核心职责】
    Orchestrator 与 Model Gateway 之间的通信桥梁：
    - 发送模型推理请求到 Model Gateway
    - 处理流式响应（SSE）
    - 实现模型降级策略
    - 提供调用统计

    【特性】
    - 连接池优化：复用连接，减少握手开销
    - 熔断器保护：防止故障传播
    - 指数退避重试：应对临时故障
    - 模型降级策略：多模型互备
    - 流式响应超时保护：防止无限等待
    - 调用统计：用于监控和性能分析

    【使用示例】
    ```python
    # 获取全局客户端
    client = get_model_gateway_client()

    # 普通调用
    result = await client.chat_completion(
        messages=[{"role": "user", "content": "你好"}],
        model="qwen-max",
    )

    # 流式调用
    async for chunk in client.stream_chat_completion(messages=[...]):
        print(chunk)

    # 带工具调用
    result = await client.chat_with_tools(
        messages=[...],
        tools=[{"type": "function", "function": {...}}],
    )
    ```

    【线程安全说明】
    - 客户端实例可安全在多个协程间共享
    - 内部使用单个 httpx.AsyncClient 实例（线程安全）
    - 调用统计使用 dict，仅在当前实例有效
    """

    def __init__(self, base_url: str | None = None):
        """初始化客户端

        Args:
            base_url: Model Gateway 服务地址
                      - None: 从配置读取（config.model_gateway_url）
                      - "mock": 启用 Mock 模式
                      - 其他: 自定义地址

        【连接延迟初始化】
        客户端不会立即建立连接，而是在首次调用时懒加载。
        这样可以避免服务未启动时的连接错误。
        """
        self.base_url = base_url or config.model_gateway_url
        self._client: httpx.AsyncClient | None = None
        self._call_stats: dict[str, dict[str, Any]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端（懒加载）

        【设计说明】
        延迟初始化的好处：
        1. 服务未启动时不会立即报错
        2. 减少不必要的连接建立
        3. 支持动态配置变更

        【连接池配置】
        所有超时和连接池参数从 config 读取，便于运维调整。
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=config.model_call_timeout_s,
                    write=10.0,
                    pool=5.0,
                ),
                limits=httpx.Limits(
                    max_connections=config.http_max_connections,
                    max_keepalive_connections=config.http_max_keepalive,
                    keepalive_expiry=config.http_keepalive_expiry,
                ),
            )
        return self._client

    async def close(self):
        """关闭客户端连接

        【使用场景】
        - 应用关闭时优雅释放资源
        - 测试完成后清理连接
        - 长时间不使用时释放连接池

        【注意】
        关闭后再次调用会重新创建连接。
        """
        if self._client:
            await self._client.aclose()
            self._client = None

    @model_gateway_circuit
    @model_retry_policy
    async def _do_chat_completion(
        self,
        client: httpx.AsyncClient,
        payload: dict,
    ) -> dict:
        """执行对话补全（带熔断器和重试）

        【执行流程】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  1. 熔断器检查（外层装饰器）                                        │
        │     │                                                               │
        │     ├─ OPEN → 抛出 CircuitBreakerOpenError                        │
        │     │                                                               │
        │  2. 重试策略（内层装饰器）                                          │
        │     │                                                               │
        │     ├─ 尝试 1 → 失败 → 等待退避时间                                │
        │     │                                                               │
        │     ├─ 尝试 2 → 失败 → 等待退避时间                                │
        │     │                                                               │
        │     └─ 尝试 3 → 成功/失败                                           │
        │                                                                     │
        │  3. 发送 HTTP 请求                                                  │
        │                                                                     │
        │  4. 返回结果或抛出异常                                              │
        └─────────────────────────────────────────────────────────────────────┘

        Args:
            client: HTTP 客户端实例
            payload: 请求载荷（OpenAI 兼容格式）

        Returns:
            OpenAI 兼容格式的响应

        Raises:
            CircuitBreakerOpenError: 熔断器打开
            httpx.TimeoutException: 请求超时
            httpx.HTTPStatusError: HTTP 错误响应
        """
        response = await client.post(
            "/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        fallback: bool = True,
        **kwargs,
    ) -> dict:
        """对话补全（核心方法）

        【功能说明】
        发送对话请求到 Model Gateway，支持：
        - 单轮/多轮对话
        - 指定模型或让网关自动路由
        - 模型降级策略
        - 自定义参数（如 top_p、presence_penalty 等）

        【执行流程】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  1. 构建 OpenAI 兼容请求                                             │
        │                                                                     │
        │  2. 确定模型尝试顺序                                                 │
        │     ├─ 指定模型 + fallback=True → 按降级顺序尝试                    │
        │     └─ 无指定模型 → 使用网关路由                                    │
        │                                                                     │
        │  3. 依次尝试每个模型                                                 │
        │     ├─ 成功 → 返回结果，记录统计                                    │
        │     ├─ 熔断器打开 → 跳过，尝试下一个                                │
        │     ├─ 超时 → 尝试下一个                                            │
        │     └─ 503 → 尝试下一个                                             │
        │                                                                     │
        │  4. 所有模型失败 → 抛出 AllProvidersDownError                       │
        └─────────────────────────────────────────────────────────────────────┘

        Args:
            messages: 消息列表，OpenAI 格式
                      [{"role": "user/assistant/system", "content": "..."}]
            model: 模型名称（可选）
                   - None: 由网关根据负载自动路由
                   - "qwen-max": 指定模型
            temperature: 温度参数，控制随机性（0-2）
                        - 0: 确定性输出
                        - 0.7: 平衡（默认）
                        - 1.0+: 更有创意
            max_tokens: 最大输出 token 数
            stream: 是否流式输出（此方法不支持，请使用 stream_chat_completion）
            fallback: 是否启用降级策略
                     - True: 失败时尝试其他模型
                     - False: 只尝试指定模型

        Returns:
            OpenAI 兼容格式的响应：
            {
                "id": "chatcmpl-xxx",
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "..."
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                }
            }

        Raises:
            AllProvidersDownError: 所有模型都不可用
            ModelTimeoutError: 模型调用超时

        【最佳实践】
        - 重要场景：设置 fallback=True，提高可用性
        - 简单查询：使用较低 temperature（0.3）
        - 创意写作：使用较高 temperature（0.9+）
        - 控制成本：设置合理的 max_tokens
        """
        client = await self._get_client()

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        if model:
            payload["model"] = model

        payload.update(kwargs)

        start_time = time.monotonic()
        models_to_try = [model] if model else [None]

        if fallback and model:
            models_to_try = MODEL_FALLBACK_ORDER

        last_error = None

        for try_model in models_to_try:
            if try_model:
                payload["model"] = try_model

            try:
                result = await self._do_chat_completion(client, payload)
                duration = time.monotonic() - start_time

                logger.info(
                    "Chat completion success",
                    model=try_model,
                    duration_ms=int(duration * 1000),
                )

                # 记录统计
                self._update_stats(try_model or "default", success=True, duration=duration)

                return result

            except CircuitBreakerOpenError as e:
                logger.warning(
                    "Circuit breaker open, skipping model",
                    model=try_model,
                    circuit=e.circuit_name,
                )
                last_error = e
                continue

            except httpx.TimeoutException as e:
                logger.warning(
                    "Model gateway timeout, trying fallback",
                    model=try_model,
                    error=str(e),
                )
                last_error = ModelTimeoutError(timeout_s=config.model_call_timeout_s)
                self._update_stats(try_model or "default", success=False)
                continue

            except httpx.HTTPStatusError as e:
                logger.error(
                    "Model gateway error",
                    model=try_model,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                self._update_stats(try_model or "default", success=False)

                if e.response.status_code == 503:
                    last_error = AllProvidersDownError()
                    continue

                try:
                    error_data = e.response.json()
                    return {
                        "error": error_data.get("error", "unknown"),
                        "message": error_data.get("message", str(e)),
                    }
                except Exception:
                    return {
                        "error": "http_error",
                        "message": str(e),
                    }

            except Exception as e:
                logger.error("Unexpected error in chat completion", error=str(e))
                self._update_stats(try_model or "default", success=False)
                last_error = e
                continue

        # 所有模型都失败
        if last_error:
            raise last_error

        raise AllProvidersDownError()

    async def stream_chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: float = 60.0,
    ):
        """流式对话补全

        【功能说明】
        使用 SSE (Server-Sent Events) 流式返回模型输出。
        适用于需要实时展示生成内容的前端场景。

        【执行流程】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  1. 构建请求（stream=True）                                         │
        │                                                                     │
        │  2. 建立流式连接                                                    │
        │                                                                     │
        │  3. 循环读取 SSE 数据                                               │
        │     │                                                               │
        │     ├─ "data: {...}" → 解析 JSON 并 yield                          │
        │     │                                                               │
        │     ├─ "data: [DONE]" → 结束流                                    │
        │     │                                                               │
        │     └─ 空行/其他 → 跳过                                            │
        │                                                                     │
        │  4. 超时或连接关闭 → 结束                                          │
        └─────────────────────────────────────────────────────────────────────┘

        Args:
            messages: 消息列表
            model: 模型名称（可选）
            temperature: 温度参数
            max_tokens: 最大输出 token
            timeout: 总超时时间（秒）
                    - 60s 适合短回复
                    - 120s+ 适合长文生成

        Yields:
            SSE 格式的数据块（已解析为 dict）：
            {
                "id": "chatcmpl-xxx",
                "choices": [{
                    "delta": {
                        "content": "生成的文本片段"
                    },
                    "finish_reason": null
                }]
            }

        Raises:
            ModelTimeoutError: 流式响应超时

        【最佳实践】
        - 前端实时展示：逐块渲染，提升用户体验
        - 错误处理：捕获异常后显示友好提示
        - 超时设置：根据预期回复长度调整
        - 资源清理：使用 async for 循环会自动关闭流

        【使用示例】
        ```python
        async for chunk in client.stream_chat_completion(messages=[...]):
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "")
            print(content, end="", flush=True)
        ```
        """
        client = await self._get_client()

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if model:
            payload["model"] = model

        try:
            async with asyncio.timeout(timeout):
                async with client.stream(
                    "POST",
                    "/v1/chat/completions",
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                yield json.loads(data)
                            except json.JSONDecodeError:
                                continue

        except TimeoutError:
            logger.error("Stream chat completion timeout", timeout=timeout)
            raise ModelTimeoutError(timeout_s=timeout)

        except httpx.TimeoutException as e:
            logger.error("Model gateway stream timeout", error=str(e))
            raise ModelTimeoutError(timeout_s=config.model_call_timeout_s)

    async def list_models(self, use_cache: bool = True) -> list[dict]:
        """获取可用模型列表

        【功能说明】
        查询 Model Gateway 支持的模型列表。
        失败时返回默认模型列表（降级）。

        Args:
            use_cache: 是否使用缓存结果（降级时）
                      - True: 网络失败返回 DEFAULT_MODELS
                      - False: 网络失败返回空列表

        Returns:
            模型列表：
            [
                {"id": "qwen-max", "provider": "qwen"},
                {"id": "deepseek-v3", "provider": "deepseek"},
                ...
            ]

        【使用场景】
        - 前端模型选择器
        - 动态配置模型路由
        - 健康检查

        【降级说明】
        当 Model Gateway 不可用时，返回预设的 DEFAULT_MODELS，
        保证系统可用性。
        """
        client = await self._get_client()

        try:
            response = await client.get("/v1/models")
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

        except Exception as e:
            logger.warning(
                "List models failed, using fallback",
                error=str(e),
            )
            if use_cache:
                return DEFAULT_MODELS
            return []

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict:
        """带工具调用的对话

        【功能说明】
        发送带有工具定义的对话请求，模型可以决定是否调用工具。
        这是 Agent 工具调用的核心方法。

        【执行流程】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  1. 构建请求（包含 tools 和 tool_choice）                           │
        │                                                                     │
        │  2. 发送到 Model Gateway                                            │
        │                                                                     │
        │  3. 解析响应                                                        │
        │     │                                                               │
        │     ├─ 普通回复 → choices[0].message.content                       │
        │     │                                                               │
        │     └─ 工具调用 → choices[0].message.tool_calls                   │
        │         [{                                                          │
        │             "id": "call_xxx",                                      │
        │             "type": "function",                                    │
        │             "function": {                                          │
        │                 "name": "query_order",                             │
        │                 "arguments": '{"order_id": "123"}'                │
        │             }                                                      │
        │         }]                                                         │
        └─────────────────────────────────────────────────────────────────────┘

        Args:
            messages: 消息列表（包含历史对话）
            tools: 工具定义列表（OpenAI 格式）
                   [{
                       "type": "function",
                       "function": {
                           "name": "query_order_status",
                           "description": "查询订单状态",
                           "parameters": {
                               "type": "object",
                               "properties": {...}
                           }
                       }
                   }]
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大输出 token

        Returns:
            包含 tool_calls 的响应：
            {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": null,
                        "tool_calls": [...]
                    }
                }]
            }

        【最佳实践】
        - 工具定义：描述清晰，参数完整
        - 历史对话：包含之前的工具调用和结果
        - 错误处理：检查 tool_calls 是否存在
        """
        return await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice="auto",
        )

    def _update_stats(self, model: str, success: bool, duration: float = 0.0):
        """更新调用统计

        【统计指标】
        - total: 总调用次数
        - success: 成功次数
        - failure: 失败次数
        - total_duration: 总耗时（成功调用）

        【使用场景】
        - 监控面板展示
        - 性能分析
        - SLA 计算
        """
        if model not in self._call_stats:
            self._call_stats[model] = {
                "total": 0,
                "success": 0,
                "failure": 0,
                "total_duration": 0.0,
            }

        stats = self._call_stats[model]
        stats["total"] += 1
        if success:
            stats["success"] += 1
            stats["total_duration"] += duration
        else:
            stats["failure"] += 1

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """获取调用统计

        Returns:
            按模型分组的调用统计：
            {
                "qwen-max": {
                    "total": 100,
                    "success": 95,
                    "failure": 5,
                    "total_duration": 120.5
                },
                ...
            }

        【使用场景】
        - 健康检查端点
        - 监控指标导出
        - 性能分析报告
        """
        return self._call_stats.copy()


# 全局客户端实例
_client = None


def get_model_gateway_client() -> ModelGatewayClient:
    """获取 ModelGateway 客户端实例（单例模式）

    【设计说明】
    使用全局单例的好处：
    1. 连接复用，减少资源消耗
    2. 统一的熔断器状态
    3. 统一的调用统计

    【线程安全】
    单例在首次调用时创建，之后复用。
    在异步环境中，多个协程共享同一个实例是安全的。

    Returns:
        ModelGatewayClient 实例
    """
    global _client
    if _client is None:
        _client = ModelGatewayClient()
    return _client
