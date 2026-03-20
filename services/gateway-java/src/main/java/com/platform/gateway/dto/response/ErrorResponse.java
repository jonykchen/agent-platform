package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 统一错误响应格式
 */
@Data
@Builder
public class ErrorResponse {

    private String error;
    private String message;
    private String userMessage;
    private String requestId;
    private Object details;
}