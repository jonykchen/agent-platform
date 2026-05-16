package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * Token 分布统计响应 DTO
 *
 * <p>按模型统计的 Token 使用分布，用于分析各模型的资源消耗占比。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/dashboard/tokens/distribution - 获取 Token 分布统计</li>
 * </ul>
 *
 * <p>【数据范围】当前租户在指定时间范围内的统计数据
 *
 * @see com.platform.gateway.controller.DashboardController
 */
@Data
@Builder
public class TokenDistributionResponse {

    /**
     * 模型名称
     *
     * <p>LLM 模型名称。
     *
     * <p>【示例】qwen-plus、deepseek-chat
     */
    private String model;

    /**
     * Token 数
     *
     * <p>该模型消耗的 Token 数量。
     */
    private Long tokens;

    /**
     * 占比
     *
     * <p>该模型 Token 数占总 Token 数的百分比。
     *
     * <p>【取值范围】0 ~ 100
     */
    private Double percentage;

    /**
     * 成本（美元）
     *
     * <p>该模型的总成本。
     *
     * <p>【单位】美元（USD）
     */
    private Double costUsd;
}
