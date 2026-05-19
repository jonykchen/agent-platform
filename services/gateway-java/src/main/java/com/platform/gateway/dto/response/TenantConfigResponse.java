package com.platform.gateway.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;

/**
 * 租户配置响应 DTO
 *
 * <p>返回租户的完整配置信息，包括配额、功能开关等。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/tenants/{tenantId} - 获取租户配置</li>
 * </ul>
 *
 * <p>【权限要求】tenant:read
 *
 * @see com.platform.gateway.controller.TenantController#getTenantConfig
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TenantConfigResponse {

    /**
     * 租户ID
     *
     * <p>租户的唯一标识。
     *
     * <p>【格式】以 "tenant_" 开头的字符串
     */
    private String id;

    /**
     * 租户名称
     */
    private String name;

    /**
     * 租户状态
     *
     * <p>【可选值】active（活跃）、suspended（暂停）、cancelled（已取消）
     */
    private String status;

    /**
     * 配额配置
     *
     * <p>租户的资源配额限制。
     */
    @JsonProperty("quota_config")
    private QuotaConfig quotaConfig;

    /**
     * 功能开关
     *
     * <p>租户可用的功能模块。
     */
    @JsonProperty("feature_flags")
    private Map<String, Object> featureFlags;

    /**
     * 创建时间
     */
    @JsonProperty("created_at")
    private Instant createdAt;

    /**
     * 更新时间
     */
    @JsonProperty("updated_at")
    private Instant updatedAt;

    /**
     * 配额配置内部类
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class QuotaConfig {

        /**
         * 每日 Token 配额
         */
        @JsonProperty("daily_tokens")
        private Long dailyTokens;

        /**
         * 每日 Token 已使用量
         */
        @JsonProperty("daily_tokens_used")
        private Long dailyTokensUsed;

        /**
         * 最大并发会话数
         */
        @JsonProperty("max_sessions")
        private Integer maxSessions;

        /**
         * 当前活跃会话数
         */
        @JsonProperty("active_sessions")
        private Integer activeSessions;

        /**
         * 最大用户数
         */
        @JsonProperty("max_users")
        private Integer maxUsers;

        /**
         * 当前用户数
         */
        @JsonProperty("current_users")
        private Integer currentUsers;

        /**
         * 最大 API Key 数
         */
        @JsonProperty("max_api_keys")
        private Integer maxApiKeys;

        /**
         * 当前 API Key 数
         */
        @JsonProperty("current_api_keys")
        private Integer currentApiKeys;
    }
}
