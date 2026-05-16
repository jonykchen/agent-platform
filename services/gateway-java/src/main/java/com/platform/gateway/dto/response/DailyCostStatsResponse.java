package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 每日成本统计响应 DTO
 *
 * <p>按日统计的 Token 消耗和成本数据，用于成本趋势图表展示。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/dashboard/costs/daily - 获取每日成本统计</li>
 * </ul>
 *
 * <p>【数据范围】当前租户在指定日期范围内的统计数据
 *
 * @see com.platform.gateway.controller.DashboardController
 */
@Data
@Builder
public class DailyCostStatsResponse {

    /**
     * 日期
     *
     * <p>统计日期。
     *
     * <p>【格式】YYYY-MM-DD，如 "2026-05-01"
     */
    private String date;

    /**
     * 成本（美元）
     *
     * <p>当天的总成本，按模型定价计算。
     *
     * <p>【单位】美元（USD）
     */
    private Double costUsd;

    /**
     * Token 数
     *
     * <p>当天消耗的 Token 总数。
     */
    private Long tokens;
}
