package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;
import java.util.Map;

/**
 * 审计事件响应
 */
@Data
@Builder
public class AuditEventResponse {

    private Long id;

    private String eventId;

    private String eventType;

    private String eventCategory;

    private String severity;

    private String tenantId;

    private String userId;

    private String resourceType;

    private String resourceId;

    private String action;

    private Map<String, Object> beforeState;

    private Map<String, Object> afterState;

    private Map<String, Object> details;

    private String requestId;

    private String traceId;

    private String ipAddress;

    private String userAgent;

    private String sourceService;

    private Instant createdAt;
}
