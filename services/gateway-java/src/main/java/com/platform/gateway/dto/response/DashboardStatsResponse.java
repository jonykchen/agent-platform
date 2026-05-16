package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 仪表盘统计数据响应 DTO
 *
 * <p>仪表盘的核心统计数据，用于首页概览展示。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/dashboard/stats - 获取仪表盘统计</li>
 * </ul>
 *
 * <p>【数据范围】当前租户在指定时间范围内的统计数据
 *
 * @see com.platform.gateway.controller.DashboardController
 */
@Data
@Builder
public class DashboardStatsResponse {

    /**
     * 总会话数
     *
     * <p>创建的会话总数。
     */
    private Long totalSessions;

    /**
     * 总运行次数
     *
     * <p>Agent 执行的总次数（包含对话和任务执行）。
     */
    private Long totalRuns;

    /**
     * 总 Token 数
     *
     * <p>消耗的 Token 总数（包含输入和输出）。
     */
    private Long totalTokens;

    /**
     * 总成本（美元）
     *
     * <p>按模型定价计算的总成本。
     *
     * <p>【单位】美元（USD）
     */
    private Double totalCostUsd;

    /**
     * 成功率
     *
     * <p>Agent 执行的成功率百分比。
     *
     * <p>【取值范围】0 ~ 100
     */
    private Double successRate;

    /**
     * 平均响应时间（毫秒）
     *
     * <p>从请求到达 Gateway 到响应返回的平均延迟。
     *
     * <p>【单位】毫秒（ms）
     */
    private Double avgResponseTimeMs;

    /**
     * 活跃用户数
     *
     * <p>在指定时间范围内有过操作的用户数量。
     */
    private Long activeUsers;

    /**
     * 待审批数
     *
     * <p>当前等待审批的任务数量。
     */
    private Long pendingApprovals;
}
