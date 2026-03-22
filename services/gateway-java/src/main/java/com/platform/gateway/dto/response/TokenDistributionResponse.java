package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * Token 分布统计响应 DTO
 */
@Data
@Builder
public class TokenDistributionResponse {

    /** 模型名称 */
    private String model;

    /** Token 数 */
    private Long tokens;

    /** 占比 (0-100) */
    private Double percentage;

    /** 成本 (美元) */
    private Double costUsd;
}
