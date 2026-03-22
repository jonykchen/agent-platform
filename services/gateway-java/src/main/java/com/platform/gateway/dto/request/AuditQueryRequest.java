package com.platform.gateway.dto.request;

import lombok.Data;

import java.time.Instant;

/**
 * 审计事件查询请求
 */
@Data
public class AuditQueryRequest {

    private Integer pageNumber = 1;

    private Integer pageSize = 20;

    private String eventType;

    private String eventCategory;

    private String severity;

    private String userId;

    private String resourceType;

    private String resourceId;

    private Instant startTime;

    private Instant endTime;

    private String sortBy;

    private Boolean sortDescending = true;
}
