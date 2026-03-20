package com.platform.gateway.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.List;

/**
 * 对话请求 DTO
 */
@Data
public class ChatRequest {

    @NotBlank(message = "消息不能为空")
    private String message;

    private List<MessageHistory> history;

    private String model;

    private Double temperature;

    private Integer maxTokens;

    private Boolean stream;

    private Boolean enableRag;

    private Boolean enableTools;

    private List<String> toolWhitelist;
}