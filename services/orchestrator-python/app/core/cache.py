"""双层缓存模块 - Dual-Layer Cache

【核心概念】为什么需要双层缓存？
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

在高并发系统中，缓存是性能优化的核心手段：
1. 减少数据库查询，降低延迟
2. 降低后端服务压力，提高吞吐量
3. 提升用户体验，响应时间从秒级降到毫秒级

【问题背景】
- 单层 Redis 缓存延迟约 1-3ms
- 热点数据频繁访问，Redis 带宽成为瓶颈
- 多实例部署时，本地缓存可进一步降低延迟

【技术选型】缓存架构对比（量化数据）
┌────────────────────┬───────────────┬───────────────┬───────────────┐
│ 方案               │ 延迟 (P99)    │ QPS/实例      │ 数据一致性    │
├────────────────────┼───────────────┼───────────────┼───────────────┤
│ 单层 Redis         │ 1-3ms         │ ~50,000       │ ✅ 强一致     │
│ 单层本地缓存       │ <0.1ms        │ ~1,000,000    │ ❌ 各实例独立 │
│ ✓ 双层缓存 (L1+L2) │ L1: <0.1ms    │ L1: ~500,000  │ ⚠️ 最终一致  │
│                    │ L2: 1-3ms     │ L2: ~50,000   │              │
└────────────────────┴───────────────┴───────────────┴───────────────┘

【决策依据】选择双层缓存的原因：
1. 性能提升：L1 命中时延迟降低 10-30 倍
2. 成本优化：减少 Redis 带宽和 CPU 消耗
3. 灵活性：可根据数据热度选择缓存层

【设计权衡】双层缓存的核心挑战
┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 挑战               │ 问题                        │ 解决方案                    │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 数据一致性         │ L1 与 L2 数据可能不一致     │ 最终一致：L1 TTL < L2 TTL   │
│ 缓存回填           │ L1 miss 后如何填充           │ 自动回填：get 时填充 L1     │
│ 缓存失效           │ 数据更新时如何失效          │ L1 不主动失效，依赖 TTL     │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【缓存三防体系】行业最佳实践
┌──────────────┬─────────────────────────────┬─────────────────────────────────┐
│ 攻击类型     │ 危害                        │ 防御策略                        │
├──────────────┼─────────────────────────────┼─────────────────────────────────┤
│ 缓存穿透     │ 大量请求查询不存在的数据，   │ 空值缓存（使用 __EMPTY__ 标记） │
│ (Penetration)│ 直接穿透到数据库             │ TTL 60s（较短）                  │
├──────────────┼─────────────────────────────┼─────────────────────────────────┤
│ 缓存击穿     │ 热点 Key 过期瞬间，大量请求  │ 分布式锁（Redis SETNX）          │
│ (Breakdown)  │ 同时穿透到数据库             │ 锁超时 10s，等待者重试           │
├──────────────┼─────────────────────────────┼─────────────────────────────────┤
│ 缓存雪崩     │ 大量 Key 同时过期，数据库    │ TTL 随机抖动（±20%）             │
│ (Avalanche)  │ 瞬间负载飙升                 │ staggered expiration            │
└──────────────┴─────────────────────────────┴─────────────────────────────────┘

【参数推荐】生产环境配置（附依据）
- 空值缓存 TTL: 60s → 依据：足够短避免占用内存，足够长防止穿透
- 分布式锁超时: 10s → 依据：数据加载通常 <1s，10s 是安全裕量
- TTL 抖动比例: 20% → 依据：1000 个 Key 过期时间分散在 800-1200s

【风险与缓解】
┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 风险               │ 影响                        │ 缓解措施                    │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ L1 数据过期        │ 返回旧数据                  │ 设置合理的 TTL，关键数据主动失效│
│ Redis 连接失败     │ 缓存完全失效                │ 降级：直接查数据库，记录告警 │
│ 锁竞争激烈         │ 请求等待时间长              │ 增加 max_retries，监控等待者数量│
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【演进历史】
- v1.0: 单层 Redis 缓存，延迟约 2ms
- v2.0: 添加本地 L1 缓存，延迟降至 <0.1ms（L1 命中时）
- v2.1: 实现缓存三防体系（穿透、击穿、雪崩）
- v2.2: 添加热点 Key 逻辑过期（当前版本）

【最佳实践】参考
- Facebook TAO: https://www.usenix.org/conference/atc13/technical-sessions/presentation/bronson
- Netflix EVCache: https://github.com/Netflix/EVCache
- Redis 缓存设计: https://redis.io/docs/manual/client-side-caching/
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from typing import Any, Callable, TypeVar, Coroutine

import structlog
from cachetools import TTLCache
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import config
from app.core.metrics import CACHE_HITS, CACHE_MISSES, CACHE_SIZE

logger = structlog.get_logger()

F = TypeVar("F", bound=Callable[..., Any])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 常量定义：缓存三防体系的核心参数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 空值标记常量，用于区分"不存在"和"值为 None"
# 为什么需要标记？因为 None 也是合法的缓存值（如查询结果为空）
# 使用特殊标记可以让 get() 区分"未命中"和"命中空值"
EMPTY_VALUE_MARKER = "__EMPTY__"

# 默认空值缓存 TTL（秒）
# 为什么是 60s？
# - 太短（如 10s）：保护效果有限，穿透仍会频繁发生
# - 太长（如 300s）：占用内存，且数据可能已存在但仍返回"不存在"
# - 60s：平衡点，既能有效防止穿透，又不会长时间占用资源
DEFAULT_NULL_TTL = 60

# 分布式锁默认超时时间（秒）
# 为什么是 10s？
# - 正常数据加载通常 < 1s
# - 考虑网络抖动、数据库慢查询，留 10 倍安全裕量
# - 太长会导致锁长时间无法释放（需等待超时）
# - 太短会导致数据还未加载完成锁就过期，其他请求重复加载
DEFAULT_LOCK_TIMEOUT = 10

# TTL 抖动默认比例
# 为什么是 20%？
# - 假设 1000 个 Key 同时设置 TTL=300s
# - 抖动后过期时间分布在 240-360s
# - 有效避免同一时刻大量 Key 过期导致的雪崩
DEFAULT_JITTER_RATIO = 0.2

# 热点 Key 判断阈值：每秒访问次数
# 超过此阈值的 Key 应使用 get_hot_key() 方法（逻辑过期策略）
HOT_KEY_THRESHOLD_QPS = 100


def calculate_ttl_with_jitter(base_ttl: int, jitter_ratio: float = DEFAULT_JITTER_RATIO) -> int:
    """计算带随机抖动的 TTL（雪崩防御核心实现）

    【问题背景】雪崩效应
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    假设系统启动时批量缓存了 10000 个配置项，TTL 都是 3600 秒：
    - 1 小时后，10000 个 Key 同时过期
    - 瞬间 10000 个请求穿透到数据库
    - 数据库负载飙升，响应变慢，甚至崩溃
    - 缓存无法回填，形成恶性循环

    【解决方案】TTL 随机抖动
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    通过在基础 TTL 上增加随机偏移，让 Key 过期时间分散：

    - 原 TTL: 3600s → 实际 TTL: 2880-4320s（±20%）
    - 10000 个 Key 过期时间分散在 48 分钟区间内
    - 每秒平均只有 ~3 个 Key 过期，数据库压力平滑

    【数学原理】
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    actual_ttl = base_ttl * (1 + random(-jitter_ratio, +jitter_ratio))
               = base_ttl + random(-base_ttl * ratio, +base_ttl * ratio)

    Args:
        base_ttl: 基础过期时间（秒），必须为正数
        jitter_ratio: 抖动比例，默认 0.2（±20%）
            - 推荐值：0.1-0.3（10%-30%）
            - 过小：分散效果不明显
            - 过大：缓存命中率下降（部分 Key 过早过期）

    Returns:
        带抖动的实际 TTL（秒），最小为 1

    Example:
        >>> # 批量缓存时自动分散过期时间
        >>> for user_id in user_ids:
        ...     ttl = calculate_ttl_with_jitter(3600, 0.2)
        ...     await cache.set(f"user:{user_id}", data, ttl)
        # 实际 TTL 在 2880-4320 之间随机分布

    【为什么不在 set() 时直接 random？】
    为了代码可测试性和可调试性，将抖动逻辑抽离为独立函数：
    - 可以在测试中 mock 此函数
    - 可以单独验证抖动算法的正确性
    - 日志中可以区分"原始 TTL"和"实际 TTL"
    """
    if base_ttl <= 0:
        # TTL <= 0 表示永不过期或不缓存，直接返回
        return base_ttl

    # 计算抖动范围：base_ttl * (1 ± jitter_ratio)
    # 例如：base_ttl=100, ratio=0.2 → 抖动范围 ±20，即 80-120
    jitter = base_ttl * jitter_ratio
    actual_ttl = int(base_ttl + random.uniform(-jitter, jitter))

    # 确保 TTL 为正数，至少 1 秒
    # random.uniform 可能产生负数导致 actual_ttl <= 0
    return max(1, actual_ttl)


class DualLayerCache:
    """双层缓存实现

    【架构设计】L1 + L2 两层缓存
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │   Client    │────▶│  L1 Cache   │────▶│  L2 Redis   │
    │  (Request)  │     │  (Local)    │     │  (Remote)   │
    └─────────────┘     └─────────────┘     └─────────────┘
           │                   │                   │
           │         <0.1ms    │         1-3ms     │
           │        (L1 hit)   │       (L2 hit)    │
           │                   │                   │
           └───────────────────┴───────────────────┘
                              │
                              ▼
                       ┌─────────────┐
                       │  Database   │
                       │  (Source)   │
                       └─────────────┘
                            ~50ms

    【一致性策略】最终一致
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    L1 和 L2 可能存在短暂不一致：
    - 场景：实例 A 更新了缓存，实例 B 的 L1 仍是旧数据
    - 影响：不同实例短暂看到不同数据（通常 < TTL）
    - 接受原因：
      1. 大多数场景可接受短暂不一致（如配置、用户信息）
      2. 强一致需要广播失效，增加复杂度和延迟
      3. TTL 过期后自动恢复一致

    【L1 缓存选型】为什么用 cachetools.TTLCache？
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    对比其他方案：

    | 方案            | 优点                    | 缺点                      |
    |-----------------|------------------------|--------------------------|
    | Python dict     | 最快                    | 无过期、无容量限制、内存泄漏 |
    | functools.lru   | 标准库                  | 无 TTL 支持               |
    | cachetools.TTL  | ✓ TTL + 容量限制 + 线程安全 | 纯内存，不持久化          |
    | Redis 本地缓存   | 功能最全                | 需要额外依赖、配置复杂     |

    选择 cachetools.TTLCache 的原因：
    1. 轻量：单文件实现，无外部依赖
    2. 功能完备：支持 TTL + maxsize + 线程安全
    3. 成熟稳定：广泛使用，久经考验

    【三防体系】穿透、击穿、雪崩
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    1. 穿透防御（Penetration）：cache_null_result()
       - 问题：频繁查询不存在的数据，绕过缓存直达数据库
       - 防御：缓存空值（__EMPTY__），TTL 60s

    2. 击穿防御（Breakdown）：get_with_lock()
       - 问题：热点 Key 过期瞬间，大量请求同时穿透
       - 防御：分布式锁（SETNX），单请求加载，其他等待

    3. 雪崩防御（Avalanche）：calculate_ttl_with_jitter()
       - 问题：大量 Key 同时过期，数据库瞬间高压
       - 防御：TTL 随机抖动 ±20%，分散过期时间

    【使用场景指南】
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    | 方法              | 适用场景                              | QPS 阈值  |
    |-------------------|--------------------------------------|----------|
    | get() / set()     | 普通数据，低并发                      | < 100    |
    | get_or_set()      | 普通数据，中等并发，无穿透风险         | < 1000   |
    | get_with_lock()   | 热点数据，高并发，需防击穿             | < 10000  |
    | get_hot_key()     | 超热点数据，极高并发，永不阻塞         | > 10000  |
    """

    def __init__(
        self,
        redis: Redis,
        name: str = "default",
        local_maxsize: int | None = None,
        ttl: int | None = None,
    ):
        """初始化双层缓存

        Args:
            redis: Redis 客户端实例（异步）
                - 必须是 redis.asyncio.Redis 实例
                - 连接池应在外部配置好

            name: 缓存名称，用于键前缀隔离
                - 不同 name 的缓存互不干扰
                - Redis 键格式：cache:{name}:{key}
                - 示例："rag", "user_profile", "tool_schema"

            local_maxsize: 本地缓存最大容量（条目数）
                - 默认值：config.cache_local_maxsize（通常 1000）
                - LRU 淘汰：超过容量时淘汰最久未使用
                - 内存估算：每条目约 1KB，1000 条约 1MB

            ttl: 默认过期时间（秒）
                - 默认值：config.cache_default_ttl（通常 300s）
                - 可在 set() 时覆盖
        """
        self._redis = redis
        self._name = name
        self._local_maxsize = local_maxsize or config.cache_local_maxsize
        self._ttl = ttl or config.cache_default_ttl

        # L1 本地缓存：使用 cachetools.TTLCache
        # - maxsize: 容量限制，LRU 淘汰
        # - ttl: 过期时间，自动清理
        self._local_cache = TTLCache(maxsize=self._local_maxsize, ttl=self._ttl)

        # 命中率统计：用于监控和调优
        # 定期通过 get_stats() 输出，帮助判断缓存效果
        self._hit_count = 0
        self._miss_count = 0

    def _make_key(self, key: str) -> str:
        """生成 Redis 键

        【键命名规范】
        格式：cache:{cache_name}:{original_key}
        示例：cache:rag:abc123def456

        【为什么加前缀？】
        1. 避免键冲突：不同缓存实例可能有相同的 key
        2. 便于管理：可以按前缀批量删除/查询
        3. 安全隔离：不同业务数据不会互相覆盖
        """
        return f"cache:{self._name}:{key}"

    def _make_lock_key(self, key: str) -> str:
        """生成分布式锁键

        【锁命名规范】
        格式：lock:cache:{cache_name}:{original_key}
        示例：lock:cache:rag:abc123def456

        【为什么锁键和缓存键分开？】
        1. 避免误删：删除锁不应影响缓存数据
        2. 便于监控：可以单独查看锁的状态
        3. 不同 TTL：锁通常 10s，缓存可能 300s
        """
        return f"lock:cache:{self._name}:{key}"

    @staticmethod
    def _hash_key(data: str | dict) -> str:
        """生成哈希键（用于复杂查询的缓存键）

        【问题背景】
        有些查询条件很复杂：
        - JSON 对象：{"user_id": "123", "filters": {...}}
        - 长字符串：SQL 语句、搜索词

        直接作为 Redis 键会：
        - 键过长（Redis 键最大 512MB，但不推荐）
        - 包含特殊字符，需要转义
        - 相同语义但格式不同的键被视为不同（如空格、字段顺序）

        【解决方案】MD5 哈希
        - 固定长度：16 字符（MD5 前 16 位）
        - 确定性：相同输入永远产生相同输出
        - 低冲突：MD5 冲突概率极低（2^-64）

        Args:
            data: 原始数据（字符串或字典）
                - 字典会按 key 排序后 JSON 序列化，确保相同内容生成相同键

        Returns:
            16 位哈希字符串

        Example:
            >>> DualLayerCache._hash_key({"a": 1, "b": 2})
            'a8f97b2c4d6e1f3a'  # 相同内容永远相同结果
            >>> DualLayerCache._hash_key({"b": 2, "a": 1})  # 字段顺序不同
            'a8f97b2c4d6e1f3a'  # 结果相同（因为 sort_keys=True）
        """
        if isinstance(data, dict):
            # 字典序列化时按 key 排序，确保相同内容生成相同哈希
            # sort_keys=True 是关键！否则 {"a":1,"b":2} 和 {"b":2,"a":1} 会产生不同哈希
            data = json.dumps(data, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()[:16]

    async def get(self, key: str) -> Any | None:
        """获取缓存值（双层查询 + 自动回填）

        【查询流程】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        1. 查 L1（本地缓存）
           ├─ 命中 → 返回值，延迟 <0.1ms
           └─ 未命中 ↓

        2. 查 L2（Redis）
           ├─ 命中 → 回填 L1，返回值，延迟 1-3ms
           └─ 未命中 → 返回 None

        【自动回填 L1】
        当 L2 命中时，自动将值写入 L1：
        - 后续请求直接从 L1 获取
        - 减少对 Redis 的访问
        - 注意：L1 的 TTL 与 L2 可能不同

        【返回值语义】
        - 返回非 None 值：缓存命中，正常数据
        - 返回 EMPTY_VALUE_MARKER：空值缓存命中（数据不存在）
        - 返回 None：缓存未命中

        Args:
            key: 缓存键

        Returns:
            缓存值、EMPTY_VALUE_MARKER（空值缓存）或 None（未命中）
        """
        full_key = self._make_key(key)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # L1 查询：本地内存，延迟 <0.1ms
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if key in self._local_cache:
            self._hit_count += 1
            CACHE_HITS.labels(cache_name=self._name).inc()

            # L1 命中日志：用于调优和问题排查
            # - 高频 L1 命中说明缓存有效
            # - 如果 L1 命中率低，考虑增大 local_maxsize
            logger.debug(
                "Cache L1 hit",
                cache=self._name,
                key=key,
                local_size=len(self._local_cache),
            )
            return self._local_cache[key]

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # L2 查询：Redis，延迟 1-3ms
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        try:
            data = await self._redis.get(full_key)
            if data is not None:
                # 反序列化 JSON
                value = json.loads(data)

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # 回填 L1：下次请求直接从本地获取
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                self._local_cache[key] = value
                self._hit_count += 1
                CACHE_HITS.labels(cache_name=self._name).inc()

                logger.debug(
                    "Cache L2 hit, backfilled to L1",
                    cache=self._name,
                    key=key,
                )
                return value

        except RedisError as e:
            # Redis 异常不应阻断业务，记录告警后继续
            # 此时相当于缓存降级，直接返回 None
            logger.warning(
                "Redis cache read failed, cache degraded",
                error=str(e),
                cache=self._name,
                key=key,
            )

        # 缓存未命中
        self._miss_count += 1
        CACHE_MISSES.labels(cache_name=self._name).inc()
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        apply_jitter: bool = True,
    ) -> None:
        """设置缓存值（双写 L1 + L2）

        【写入流程】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        1. 写 L1（本地缓存）- 应用小抖动（±5%），轻微分散过期
        2. 写 L2（Redis）- 应用大抖动（±20%），防雪崩

        【TTL 抖动策略】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        L1 小抖动（±5%）：
        - L1 虽然实例间独立，但同一实例内可能大量 Key 同时过期
        - 小抖动可分散实例内的过期峰值

        L2 大抖动（±20%）：
        - 防止多实例同时向 Redis 发起大量回源请求（缓存雪崩）

        Args:
            key: 缓存键
            value: 缓存值（会被 JSON 序列化）
            ttl: 过期时间（秒），为 None 时使用默认值
            apply_jitter: 是否应用 TTL 抖动（雪崩防御），默认 True
        """
        import random

        full_key = self._make_key(key)
        base_ttl = ttl or self._ttl

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 应用 TTL 抖动（雪崩防御）
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if apply_jitter:
            # L1 小抖动（±5%）：分散实例内过期峰值
            l1_ttl = int(base_ttl * random.uniform(0.95, 1.05))
            # L2 大抖动（±20%）：防止多实例同时回源
            l2_ttl = int(base_ttl * random.uniform(0.8, 1.2))
        else:
            l1_ttl = base_ttl
            l2_ttl = base_ttl

        # 设置 L1（带小抖动）
        self._local_cache[key] = value
        self._local_cache_ttl[key] = l1_ttl

        # 设置 L2
        try:
            await self._redis.setex(
                full_key,
                l2_ttl,
                json.dumps(value, ensure_ascii=False),
            )
            logger.debug(
                "Cache set",
                cache=self._name,
                key=key,
                l1_ttl=l1_ttl,
                l2_ttl=l2_ttl,
                jitter_applied=apply_jitter,
            )
        except RedisError as e:
            # L2 写入失败不应阻断业务，L1 仍然有效
            logger.warning(
                "Redis cache write failed, L1 only",
                error=str(e),
                cache=self._name,
                key=key,
            )

        # 更新指标
        CACHE_SIZE.labels(cache_name=self._name).set(len(self._local_cache))

    async def cache_null_result(self, key: str, ttl: int = DEFAULT_NULL_TTL) -> None:
        """缓存空值结果（穿透防御）

        【问题：缓存穿透】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        攻击者持续请求不存在的数据：
        - 请求 id=-1, id=-2, id=-3...
        - 缓存未命中，每次都查询数据库
        - 数据库压力剧增，甚至崩溃

        【解决方案：空值缓存】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        当数据不存在时，缓存一个特殊标记：
        - 标记：__EMPTY__（区分于 None）
        - TTL：60s（较短，避免长期占用）

        后续请求：
        - 缓存命中 __EMPTY__ → 直接返回 None，不查数据库
        - 60s 后过期 → 再次查询，如果数据已存在则缓存

        【为什么用特殊标记而不是 None？】
        None 可能是合法的缓存值：
        - 查询结果确实是 None（如用户设置某字段为空）
        - 需要区分"缓存了 None 值"和"缓存未命中"

        Args:
            key: 缓存键
            ttl: 空值缓存 TTL（秒），默认 60 秒
        """
        await self.set(key, EMPTY_VALUE_MARKER, ttl=ttl, apply_jitter=True)
        logger.info(
            "Cached null result (penetration defense)",
            cache=self._name,
            key=key,
            ttl=ttl,
        )

    async def delete(self, key: str) -> None:
        """删除缓存值（双删 L1 + L2）

        【一致性考虑】
        删除操作会同时清除 L1 和 L2：
        - 保证下次查询能获取最新数据
        - 但其他实例的 L1 可能仍有旧数据
        - 依赖 L1 TTL 自动过期

        【什么时候需要主动删除？】
        1. 数据更新后需要立即生效
        2. 发现缓存数据错误
        3. 用户主动清除（如"刷新"功能）
        """
        full_key = self._make_key(key)

        # 删除 L1
        if key in self._local_cache:
            del self._local_cache[key]

        # 删除 L2
        try:
            await self._redis.delete(full_key)
        except RedisError as e:
            logger.warning(
                "Redis cache delete failed",
                error=str(e),
                cache=self._name,
                key=key,
            )

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any] | Callable[[], Coroutine[Any, None, Any]],
        ttl: int | None = None,
    ) -> Any:
        """获取或计算缓存值（简单缓存模式）

        【适用场景】
        - 低并发场景（QPS < 1000）
        - 数据加载快（< 100ms）
        - 无热点 Key 风险

        【不适用场景】
        - 高并发热点 Key（用 get_with_lock）
        - 数据加载慢（用 get_hot_key）

        【工作流程】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        1. 尝试获取缓存
           ├─ 命中 → 返回值
           └─ 未命中 ↓

        2. 调用 factory() 计算新值
           ├─ 返回 None → 缓存空值，返回 None
           └─ 返回值 → 缓存并返回

        Args:
            key: 缓存键
            factory: 值生成函数（同步或异步）
            ttl: 缓存 TTL

        Returns:
            缓存值或计算结果
        """
        value = await self.get(key)
        if value is not None:
            # 空值缓存命中，返回 None 表示数据不存在
            if value == EMPTY_VALUE_MARKER:
                return None
            return value

        # 计算新值
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        # 空值缓存（穿透防御）
        if value is None:
            await self.cache_null_result(key)
            return None

        await self.set(key, value, ttl)
        return value

    async def get_with_lock(
        self,
        key: str,
        loader: Callable[[], Any] | Callable[[], Coroutine[Any, None, Any]],
        ttl: int | None = None,
        lock_timeout: int = DEFAULT_LOCK_TIMEOUT,
        retry_interval: float = 0.1,
        max_retries: int = 100,
    ) -> Any:
        """使用分布式锁获取缓存值（击穿防御）

        【问题：缓存击穿】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        热点 Key 过期瞬间：
        T=0:     缓存过期
        T=0.001: 请求 1 发现缓存不存在，开始加载数据
        T=0.002: 请求 2 发现缓存不存在，开始加载数据
        T=0.003: 请求 3 发现缓存不存在，开始加载数据...
        ...
        T=0.100: 100 个请求同时查询数据库！

        【解决方案：分布式锁】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        使用 Redis SETNX 实现互斥锁：
        - 请求 1 获取锁成功 → 加载数据 → 更新缓存 → 释放锁
        - 请求 2 获取锁失败 → 等待并重试 → 发现缓存已填充 → 直接返回
        - 只有 1 个请求穿透到数据库

        【时序图】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        Request 1          Cache            Request 2
           │                 │                 │
           │──GET───────────▶│                 │
           │◀─miss───────────│                 │
           │                 │                 │
           │──SETNX(lock)───▶│                 │
           │◀─OK─────────────│                 │
           │                 │                 │
           │──load data─────▶│                 │──GET───▶
           │                 │                 │◀─miss───
           │                 │                 │
           │                 │                 │──SETNX(lock)───▶
           │                 │                 │◀─FAIL (lock exists)
           │                 │                 │
           │──SET(value)────▶│                 │──sleep & retry──
           │                 │                 │
           │──DEL(lock)─────▶│                 │
           │                 │                 │──GET───▶
           │                 │                 │◀─hit───
           │                 │                 │

        【竞态条件分析】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        可能的竞态：
        1. 获取锁后，进程崩溃 → 锁不会释放
           解决：锁有超时时间（lock_timeout），自动过期

        2. 加载数据时间 > 锁超时 → 其他请求获取锁，重复加载
           解决：设置合理的 lock_timeout，监控加载时间

        3. 锁竞争激烈 → 大量请求等待
           解决：监控等待者数量，超过阈值告警

        Args:
            key: 缓存键
            loader: 数据加载函数（同步或异步）
            ttl: 缓存 TTL
            lock_timeout: 锁超时时间（秒），默认 10 秒
            retry_interval: 获取锁失败时的重试间隔（秒），默认 0.1 秒
            max_retries: 最大重试次数，默认 100 次
                - 最大等待时间 = max_retries * retry_interval = 10 秒
                - 超过后降级直接加载

        Returns:
            缓存值或加载结果
        """
        # 先尝试获取缓存
        value = await self.get(key)
        if value is not None:
            if value == EMPTY_VALUE_MARKER:
                return None
            return value

        lock_key = self._make_lock_key(key)
        lock_acquired = False

        try:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 尝试获取分布式锁（Redis SETNX）
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            lock_acquired = await self._redis.set(
                lock_key,
                "1",
                nx=True,  # SETNX: 仅当 key 不存在时设置
                ex=lock_timeout,  # 过期时间：防止死锁
            )

            if lock_acquired:
                logger.debug(
                    "Cache lock acquired",
                    cache=self._name,
                    key=key,
                    lock_timeout=lock_timeout,
                )

                # 获取锁成功，加载数据
                if asyncio.iscoroutinefunction(loader):
                    value = await loader()
                else:
                    value = loader()

                # 处理空值
                if value is None:
                    await self.cache_null_result(key)
                    return None

                # 设置缓存
                await self.set(key, value, ttl)
                return value

            else:
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # 获取锁失败，等待并重试
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                logger.debug(
                    "Cache lock contention, waiting for other request to fill cache",
                    cache=self._name,
                    key=key,
                )

                for attempt in range(max_retries):
                    await asyncio.sleep(retry_interval)

                    # 检查缓存是否已被其他请求填充
                    value = await self.get(key)
                    if value is not None:
                        if value == EMPTY_VALUE_MARKER:
                            return None
                        logger.debug(
                            "Cache filled by another request",
                            cache=self._name,
                            key=key,
                            attempt=attempt + 1,
                            wait_time_ms=int((attempt + 1) * retry_interval * 1000),
                        )
                        return value

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # 超过最大重试次数，降级处理：直接加载数据
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # 这是一种保护措施，避免请求无限等待
                logger.warning(
                    "Cache lock wait timeout, loading directly (degraded mode)",
                    cache=self._name,
                    key=key,
                    max_retries=max_retries,
                    total_wait_time_ms=int(max_retries * retry_interval * 1000),
                )

                if asyncio.iscoroutinefunction(loader):
                    value = await loader()
                else:
                    value = loader()

                if value is None:
                    await self.cache_null_result(key)
                    return None

                await self.set(key, value, ttl)
                return value

        except RedisError as e:
            logger.error(
                "Redis lock operation failed, falling back to direct load",
                error=str(e),
                cache=self._name,
                key=key,
            )
            # Redis 异常时降级：直接加载数据
            if asyncio.iscoroutinefunction(loader):
                value = await loader()
            else:
                value = loader()

            if value is not None and value != EMPTY_VALUE_MARKER:
                await self.set(key, value, ttl)
            return value

        finally:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 释放锁（仅在成功获取锁时）
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            if lock_acquired:
                try:
                    await self._redis.delete(lock_key)
                    logger.debug(
                        "Cache lock released",
                        cache=self._name,
                        key=key,
                    )
                except RedisError as e:
                    # 锁释放失败不影响数据，只是会有短暂残留
                    # 依赖锁的超时机制自动清理
                    logger.warning(
                        "Failed to release cache lock, will expire automatically",
                        error=str(e),
                        cache=self._name,
                        key=key,
                        lock_timeout=lock_timeout,
                    )

    async def get_hot_key(
        self,
        key: str,
        loader: Callable[[], Any] | Callable[[], Coroutine[Any, None, Any]],
        ttl: int | None = None,
        refresh_ahead_ratio: float = 0.8,
    ) -> Any:
        """热点 Key 逻辑过期（永不过期策略）

        【问题：热点 Key 过期】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        超热点 Key（QPS > 10000）即使有分布式锁也会有大量等待：
        - 锁持有时间 100ms
        - 等待者 1000 个，每个等 0.1ms
        - 总等待时间累积，用户体验下降

        【解决方案：逻辑过期】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        核心思想：物理不过期，逻辑判断过期

        缓存数据结构：
        {
            "value": 实际数据,
            "expire_at": 逻辑过期时间戳,
            "created_at": 创建时间戳
        }

        行为：
        1. 未过期（当前时间 < expire_at）：
           - 直接返回数据
           - 接近过期时，异步后台刷新

        2. 已过期（当前时间 >= expire_at）：
           - 返回旧数据（可能过时，但不会阻塞）
           - 触发后台刷新

        3. 缓存不存在：
           - 加载数据并设置

        【逻辑过期 vs 物理过期】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        | 特性         | 物理过期 (get_with_lock) | 逻辑过期 (get_hot_key) |
        |--------------|-------------------------|------------------------|
        | 过期时行为   | 阻塞等待新数据           | 返回旧数据，后台刷新    |
        | 数据新鲜度   | 总是最新的               | 可能短暂过时           |
        | 请求延迟     | 可能高（等待锁）         | 恒定低（<1ms）         |
        | 适用场景     | 热点 Key (QPS < 10000)   | 超热点 Key (QPS > 10000)|

        【提前刷新（Refresh Ahead）】
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        当数据接近过期时（剩余时间 < TTL * (1 - refresh_ahead_ratio)），
        提前触发后台刷新，确保用户几乎总是获取到新鲜数据。

        示例：
        - TTL = 300s
        - refresh_ahead_ratio = 0.8
        - 过期前 20% 时间（60s）开始刷新
        - 即在 T=240s 时开始后台刷新

        Args:
            key: 缓存键
            loader: 数据加载函数（同步或异步）
            ttl: 逻辑过期时间（秒）
            refresh_ahead_ratio: 提前刷新比例，默认 0.8
                - 0.8 表示过期前 20% 时间开始刷新
                - 推荐值：0.7-0.9

        Returns:
            缓存值或加载结果
        """
        full_key = self._make_key(key)
        base_ttl = ttl or self._ttl

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 尝试获取缓存
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        try:
            data = await self._redis.get(full_key)
            if data is not None:
                cached_data = json.loads(data)

                # 检查是否为空值缓存
                if cached_data.get("value") == EMPTY_VALUE_MARKER:
                    return None

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # 检查逻辑过期时间
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                expire_at = cached_data.get("expire_at", 0)
                current_time = time.time()

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # 未过期：直接返回，检查是否需要提前刷新
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                if current_time < expire_at:
                    # 回填 L1
                    self._local_cache[key] = cached_data["value"]
                    self._hit_count += 1
                    CACHE_HITS.labels(cache_name=self._name).inc()

                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # 接近过期时，触发后台异步刷新（Refresh Ahead）
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    refresh_threshold = expire_at - base_ttl * (1 - refresh_ahead_ratio)
                    if current_time >= refresh_threshold:
                        remaining_ttl = int(expire_at - current_time)
                        logger.debug(
                            "Hot key refresh triggered (refresh ahead)",
                            cache=self._name,
                            key=key,
                            remaining_ttl=remaining_ttl,
                            refresh_threshold_ratio=1 - refresh_ahead_ratio,
                        )
                        # 创建后台刷新任务（不等待完成）
                        # 使用 create_task 而不是 await，实现异步后台执行
                        asyncio.create_task(
                            self._refresh_hot_key_background(key, loader, base_ttl)
                        )

                    return cached_data["value"]

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # 已过期：返回旧数据，触发后台刷新
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                logger.debug(
                    "Hot key logically expired, returning stale data and refreshing in background",
                    cache=self._name,
                    key=key,
                    expired_seconds=int(current_time - expire_at),
                )
                asyncio.create_task(
                    self._refresh_hot_key_background(key, loader, base_ttl)
                )

                # 返回旧数据（可能为 None）
                return cached_data.get("value")

        except RedisError as e:
            logger.warning(
                "Redis hot key read failed",
                error=str(e),
                cache=self._name,
                key=key,
            )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 缓存未命中，加载数据并设置
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if asyncio.iscoroutinefunction(loader):
            value = await loader()
        else:
            value = loader()

        if value is None:
            await self.cache_null_result(key)
            return None

        await self._set_hot_key_value(key, value, base_ttl)
        return value

    async def _refresh_hot_key_background(
        self,
        key: str,
        loader: Callable[[], Any] | Callable[[], Coroutine[Any, None, Any]],
        ttl: int,
    ) -> None:
        """后台刷新热点 Key

        【异步后台任务】
        使用 asyncio.create_task() 创建后台任务：
        - 不阻塞当前请求
        - 即使任务失败也不影响返回值
        - 异常会被捕获并记录日志

        【幂等性】
        多个刷新任务可能同时运行：
        - 后完成的会覆盖先完成的
        - 对于大多数场景这是可接受的
        - 如需严格控制，可添加刷新锁
        """
        try:
            if asyncio.iscoroutinefunction(loader):
                value = await loader()
            else:
                value = loader()

            if value is not None:
                await self._set_hot_key_value(key, value, ttl)
                logger.info(
                    "Hot key refreshed in background",
                    cache=self._name,
                    key=key,
                    new_ttl=ttl,
                )

        except Exception as e:
            # 刷新失败不影响用户，他们仍能获取旧数据
            logger.error(
                "Hot key background refresh failed, stale data still available",
                error=str(e),
                cache=self._name,
                key=key,
            )

    async def _set_hot_key_value(self, key: str, value: Any, ttl: int) -> None:
        """设置热点 Key 的逻辑过期数据

        【数据结构】
        {
            "value": 实际数据,
            "expire_at": 过期时间戳（逻辑过期）,
            "created_at": 创建时间戳
        }

        【物理过期作为兜底】
        虽然使用逻辑过期，但 Redis 层仍设置物理过期时间：
        - 防止数据长期占用内存
        - 作为清理机制，避免"僵尸"数据
        - 物理过期时间 = 逻辑过期时间 × 2
        """
        full_key = self._make_key(key)

        # 构建带逻辑过期时间的数据结构
        hot_key_data = {
            "value": value,
            "expire_at": time.time() + ttl,  # 逻辑过期时间
            "created_at": time.time(),
        }

        # 设置 L1
        self._local_cache[key] = value

        # 设置 L2（物理过期作为兜底清理机制）
        try:
            # 物理过期时间设为逻辑过期的 2 倍，作为兜底清理机制
            # 即使后台刷新失败，数据也会在 2×TTL 后被 Redis 清理
            physical_ttl = int(ttl * 2)
            await self._redis.setex(
                full_key,
                physical_ttl,
                json.dumps(hot_key_data, ensure_ascii=False),
            )
        except RedisError as e:
            logger.warning(
                "Redis hot key write failed",
                error=str(e),
                cache=self._name,
                key=key,
            )

        CACHE_SIZE.labels(cache_name=self._name).set(len(self._local_cache))

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计

        【监控指标】
        - hit_rate: 命中率，目标 > 80%
        - local_size: L1 容量使用率
        - hit_count / miss_count: 绝对数量，用于趋势分析

        【告警阈值】
        - 命中率 < 50%：缓存策略需优化
        - local_size 接近 local_maxsize：考虑扩容
        """
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0

        return {
            "name": self._name,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": round(hit_rate, 4),
            "local_size": len(self._local_cache),
            "local_maxsize": self._local_maxsize,
            "ttl": self._ttl,
        }

    def clear(self) -> None:
        """清空本地缓存

        【使用场景】
        - 测试清理
        - 发现数据错误需要强制刷新
        - 内存压力大时释放空间
        """
        self._local_cache.clear()
        CACHE_SIZE.labels(cache_name=self._name).set(0)


class CacheManager:
    """缓存管理器

    【职责】
    管理多个命名缓存实例：
    - 按需创建，惰性初始化
    - 统一配置管理
    - 统计信息聚合

    【命名缓存】
    不同业务使用不同的缓存实例，互不干扰：
    - "rag": RAG 查询结果
    - "tool_schema": 工具 Schema
    - "model_list": 模型列表

    【生命周期】
    - 应用启动时调用 init_cache_manager(redis)
    - 各模块通过 get_cache_manager() 获取实例
    - 按需调用 get_cache("name") 获取具体缓存
    """

    def __init__(self, redis: Redis):
        """初始化缓存管理器

        Args:
            redis: Redis 客户端实例（异步）
        """
        self._redis = redis
        self._caches: dict[str, DualLayerCache] = {}

    def get_cache(
        self,
        name: str,
        ttl: int | None = None,
        local_maxsize: int | None = None,
    ) -> DualLayerCache:
        """获取或创建命名缓存

        【惰性初始化】
        缓存实例在首次使用时创建：
        - 节省内存（不需要的缓存不创建）
        - 配置灵活（不同缓存可不同参数）

        Args:
            name: 缓存名称
            ttl: 默认过期时间
            local_maxsize: 本地缓存最大容量

        Returns:
            DualLayerCache 实例
        """
        if name not in self._caches:
            self._caches[name] = DualLayerCache(
                redis=self._redis,
                name=name,
                ttl=ttl,
                local_maxsize=local_maxsize,
            )
        return self._caches[name]

    def get_rag_cache(self) -> DualLayerCache:
        """获取 RAG 结果缓存

        【配置说明】
        - TTL: 较长（通常 300s+），RAG 结果相对稳定
        - maxsize: 500，RAG 查询结果较大，不宜过多
        """
        return self.get_cache(
            name="rag",
            ttl=config.cache_rag_ttl,
            local_maxsize=500,
        )

    def get_tool_schema_cache(self) -> DualLayerCache:
        """获取工具 Schema 缓存

        【配置说明】
        - TTL: 较长（通常 600s+），Schema 变更不频繁
        - maxsize: 200，工具数量有限
        """
        return self.get_cache(
            name="tool_schema",
            ttl=config.cache_tool_schema_ttl,
            local_maxsize=200,
        )

    def get_model_list_cache(self) -> DualLayerCache:
        """获取模型列表缓存

        【配置说明】
        - TTL: 较短（通常 60s），模型状态可能变化
        - maxsize: 10，模型列表单一，容量需求小
        """
        return self.get_cache(
            name="model_list",
            ttl=config.cache_model_list_ttl,
            local_maxsize=10,
        )

    def get_all_stats(self) -> dict[str, dict]:
        """获取所有缓存统计

        用于监控和调优，可定期输出到日志或监控系统
        """
        return {name: cache.get_stats() for name, cache in self._caches.items()}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 全局缓存管理器实例
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 全局单例：应用启动时初始化
_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """获取缓存管理器实例

    Returns:
        CacheManager 实例

    Raises:
        RuntimeError: 缓存管理器未初始化
            通常是因为应用启动时未调用 init_cache_manager()
    """
    global _cache_manager
    if _cache_manager is None:
        raise RuntimeError(
            "Cache manager not initialized. "
            "Call init_cache_manager(redis) during application startup."
        )
    return _cache_manager


def init_cache_manager(redis: Redis) -> CacheManager:
    """初始化缓存管理器

    【调用时机】
    在应用启动时调用，通常在 FastAPI 的 lifespan 或 on_event("startup") 中：

    ```python
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动时初始化
        redis = Redis.from_url(config.redis_url)
        init_cache_manager(redis)
        yield
        # 关闭时清理
        await redis.close()
    ```

    Args:
        redis: Redis 客户端实例

    Returns:
        初始化后的 CacheManager 实例
    """
    global _cache_manager
    _cache_manager = CacheManager(redis)
    return _cache_manager


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 缓存装饰器
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def cached(
    cache_name: str,
    key_builder: Callable[..., str] | None = None,
    ttl: int | None = None,
):
    """缓存装饰器（声明式缓存）

    【使用方式】
    将函数结果自动缓存，无需手动调用 get/set：

    ```python
    @cached("rag", key_builder=lambda q: DualLayerCache._hash_key(q))
    async def search(query: str) -> list:
        # 复杂的 RAG 搜索逻辑
        return await rag_engine.search(query)
    ```

    【工作原理】
    1. 调用函数前，检查缓存
    2. 缓存命中 → 直接返回
    3. 缓存未命中 → 执行函数，缓存结果，返回

    【适用场景】
    - 函数结果可缓存（幂等）
    - 函数参数可哈希
    - 不适合需要精确控制缓存的场景

    Args:
        cache_name: 缓存名称（使用 CacheManager.get_cache(name)）
        key_builder: 键生成函数，接收被装饰函数的参数
            - 默认：使用 args/kwargs 的 JSON 哈希
            - 自定义：lambda arg1, arg2: f"prefix:{arg1}:{arg2}"
        ttl: 缓存 TTL（秒）
    """
    from functools import wraps

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_manager().get_cache(cache_name, ttl=ttl)

            # 生成键
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                # 默认使用参数哈希
                key = DualLayerCache._hash_key({"args": args, "kwargs": kwargs})

            return await cache.get_or_set(key, lambda: func(*args, **kwargs), ttl)

        return wrapper  # type: ignore

    return decorator
