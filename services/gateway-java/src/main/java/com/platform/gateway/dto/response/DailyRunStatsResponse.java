package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 每日运行统计响应 DTO
 *
 * <p>按日统计的 Agent 运行数据，用于趋势图表展示。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/dashboard/runs/daily - 获取每日运行统计</li>
 * </ul>
 *
 * <p>【数据范围】当前租户在指定日期范围内的统计数据
 *
 * @see com.platform.gateway.controller.DashboardController
 */
@Data
@Builder
public class DailyRunStatsResponse {

    /**
     * 日期
     *
     * <p>统计日期。
     *
     * <p>【格式】YYYY-MM-DD，如 "2026-05-01"
     */
    private String date;

    /**
     * 运行次数
     *
     * <p>当天的 Agent 执行总次数。
     */
    private Long runs;

    /**
     * 成功次数
     *
     * <p>当天成功完成的执行次数。
     */
    private Long successful;

    /**
     * 失败次数
     *
     * <p>当天失败的执行次数。
     */
    private Long failed;

    /**
     * 平均耗时（毫秒）
     *
     * <p>当天执行的平均耗时。
     *
     * <p>【单位】毫秒（ms）
     */
    private Double avgDurationMs;
}
