package com.platform.gateway.dto.response;

import lombok.Data;

/**
 * 工具调用信息
 */
@Data
public class ToolCallInfo {

    private String callId;
    private String toolName;
    private String argumentsJson;
}