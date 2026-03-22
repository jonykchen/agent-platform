package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 每日运行统计响应 DTO
 */
@Data
@Builder
public class DailyRunStatsResponse {

    /** 日期 (YYYY-MM-DD) */
    private String date;

    /** 运行次数 */
    private Long runs;

    /** 成功次数 */
    private Long successful;

    /** 失败次数 */
    private Long failed;

    /** 平均耗时 (毫秒) */
    private Double avgDurationMs;
}
