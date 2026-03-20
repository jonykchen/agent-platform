package com.platform.gateway.dto.request;

import lombok.Data;

/**
 * 对话历史消息
 */
@Data
public class MessageHistory {

    private String role;    // user / assistant / system
    private String content;
}