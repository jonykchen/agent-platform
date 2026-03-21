"""Feature Flag 客户端 (M-04)

基于 Redis 的轻量级 Feature Flag 实现。
支持灰度策略：按用户、租户、百分比。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger()


@dataclass
class StrategyResult:
    """策略匹配结果"""
    matched: bool
    strategy_name: str
    reason: str = ""


class FeatureFlagClient:
    """Feature Flag 客户端

    支持的策略：
    - default: 全量开关
    - gradualRollout: 百分比灰度（一致性哈希）
    - specificTenant: 租户白名单
    - specificUsers: 用户白名单
    - flexibleRollout: 灵活灰度（支持 stickiness）

    使用方式:
        ff = FeatureFlagClient(redis)

        # 简单检查
        if await ff.is_enabled("rag_enabled"):
            ...

        # 带上下文检查（灰度）
        context = {"user_id": "user_001", "tenant_id": "tenant_001"}
        if await ff.is_enabled("new_feature", context):
            ...
    """

    def __init__(
        self,
        redis: Redis,
        config_cache_ttl: int = 60,
        key_prefix: str = "ff:",
    ):
        self.redis = redis
        self.config_cache_ttl = config_cache_ttl
        self.key_prefix = key_prefix

        # 本地缓存
        self._local_cache: dict[str, tuple[dict, float]] = {}
        self._cache_lock = asyncio.Lock()

    async def is_enabled(
        self,
        flag_name: str,
        context: dict | None = None,
        default: bool = False,
    ) -> bool:
        """判断 Feature Flag 是否启用

        Args:
            flag_name: 功能开关名称
            context: 上下文信息（用于灰度判断）
                - user_id: 用户 ID
                - tenant_id: 租户 ID
                - session_id: 会话 ID
            default: 默认值（flag 不存在时返回）

        Returns:
            是否启用
        """
        config = await self._get_flag_config(flag_name)

        if config is None:
            return default

        # 检查总开关
        if not config.get("enabled", False):
            return False

        strategies = config.get("strategies", [])
        if not strategies:
            return config["enabled"]

        # 检查每个策略（任一匹配即启用）
        for strategy in strategies:
            result = await self._match_strategy(strategy, context)
            if result.matched:
                logger.debug(
                    "Feature flag matched",
                    flag_name=flag_name,
                    strategy=result.strategy_name,
                    context=context,
                )
                return True

        return default

    async def get_variant(
        self,
        flag_name: str,
        context: dict | None = None,
    ) -> str | None:
        """获取 A/B 测试变体

        Returns:
            变体名称，如 "control" / "treatment"
        """
        config = await self._get_flag_config(flag_name)

        if config is None or not config.get("enabled", False):
            return None

        variants = config.get("variants", {})
        if not variants:
            return None

        # 根据权重选择变体
        stickiness = context.get("user_id", context.get("session_id", "default"))
        hash_val = int(hashlib.md5(f"{flag_name}:{stickiness}".encode()).hexdigest(), 16)
        bucket = hash_val % 100

        cumulative = 0
        for variant_name, variant_config in variants.items():
            weight = variant_config.get("weight", 50)
            cumulative += weight
            if bucket < cumulative:
                return variant_name

        return list(variants.keys())[0] if variants else None

    async def set_flag(
        self,
        flag_name: str,
        config: dict,
    ) -> None:
        """设置 Feature Flag 配置

        Args:
            flag_name: 功能开关名称
            config: 配置，如:
                {
                    "enabled": true,
                    "strategies": [
                        {"name": "gradualRollout", "parameters": {"rolloutPercentage": 80}}
                    ]
                }
        """
        key = f"{self.key_prefix}{flag_name}"
        await self.redis.set(key, json.dumps(config))

        # 清除本地缓存
        async with self._cache_lock:
            self._local_cache.pop(flag_name, None)

        logger.info("Feature flag set", flag_name=flag_name, config=config)

    async def delete_flag(self, flag_name: str) -> None:
        """删除 Feature Flag"""
        key = f"{self.key_prefix}{flag_name}"
        await self.redis.delete(key)

        async with self._cache_lock:
            self._local_cache.pop(flag_name, None)

        logger.info("Feature flag deleted", flag_name=flag_name)

    async def list_flags(self) -> list[str]:
        """列出所有 Feature Flag"""
        pattern = f"{self.key_prefix}*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key.decode() if isinstance(key, bytes) else key)

        return [k[len(self.key_prefix):] for k in keys]

    async def _get_flag_config(self, flag_name: str) -> dict | None:
        """获取 Flag 配置（带本地缓存）"""
        now = time.time()

        # 检查本地缓存
        async with self._cache_lock:
            if flag_name in self._local_cache:
                config, cache_time = self._local_cache[flag_name]
                if (now - cache_time) < self.config_cache_ttl:
                    return config

        # 从 Redis 读取
        key = f"{self.key_prefix}{flag_name}"
        raw = await self.redis.get(key)

        if raw is None:
            return None

        config = json.loads(raw if isinstance(raw, str) else raw.decode())

        # 更新本地缓存
        async with self._cache_lock:
            self._local_cache[flag_name] = (config, now)

        return config

    async def _match_strategy(self, strategy: dict, context: dict | None) -> StrategyResult:
        """匹配单个策略"""
        name = strategy.get("name", "")
        params = strategy.get("parameters", {})
        context = context or {}

        if name == "default":
            return StrategyResult(matched=True, strategy_name="default")

        elif name == "gradualRollout":
            return self._match_gradual_rollout(params, context)

        elif name == "specificTenant":
            return self._match_specific_tenant(params, context)

        elif name == "specificUsers":
            return self._match_specific_users(params, context)

        elif name == "flexibleRollout":
            return self._match_flexible_rollout(params, context)

        else:
            logger.warning("Unknown strategy", strategy_name=name)
            return StrategyResult(matched=False, strategy_name=name, reason="unknown strategy")

    def _match_gradual_rollout(self, params: dict, context: dict) -> StrategyResult:
        """百分比灰度策略"""
        percentage = params.get("rolloutPercentage", 100)
        stickiness_key = params.get("stickiness", "userId")

        if stickiness_key not in context:
            return StrategyResult(
                matched=percentage >= 100,
                strategy_name="gradualRollout",
                reason=f"missing stickiness key: {stickiness_key}",
            )

        value = context[stickiness_key]
        hash_val = int(hashlib.md5(f"gradualRollout:{value}".encode()).hexdigest(), 16)
        bucket = hash_val % 100

        matched = bucket < percentage
        return StrategyResult(
            matched=matched,
            strategy_name="gradualRollout",
            reason=f"bucket={bucket}, percentage={percentage}",
        )

    def _match_specific_tenant(self, params: dict, context: dict) -> StrategyResult:
        """租户白名单策略"""
        tenant_ids = params.get("tenantIds", [])
        tenant_id = context.get("tenant_id")

        matched = tenant_id in tenant_ids
        return StrategyResult(
            matched=matched,
            strategy_name="specificTenant",
            reason=f"tenant_id={tenant_id}, whitelist={tenant_ids}",
        )

    def _match_specific_users(self, params: dict, context: dict) -> StrategyResult:
        """用户白名单策略"""
        user_ids = params.get("userIds", [])
        user_id = context.get("user_id")

        matched = user_id in user_ids
        return StrategyResult(
            matched=matched,
            strategy_name="specificUsers",
            reason=f"user_id={user_id}, whitelist={user_ids}",
        )

    def _match_flexible_rollout(self, params: dict, context: dict) -> StrategyResult:
        """灵活灰度策略"""
        percentage = params.get("rolloutPercentage", 100)
        stickiness_key = params.get("stickiness", "userId")
        group_id = params.get("groupId", "default")

        if stickiness_key not in context:
            return StrategyResult(
                matched=percentage >= 100,
                strategy_name="flexibleRollout",
                reason=f"missing stickiness key: {stickiness_key}",
            )

        value = context[stickiness_key]
        hash_val = int(hashlib.md5(f"{group_id}:{value}".encode()).hexdigest(), 16)
        bucket = hash_val % 100

        matched = bucket < percentage
        return StrategyResult(
            matched=matched,
            strategy_name="flexibleRollout",
            reason=f"bucket={bucket}, percentage={percentage}, group={group_id}",
        )
