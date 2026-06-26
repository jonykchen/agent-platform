package com.platform.gateway.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.StringRedisSerializer;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * 缓存配置
 *
 * <p>使用 Redis 作为分布式缓存后端，支持多实例部署。
 *
 * <p>【缓存命名空间】
 * <ul>
 *   <li>dashboard-stats: 仪表盘统计数据（5 分钟 TTL）</li>
 *   <li>dashboard-daily-runs: 每日运行趋势（10 分钟 TTL）</li>
 *   <li>dashboard-daily-costs: 每日成本趋势（10 分钟 TTL）</li>
 *   <li>dashboard-token-distribution: Token 分布（10 分钟 TTL）</li>
 *   <li>dashboard-model-stats: 模型调用统计（10 分钟 TTL）</li>
 *   <li>tenant-config: 租户配置（10 分钟 TTL）</li>
 *   <li>tenant-usage: 租户用量统计（5 分钟 TTL）</li>
 *   <li>model-configs: 模型配置（30 分钟 TTL）</li>
 * </ul>
 *
 * <p>【序列化策略】
 * <ul>
 *   <li>Key: String 序列化（便于 Redis CLI 查看）</li>
 *   <li>Value: JSON 序列化（跨语言兼容）</li>
 * </ul>
 */
@Configuration
@EnableCaching
public class CacheConfig {

    /**
     * 仪表盘统计数据缓存 TTL（5 分钟）
     */
    private static final Duration DASHBOARD_STATS_TTL = Duration.ofMinutes(5);

    /**
     * 趋势数据缓存 TTL（10 分钟）
     */
    private static final Duration DASHBOARD_TREND_TTL = Duration.ofMinutes(10);

    /**
     * 租户配置缓存 TTL（10 分钟）
     * 配置变更频率低，可缓存较长时间
     */
    private static final Duration TENANT_CONFIG_TTL = Duration.ofMinutes(10);

    /**
     * 租户用量统计缓存 TTL（5 分钟）
     * 用量数据需要一定实时性
     */
    private static final Duration TENANT_USAGE_TTL = Duration.ofMinutes(5);

    /**
     * 模型配置缓存 TTL（30 分钟）
     * 模型配置极少变更
     */
    private static final Duration MODEL_CONFIG_TTL = Duration.ofMinutes(30);

    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory connectionFactory) {
        // 配置 ObjectMapper 支持 Java 8 时间类型
        ObjectMapper objectMapper = new ObjectMapper();
        objectMapper.registerModule(new JavaTimeModule());
        objectMapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

        // 默认配置：5 分钟 TTL
        RedisCacheConfiguration defaultConfig = RedisCacheConfiguration.defaultCacheConfig()
                .serializeKeysWith(RedisSerializationContext.SerializationPair.fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(new GenericJackson2JsonRedisSerializer(objectMapper)))
                .entryTtl(DASHBOARD_STATS_TTL)
                .disableCachingNullValues()
                .prefixCacheNameWith("gateway:");

        // 各缓存空间的个性化配置
        Map<String, RedisCacheConfiguration> cacheConfigurations = new HashMap<>();

        // 仪表盘统计数据：5 分钟 TTL
        cacheConfigurations.put("dashboard-stats", defaultConfig.entryTtl(DASHBOARD_STATS_TTL));

        // 趋势数据：10 分钟 TTL
        cacheConfigurations.put("dashboard-daily-runs", defaultConfig.entryTtl(DASHBOARD_TREND_TTL));
        cacheConfigurations.put("dashboard-daily-costs", defaultConfig.entryTtl(DASHBOARD_TREND_TTL));
        cacheConfigurations.put("dashboard-token-distribution", defaultConfig.entryTtl(DASHBOARD_TREND_TTL));
        cacheConfigurations.put("dashboard-model-stats", defaultConfig.entryTtl(DASHBOARD_TREND_TTL));

        // 租户配置：10 分钟 TTL（变更频率低）
        cacheConfigurations.put("tenant-config", defaultConfig.entryTtl(TENANT_CONFIG_TTL));

        // 租户用量统计：5 分钟 TTL（需要一定实时性）
        cacheConfigurations.put("tenant-usage", defaultConfig.entryTtl(TENANT_USAGE_TTL));

        // 模型配置：30 分钟 TTL（极少变更）
        cacheConfigurations.put("model-configs", defaultConfig.entryTtl(MODEL_CONFIG_TTL));

        return RedisCacheManager.builder(connectionFactory)
                .cacheDefaults(defaultConfig)
                .withInitialCacheConfigurations(cacheConfigurations)
                .transactionAware()
                .build();
    }
}
