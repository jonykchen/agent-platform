package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 模型调用统计响应 DTO
 */
@Data
@Builder
public class ModelCallStatsResponse {

    /** 模型名称 */
    private String model;

    /** 总调用次数 */
    private Long totalCalls;

    /** 成功率 (0-100) */
    private Double successRate;

    /** 平均延迟 (毫秒) */
    private Double avgLatencyMs;

    /** 总 Token 数 */
    private Long totalTokens;

    /** 成本 (美元) */
    private Double costUsd;
}
