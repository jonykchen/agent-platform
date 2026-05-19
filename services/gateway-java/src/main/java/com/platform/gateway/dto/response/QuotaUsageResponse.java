package com.platform.gateway.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 租户配额使用情况响应 DTO
 *
 * <p>返回租户各类资源的配额使用情况，用于仪表盘展示。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/tenants/{tenantId}/quota - 获取租户配额使用情况</li>
 * </ul>
 *
 * <p>【权限要求】tenant:read
 *
 * @see com.platform.gateway.controller.TenantController#getQuotaUsage
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuotaUsageResponse {

    /**
     * 租户ID
     */
    @JsonProperty("tenant_id")
    private String tenantId;

    /**
     * Token 配额使用情况
     */
    @JsonProperty("token_usage")
    private TokenUsage tokenUsage;

    /**
     * 会话配额使用情况
     */
    @JsonProperty("session_usage")
    private SessionUsage sessionUsage;

    /**
     * 用户配额使用情况
     */
    @JsonProperty("user_usage")
    private UserUsage userUsage;

    /**
     * API Key 配额使用情况
     */
    @JsonProperty("api_key_usage")
    private ApiKeyUsage apiKeyUsage;

    /**
     * 配额周期
     *
     * <p>【可选值】daily（每日）、monthly（每月）
     */
    @JsonProperty("quota_period")
    private String quotaPeriod;

    /**
     * 配额重置时间
     */
    @JsonProperty("reset_at")
    private String resetAt;

    /**
     * Token 使用情况
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TokenUsage {

        /**
         * 已使用量
         */
        private Long used;

        /**
         * 配额上限
         */
        private Long limit;

        /**
         * 使用百分比
         */
        private Double percentage;

        /**
         * 输入 Token 数
         */
        @JsonProperty("input_tokens")
        private Long inputTokens;

        /**
         * 输出 Token 数
         */
        @JsonProperty("output_tokens")
        private Long outputTokens;
    }

    /**
     * 会话使用情况
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class SessionUsage {

        /**
         * 活跃会话数
         */
        @JsonProperty("active_count")
        private Integer activeCount;

        /**
         * 最大会话数
         */
        @JsonProperty("max_count")
        private Integer maxCount;

        /**
         * 使用百分比
         */
        private Double percentage;
    }

    /**
     * 用户使用情况
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class UserUsage {

        /**
         * 当前用户数
         */
        @JsonProperty("current_count")
        private Integer currentCount;

        /**
         * 最大用户数
         */
        @JsonProperty("max_count")
        private Integer maxCount;

        /**
         * 使用百分比
         */
        private Double percentage;
    }

    /**
     * API Key 使用情况
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ApiKeyUsage {

        /**
         * 当前 API Key 数
         */
        @JsonProperty("current_count")
        private Integer currentCount;

        /**
         * 最大 API Key 数
         */
        @JsonProperty("max_count")
        private Integer maxCount;

        /**
         * 使用百分比
         */
        private Double percentage;
    }
}
