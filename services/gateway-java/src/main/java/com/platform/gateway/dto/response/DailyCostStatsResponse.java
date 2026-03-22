package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 每日成本统计响应 DTO
 */
@Data
@Builder
public class DailyCostStatsResponse {

    /** 日期 (YYYY-MM-DD) */
    private String date;

    /** 成本 (美元) */
    private Double costUsd;

    /** Token 数 */
    private Long tokens;
}
