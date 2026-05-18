package com.platform.gateway.config;

import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.BucketConfiguration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 速率限制配置
 *
 * <p>使用 Bucket4j 实现多维度速率限制，支持：
 * <ul>
 *   <li>用户级 RPM (Requests Per Minute) 限制</li>
 *   <li>租户级 TPM (Tokens Per Minute) 限制</li>
 * </ul>
 *
 * <h2>速率限制架构</h2>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          请求入口                                           │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *                              │
 *                              ▼
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │  L1: 用户级限流 (RPM)                                                        │
 * │  ┌─────────────────────────────────────────────────────────────────────┐   │
 * │  │  Bucket: user:{user_id}                                             │   │
 * │  │  限制: 60 requests/minute (默认)                                    │   │
 * │  │  超限: HTTP 429 Too Many Requests                                   │   │
 * │  └─────────────────────────────────────────────────────────────────────┘   │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *                              │
 *                              ▼
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │  L2: 租户级限流 (TPM)                                                        │
 * │  ┌─────────────────────────────────────────────────────────────────────┐   │
 * │  │  Bucket: tenant:{tenant_id}                                         │   │
 * │  │  限制: 100,000 tokens/minute (默认)                                 │   │
 * │  │  计数: 基于实际 token 使用量                                         │   │
 * │  └─────────────────────────────────────────────────────────────────────┘   │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *                              │
 *                              ▼
 *                         正常处理请求
 * </pre>
 *
 * <h2>配置项</h2>
 * <ul>
 *   <li>{@code rate-limit.user.rpm}: 每用户每分钟请求数限制，默认 60</li>
 *   <li>{@code rate-limit.tenant.tpm}: 每租户每分钟 token 数限制，默认 100,000</li>
 * </ul>
 *
 * <h2>分布式支持说明</h2>
 * <p>当前版本使用本地内存存储，适用于单实例部署。
 * 生产环境多实例部署时，建议升级为 Redis 分布式限流方案：
 * <ul>
 *   <li>添加 bucket4j-redis 依赖</li>
 *   <li>使用 RedisBasedBucket 实现跨实例共享</li>
 * </ul>
 *
 * @see io.github.bucket4j.Bucket
 */
@Configuration
public class RateLimitConfig {

    @Value("${rate-limit.user.rpm:60}")
    private int userRpm;

    @Value("${rate-limit.tenant.tpm:100000}")
    private int tenantTpm;

    @Value("${rate-limit.enabled:true}")
    private boolean rateLimitEnabled;

    /**
     * 用户级 Bucket 配置
     *
     * <p>使用令牌桶算法，每分钟补充令牌，允许短时突发流量。
     *
     * @return Bucket 配置
     */
    @Bean
    public BucketConfiguration userBucketConfiguration() {
        // 每分钟补充令牌，允许一定突发
        Bandwidth bandwidth = Bandwidth.builder()
                .capacity(userRpm)
                .refillIntervally(userRpm, Duration.ofMinutes(1))
                .build();

        return BucketConfiguration.builder()
                .addLimit(bandwidth)
                .build();
    }

    /**
     * 租户级 Token Bucket 配置
     *
     * <p>基于实际 token 使用量计费，适用于 LLM 调用场景。
     *
     * @return Bucket 配置
     */
    @Bean
    public BucketConfiguration tenantBucketConfiguration() {
        Bandwidth bandwidth = Bandwidth.builder()
                .capacity(tenantTpm)
                .refillIntervally(tenantTpm, Duration.ofMinutes(1))
                .build();

        return BucketConfiguration.builder()
                .addLimit(bandwidth)
                .build();
    }

    /**
     * 本地内存 Bucket 存储
     *
     * <p>适用于单实例部署或本地测试。生产环境多实例部署建议使用 Redis 分布式方案。
     *
     * @return Bucket 管理器
     */
    @Bean
    public LocalBucketManager localBucketManager() {
        return new LocalBucketManager();
    }

    /**
     * 本地内存 Bucket 管理器
     *
     * <p>用于单实例场景，使用 ConcurrentHashMap 存储 Bucket。
     * 线程安全，支持高并发访问。
     */
    public static class LocalBucketManager {

        private final ConcurrentHashMap<String, Bucket> buckets = new ConcurrentHashMap<>();

        /**
         * 获取或创建用户级 Bucket
         *
         * @param userId 用户 ID
         * @param configuration Bucket 配置
         * @return Bucket 实例
         */
        public Bucket getUserBucket(String userId, BucketConfiguration configuration) {
            String key = "user:" + userId;
            return buckets.computeIfAbsent(key, k -> {
                Bandwidth[] bandwidths = configuration.getBandwidths();
                long capacity = bandwidths.length > 0 ? bandwidths[0].getCapacity() : 60L;
                Bandwidth bandwidth = Bandwidth.builder()
                        .capacity(capacity)
                        .refillIntervally(capacity, Duration.ofMinutes(1))
                        .build();
                return Bucket.builder()
                        .addLimit(bandwidth)
                        .build();
            });
        }

        /**
         * 获取或创建租户级 Bucket
         *
         * @param tenantId 租户 ID
         * @param configuration Bucket 配置
         * @return Bucket 实例
         */
        public Bucket getTenantBucket(String tenantId, BucketConfiguration configuration) {
            String key = "tenant:" + tenantId;
            return buckets.computeIfAbsent(key, k -> {
                Bandwidth[] bandwidths = configuration.getBandwidths();
                long capacity = bandwidths.length > 0 ? bandwidths[0].getCapacity() : 100000L;
                Bandwidth bandwidth = Bandwidth.builder()
                        .capacity(capacity)
                        .refillIntervally(capacity, Duration.ofMinutes(1))
                        .build();
                return Bucket.builder()
                        .addLimit(bandwidth)
                        .build();
            });
        }

        /**
         * 清除所有 Bucket（用于测试）
         */
        public void clearAll() {
            buckets.clear();
        }

        /**
         * 清除指定用户的 Bucket
         *
         * @param userId 用户 ID
         */
        public void clearUserBucket(String userId) {
            buckets.remove("user:" + userId);
        }

        /**
         * 清除指定租户的 Bucket
         *
         * @param tenantId 租户 ID
         */
        public void clearTenantBucket(String tenantId) {
            buckets.remove("tenant:" + tenantId);
        }
    }
}