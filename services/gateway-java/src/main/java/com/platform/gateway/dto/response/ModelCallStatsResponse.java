package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 模型调用统计响应 DTO
 *
 * <p>按模型统计的调用数据，用于分析各模型的使用情况和性能。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/dashboard/models - 获取模型调用统计</li>
 * </ul>
 *
 * <p>【数据范围】当前租户在指定时间范围内的统计数据
 *
 * @see com.platform.gateway.controller.DashboardController
 */
@Data
@Builder
public class ModelCallStatsResponse {

    /**
     * 模型名称
     *
     * <p>LLM 模型名称。
     *
     * <p>【示例】qwen-plus、deepseek-chat
     */
    private String model;

    /**
     * 总调用次数
     *
     * <p>该模型的总调用次数。
     */
    private Long totalCalls;

    /**
     * 成功率
     *
     * <p>该模型调用成功的百分比。
     *
     * <p>【取值范围】0 ~ 100
     */
    private Double successRate;

    /**
     * 平均延迟（毫秒）
     *
     * <p>该模型的平均响应延迟。
     *
     * <p>【单位】毫秒（ms）
     */
    private Double avgLatencyMs;

    /**
     * 总 Token 数
     *
     * <p>该模型消耗的 Token 总数。
     */
    private Long totalTokens;

    /**
     * 成本（美元）
     *
     * <p>该模型的总成本。
     *
     * <p>【单位】美元（USD）
     */
    private Double costUsd;
}
