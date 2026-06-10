"""模型响应缓存（Redis）

对确定性较高的请求（temperature 较低）缓存模型响应，降低重复调用成本与延迟。
缓存键由 model + messages + temperature + max_tokens 哈希得到，命中即直接返回。

【设计说明】
- 仅缓存非流式、temperature <= 阈值的请求（高随机性请求缓存意义不大）
- 缓存失败不影响主流程（降级为直接调用）
- TTL 可配置，默认 10 分钟
"""

import hashlib
import json

import structlog

logger = structlog.get_logger()


class ResponseCache:
    """基于 Redis 的模型响应缓存"""

    def __init__(self, redis_url: str, ttl_seconds: int = 600, max_temperature: float = 0.3):
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._max_temperature = max_temperature
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            from redis.asyncio import Redis

            self._redis = Redis.from_url(self._redis_url)
        return self._redis

    @staticmethod
    def _build_key(model: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
        payload = json.dumps(
            {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
        return f"model_cache:{digest}"

    def is_cacheable(self, temperature: float, stream: bool) -> bool:
        """判断请求是否适合缓存：非流式且温度足够低（结果确定性高）"""
        return not stream and temperature <= self._max_temperature

    async def get(self, model: str, messages: list[dict], temperature: float, max_tokens: int) -> dict | None:
        """读取缓存，未命中或异常返回 None（降级）"""
        try:
            redis = await self._get_redis()
            key = self._build_key(model, messages, temperature, max_tokens)
            cached = await redis.get(key)
            if cached:
                logger.info("response_cache_hit", key=key)
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning("response_cache_get_failed", error=str(e))
            return None

    async def set(self, model: str, messages: list[dict], temperature: float, max_tokens: int, value: dict) -> None:
        """写入缓存，失败不影响主流程"""
        try:
            redis = await self._get_redis()
            key = self._build_key(model, messages, temperature, max_tokens)
            await redis.set(key, json.dumps(value, ensure_ascii=False), ex=self._ttl)
            logger.debug("response_cache_set", key=key, ttl=self._ttl)
        except Exception as e:
            logger.warning("response_cache_set_failed", error=str(e))


_response_cache: ResponseCache | None = None


def get_response_cache() -> ResponseCache:
    """获取全局响应缓存单例"""
    global _response_cache
    if _response_cache is None:
        from app.core.config import config

        _response_cache = ResponseCache(
            redis_url=config.redis_url,
            ttl_seconds=getattr(config, "cache_default_ttl", 600),
            max_temperature=getattr(config, "cache_max_temperature", 0.3),
        )
    return _response_cache
