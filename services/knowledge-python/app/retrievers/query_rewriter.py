"""Query 改写器

【核心概念】Query 改写
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query 改写是提升检索召回率的关键技术：
1. 用户查询可能表述模糊或包含错别字
2. LLM 可以理解查询意图并生成更精确的查询
3. 改写后的查询更易匹配相关文档

【改写策略】
┌─────────────────────────────────────────────────────────────────────────┐
│  原始查询                │  改写策略                │  效果           │
├─────────────────────────┼──────────────────────────┼─────────────────┤
│  "怎么退货"              │  扩展为完整表述           │  召回退货政策文档│
│  "订单问题"              │  细化为具体场景           │  精准匹配        │
│  "会员权益说明"           │  拆分为多个子查询         │  覆盖更多文档    │
│  "发票"                  │  补充上下文               │  避免歧义        │
└─────────────────────────────────────────────────────────────────────────┘

【缓存策略】
- 改写结果缓存 7 天（比 Embedding 缓存短，因为 LLM 可能更新）
- Key: `rewrite:SHA256(query)`
- 避免重复调用 LLM

【参考】
- Query 改写论文: https://arxiv.org/abs/2305.14283
- HyDE: https://arxiv.org/abs/2212.10496
"""

from __future__ import annotations

import hashlib
import json
import structlog
from typing import Any

import httpx
import redis.asyncio as redis

from app.core.config import config

logger = structlog.get_logger()

# 缓存配置
REWRITE_CACHE_PREFIX = "rewrite:"
REWRITE_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 天


class QueryRewriter:
    """Query 改写器

    功能：
    - 使用 LLM 改写查询以提升召回率
    - 缓存改写结果
    - 支持查询扩展（生成多个变体）

    使用示例：
        rewriter = QueryRewriter()

        # 改写查询
        result = await rewriter.rewrite("怎么退货")
        # result = {
        #     "rewritten_query": "退货流程和退货政策说明",
        #     "expanded_queries": ["退货流程", "退货条件", "退货时效"],
        # }
    """

    def __init__(
        self,
        redis_url: str | None = None,
        model_gateway_url: str | None = None,
        model: str | None = None,
    ):
        """初始化改写器

        Args:
            redis_url: Redis 连接 URL
            model_gateway_url: 模型网关 URL
            model: 使用的模型名称
        """
        self.redis_url = redis_url or config.redis_url
        self.model_gateway_url = model_gateway_url or getattr(
            config, "model_gateway_url", "http://localhost:8002"
        )
        self.model = model or getattr(config, "default_model", "qwen-plus")
        self._redis_client: redis.Redis | None = None
        self._http_client: httpx.AsyncClient | None = None

    async def _get_redis_client(self) -> redis.Redis:
        """获取 Redis 客户端"""
        if self._redis_client is None:
            self._redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis_client

    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.model_gateway_url,
                timeout=httpx.Timeout(30.0),
            )
        return self._http_client

    async def close(self) -> None:
        """关闭连接"""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _make_cache_key(self, query: str) -> str:
        """生成缓存 Key"""
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
        return f"{REWRITE_CACHE_PREFIX}{query_hash}"

    def _build_rewrite_prompt(self, query: str) -> str:
        """构建改写 Prompt

        改写目标：
        1. 补全省略信息
        2. 纠正错别字
        3. 扩展关键词

        Args:
            query: 原始查询

        Returns:
            改写 Prompt
        """
        return f"""你是一个查询改写助手，负责优化用户的搜索查询以提升检索效果。

原始查询：{query}

请执行以下改写任务：
1. 理解用户真实意图
2. 补全省略信息（如"退货"→"退货流程和退货政策"）
3. 纠正明显的错别字
4. 扩展相关关键词

请以 JSON 格式返回结果：
{{
    "rewritten_query": "改写后的查询（一个完整表述）",
    "expanded_queries": ["关键词1", "关键词2", "关键词3"],
    "intent": "查询意图分类（如：policy/instruction/definition）"
}}

只返回 JSON，不要有其他内容。"""

    async def rewrite(
        self,
        query: str,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """改写查询

        Args:
            query: 原始查询
            use_cache: 是否使用缓存

        Returns:
            改写结果：
            {
                "rewritten_query": "改写后的查询",
                "expanded_queries": ["关键词列表"],
                "intent": "查询意图",
            }
        """
        # 尝试从缓存获取
        if use_cache:
            cached = await self._get_cached(query)
            if cached:
                logger.debug(
                    "query_rewrite_cache_hit",
                    original=query[:50],
                )
                return cached

        # 调用 LLM 改写
        try:
            result = await self._call_llm(query)

            # 缓存结果
            if use_cache:
                await self._set_cached(query, result)

            logger.info(
                "query_rewritten",
                original=query[:50],
                rewritten=result.get("rewritten_query", "")[:50],
            )
            return result

        except Exception as e:
            logger.warning(
                "query_rewrite_failed",
                query=query[:50],
                error=str(e),
            )
            # 失败时返回原查询
            return {
                "rewritten_query": query,
                "expanded_queries": [query],
                "intent": "unknown",
            }

    async def _get_cached(self, query: str) -> dict[str, Any] | None:
        """获取缓存的改写结果"""
        try:
            client = await self._get_redis_client()
            key = self._make_cache_key(query)

            data = await client.get(key)
            if data:
                return json.loads(data)
            return None

        except redis.RedisError as e:
            logger.warning(
                "rewrite_cache_read_failed",
                error=str(e),
            )
            return None

    async def _set_cached(self, query: str, result: dict[str, Any]) -> bool:
        """缓存改写结果"""
        try:
            client = await self._get_redis_client()
            key = self._make_cache_key(query)

            await client.setex(
                key,
                REWRITE_CACHE_TTL_SECONDS,
                json.dumps(result, ensure_ascii=False),
            )
            return True

        except redis.RedisError as e:
            logger.warning(
                "rewrite_cache_write_failed",
                error=str(e),
            )
            return False

    async def _call_llm(self, query: str) -> dict[str, Any]:
        """调用 LLM 进行改写

        Args:
            query: 原始查询

        Returns:
            改写结果
        """
        client = await self._get_http_client()
        prompt = self._build_rewrite_prompt(query)

        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,  # 低温度保证稳定性
                "max_tokens": 500,
            },
        )
        response.raise_for_status()

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 解析 JSON 响应
        try:
            # 去除可能的 markdown 代码块标记
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content.strip())

            # 验证必要字段
            return {
                "rewritten_query": result.get("rewritten_query", query),
                "expanded_queries": result.get("expanded_queries", [query]),
                "intent": result.get("intent", "unknown"),
            }

        except json.JSONDecodeError:
            logger.warning(
                "rewrite_response_parse_failed",
                content=content[:100],
            )
            return {
                "rewritten_query": query,
                "expanded_queries": [query],
                "intent": "unknown",
            }

    async def batch_rewrite(
        self,
        queries: list[str],
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """批量改写查询

        Args:
            queries: 查询列表
            use_cache: 是否使用缓存

        Returns:
            改写结果列表
        """
        import asyncio

        results = await asyncio.gather(
            *[self.rewrite(q, use_cache=use_cache) for q in queries]
        )
        return list(results)


# 全局实例
_rewriter: QueryRewriter | None = None


def get_query_rewriter() -> QueryRewriter:
    """获取 Query 改写器实例"""
    global _rewriter
    if _rewriter is None:
        _rewriter = QueryRewriter()
    return _rewriter
