package com.platform.gateway.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * 租户用量统计响应 DTO
 *
 * <p>返回租户的用量统计数据，包括 Token 消耗、请求次数等。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/tenants/{tenantId}/usage - 获取租户用量统计</li>
 * </ul>
 *
 * <p>【权限要求】tenant:read
 *
 * @see com.platform.gateway.controller.TenantController#getUsage
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UsageResponse {

    /**
     * 租户ID
     */
    @JsonProperty("tenant_id")
    private String tenantId;

    /**
     * 统计周期开始时间
     */
    @JsonProperty("period_start")
    private Instant periodStart;

    /**
     * 统计周期结束时间
     */
    @JsonProperty("period_end")
    private Instant periodEnd;

    /**
     * Token 使用统计
     */
    @JsonProperty("token_stats")
    private TokenStats tokenStats;

    /**
     * 请求统计
     */
    @JsonProperty("request_stats")
    private RequestStats requestStats;

    /**
     * 模型调用统计
     */
    @JsonProperty("model_stats")
    private ModelStats modelStats;

    /**
     * Token 使用统计
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TokenStats {

        /**
         * 总 Token 数
         */
        @JsonProperty("total_tokens")
        private Long totalTokens;

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

        /**
         * 日均 Token 数
         */
        @JsonProperty("daily_average")
        private Long dailyAverage;
    }

    /**
     * 请求统计
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RequestStats {

        /**
         * 总请求数
         */
        @JsonProperty("total_requests")
        private Long totalRequests;

        /**
         * 成功请求数
         */
        @JsonProperty("successful_requests")
        private Long successfulRequests;

        /**
         * 失败请求数
         */
        @JsonProperty("failed_requests")
        private Long failedRequests;

        /**
         * 成功率
         */
        @JsonProperty("success_rate")
        private Double successRate;

        /**
         * 平均响应时间（毫秒）
         */
        @JsonProperty("avg_response_time_ms")
        private Double avgResponseTimeMs;
    }

    /**
     * 模型调用统计
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ModelStats {

        /**
         * 模型名称
         */
        private String model;

        /**
         * 调用次数
         */
        private Long calls;

        /**
         * Token 数量
         */
        private Long tokens;

        /**
         * 平均响应时间（毫秒）
         */
        @JsonProperty("avg_latency_ms")
        private Long avgLatencyMs;
    }
}
