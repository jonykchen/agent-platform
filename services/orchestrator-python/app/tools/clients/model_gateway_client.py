"""ModelGateway HTTP 客户端

通过 HTTP 调用 ModelGateway 服务进行模型推理。
"""

import json
import structlog

import httpx

from app.core.config import config
from app.core.exceptions import ModelTimeoutError, AllProvidersDownError

logger = structlog.get_logger()


class ModelGatewayClient:
    """ModelGateway HTTP 客户端"""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or config.model_gateway_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=30.0,
                    write=10.0,
                    pool=5.0,
                ),
            )
        return self._client

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        **kwargs,
    ) -> dict:
        """对话补全

        Args:
            messages: 消息列表 [{"role": "user/assistant/system", "content": "..."}]
            model: 模型名称（可选，由网关路由）
            temperature: 温度参数
            max_tokens: 最大输出 token
            stream: 是否流式输出

        Returns:
            OpenAI 兼容格式的响应
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

        # 添加额外参数
        payload.update(kwargs)

        try:
            response = await client.post(
                "/v1/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException as e:
            logger.error("Model gateway timeout", error=str(e))
            raise ModelTimeoutError(timeout_s=30.0)

        except httpx.HTTPStatusError as e:
            logger.error(
                "Model gateway error",
                status_code=e.response.status_code,
                error=str(e),
            )

            if e.response.status_code == 503:
                raise AllProvidersDownError()

            # 尝试解析错误响应
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

    async def stream_chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        """流式对话补全

        Yields:
            SSE 格式的数据块
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

        except httpx.TimeoutException as e:
            logger.error("Model gateway stream timeout", error=str(e))
            raise ModelTimeoutError(timeout_s=30.0)

    async def list_models(self) -> list[dict]:
        """获取可用模型列表"""
        client = await self._get_client()

        try:
            response = await client.get("/v1/models")
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

        except Exception as e:
            logger.error("List models failed", error=str(e))
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

        Args:
            messages: 消息列表
            tools: 工具定义列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大输出 token

        Returns:
            包含 tool_calls 的响应
        """
        return await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice="auto",
        )


# 全局客户端实例
_client = None


def get_model_gateway_client() -> ModelGatewayClient:
    """获取 ModelGateway 客户端实例"""
    global _client
    if _client is None:
        _client = ModelGatewayClient()
    return _client