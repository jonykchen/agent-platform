package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 仪表盘统计数据响应 DTO
 */
@Data
@Builder
public class DashboardStatsResponse {

    /** 总会话数 */
    private Long totalSessions;

    /** 总运行次数 */
    private Long totalRuns;

    /** 总 Token 数 */
    private Long totalTokens;

    /** 总成本 (美元) */
    private Double totalCostUsd;

    /** 成功率 (0-100) */
    private Double successRate;

    /** 平均响应时间 (毫秒) */
    private Double avgResponseTimeMs;

    /** 活跃用户数 */
    private Long activeUsers;

    /** 待审批数 */
    private Long pendingApprovals;
}
