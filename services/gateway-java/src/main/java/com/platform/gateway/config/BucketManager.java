package com.platform.gateway.config;

import io.github.bucket4j.Bucket;
import io.github.bucket4j.BucketConfiguration;

/**
 * 限流 Bucket 管理器抽象
 *
 * <p>统一本地（单实例）与分布式（Redis，多实例）两种限流实现的契约。
 * 由 {@link RateLimitConfig} 根据 {@code rate-limit.distributed.enabled}
 * 注入对应实现：
 * <ul>
 *   <li>{@code false}（默认）→ {@code LocalBucketManager}：ConcurrentHashMap 本地存储</li>
 *   <li>{@code true} → {@code RedisBucketManager}：基于 bucket4j-redis (Lettuce)
 *       的跨实例共享限流，多副本部署时配额全局一致</li>
 * </ul>
 */
public interface BucketManager {

    /**
     * 获取或创建用户级限流 Bucket。
     *
     * @param userId        用户 ID（或 IP 限流键）
     * @param configuration Bucket 配置
     * @return Bucket 实例
     */
    Bucket getUserBucket(String userId, BucketConfiguration configuration);

    /**
     * 获取或创建租户级限流 Bucket。
     *
     * @param tenantId      租户 ID
     * @param configuration Bucket 配置
     * @return Bucket 实例
     */
    Bucket getTenantBucket(String tenantId, BucketConfiguration configuration);
}
