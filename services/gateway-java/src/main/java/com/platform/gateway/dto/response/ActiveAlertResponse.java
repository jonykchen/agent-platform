package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 活跃告警响应 DTO
 */
@Data
@Builder
public class ActiveAlertResponse {

    /** 告警 ID */
    private String id;

    /** 告警类型: error, warning, info */
    private String type;

    /** 告警消息 */
    private String message;

    /** 来源 */
    private String source;

    /** 创建时间 (ISO 8601) */
    private String createdAt;
}
