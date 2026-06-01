package com.platform.gateway.dto.config;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 配额配置 JSONB 映射类
 *
 * <p>映射 tenant.quota_config JSONB 字段。
 *
 * <p>【JSONB 结构】
 * <pre>
 * {
 *   "daily_tokens": 10000000,
 *   "monthly_cost_usd": 1000.0,
 *   "max_sessions": 1000,
 *   "max_users": 100,
 *   "max_api_keys": 10
 * }
 * </pre>
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class QuotaConfig {

    @JsonProperty("daily_tokens")
    private Long dailyTokens = 10_000_000L;

    @JsonProperty("monthly_cost_usd")
    private Double monthlyCostUsd = 1000.0;

    @JsonProperty("max_sessions")
    private Integer maxSessions = 1000;

    @JsonProperty("max_users")
    private Integer maxUsers = 100;

    @JsonProperty("max_api_keys")
    private Integer maxApiKeys = 10;

    /**
     * 获取默认配置
     */
    public static QuotaConfig defaultConfig() {
        return new QuotaConfig();
    }

    /**
     * 根据 tier 获取默认配置
     */
    public static QuotaConfig defaultForTier(String tier) {
        return switch (tier) {
            case "free" -> new QuotaConfig(1_000_000L, 50.0, 50, 5, 2);
            case "standard" -> new QuotaConfig(5_000_000L, 200.0, 500, 50, 5);
            case "premium" -> new QuotaConfig(10_000_000L, 500.0, 1000, 100, 10);
            case "enterprise" -> new QuotaConfig(10_000_000L, 1000.0, 1000, 100, 20);
            default -> defaultConfig();
        };
    }
}
