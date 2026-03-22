package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

import java.util.Map;

/**
 * 审计统计响应
 */
@Data
@Builder
public class AuditStatsResponse {

    private Long totalEvents;

    private Map<String, Long> bySeverity;

    private Map<String, Long> byCategory;

    private Map<String, Long> byEventType;
}
