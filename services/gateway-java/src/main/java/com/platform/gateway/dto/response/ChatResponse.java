package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * 对话响应 DTO
 */
@Data
@Builder
public class ChatResponse {

    private String requestId;

    private String response;

    private String modelUsed;

    private Integer promptTokens;

    private Integer completionTokens;

    private Integer totalTokens;

    private Double costUsd;

    private List<ToolCallInfo> toolCalls;

    private Long createdAt;

    private Integer latencyMs;

    private String finishReason;

    private String error;
}