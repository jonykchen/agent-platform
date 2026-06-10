package com.platform.gateway.config;

import io.github.bucket4j.Bucket;
import io.github.bucket4j.BucketConfiguration;
import io.github.bucket4j.distributed.ExpirationAfterWriteStrategy;
import io.github.bucket4j.distributed.proxy.ProxyManager;
import io.github.bucket4j.redis.lettuce.cas.LettuceBasedProxyManager;
import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisURI;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * 分布式限流配置（Redis + Bucket4j）
 *
 * <p>仅当 {@code rate-limit.distributed.enabled=true} 时启用。多实例部署下，
 * 限流配额通过 Redis 全局共享，避免本地内存方案在多副本场景下"每实例独立配额"
 * 导致的实际限流失效。
 *
 * <p>实现基于 bucket4j-redis 的 {@link LettuceBasedProxyManager}（CAS 乐观并发），
 * Bucket 状态以 byte[] key 存于 Redis，并设置基于补满时间的过期，避免冷 key 堆积。
 */
@Slf4j
@Configuration
@ConditionalOnProperty(name = "rate-limit.distributed.enabled", havingValue = "true")
public class RedisRateLimitConfig {

    @Value("${spring.data.redis.host:localhost}")
    private String redisHost;

    @Value("${spring.data.redis.port:6379}")
    private int redisPort;

    @Value("${spring.data.redis.password:}")
    private String redisPassword;

    @Value("${rate-limit.user.rpm:60}")
    private int userRpm;

    @Value("${rate-limit.tenant.tpm:100000}")
    private int tenantTpm;

    private RedisClient redisClient;

    @Bean
    public RedisClient rateLimitRedisClient() {
        RedisURI.Builder uriBuilder = RedisURI.builder()
                .withHost(redisHost)
                .withPort(redisPort);
        if (redisPassword != null && !redisPassword.isBlank()) {
            uriBuilder.withPassword(redisPassword.toCharArray());
        }
        this.redisClient = RedisClient.create(uriBuilder.build());
        log.info("Distributed rate limiting enabled (Redis {}:{})", redisHost, redisPort);
        return this.redisClient;
    }

    @Bean
    public ProxyManager<byte[]> lettuceProxyManager(RedisClient rateLimitRedisClient) {
        // 过期策略：按补满至最大容量所需时间设置 TTL（+1 分钟缓冲），避免冷 key 永久驻留
        return LettuceBasedProxyManager.builderFor(rateLimitRedisClient)
                .withExpirationStrategy(
                        ExpirationAfterWriteStrategy.basedOnTimeForRefillingBucketUpToMax(
                                Duration.ofMinutes(2)))
                .build();
    }

    @Bean
    public BucketManager redisBucketManager(ProxyManager<byte[]> lettuceProxyManager) {
        return new RedisBucketManager(lettuceProxyManager);
    }

    @PreDestroy
    public void shutdown() {
        if (redisClient != null) {
            redisClient.shutdown();
            log.info("Rate limit Redis client shut down");
        }
    }

    /**
     * 基于 Redis ProxyManager 的分布式 Bucket 管理器。
     */
    public static class RedisBucketManager implements BucketManager {

        private final ProxyManager<byte[]> proxyManager;

        public RedisBucketManager(ProxyManager<byte[]> proxyManager) {
            this.proxyManager = proxyManager;
        }

        @Override
        public Bucket getUserBucket(String userId, BucketConfiguration configuration) {
            return resolve("rl:user:" + userId, configuration);
        }

        @Override
        public Bucket getTenantBucket(String tenantId, BucketConfiguration configuration) {
            return resolve("rl:tenant:" + tenantId, configuration);
        }

        private Bucket resolve(String key, BucketConfiguration configuration) {
            byte[] keyBytes = key.getBytes(StandardCharsets.UTF_8);
            // BucketProxy 实现 Bucket 接口，跨实例共享 Redis 中的同一限流状态
            return proxyManager.builder().build(keyBytes, configuration);
        }
    }
}
