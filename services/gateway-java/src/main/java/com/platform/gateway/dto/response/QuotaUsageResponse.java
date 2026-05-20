package com.platform.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 租户配额使用情况响应 DTO
 *
 * <p>匹配前端 QuotaUsage 类型定义
 *
 * @see com.platform.gateway.controller.TenantController#getQuotaUsage
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuotaUsageResponse {

    /**
     * 每日 Token 已使用量
     */
    private Long dailyTokensUsed;

    /**
     * 每日 Token 配额上限
     */
    private Long dailyTokensLimit;

    /**
     * 月度成本已使用
     */
    private Double monthlyCostUsed;

    /**
     * 月度成本上限
     */
    private Double monthlyCostLimit;

    /**
     * 当前并发任务数
     */
    private Integer concurrentRunsCurrent;

    /**
     * 并发任务上限
     */
    private Integer concurrentRunsLimit;
}