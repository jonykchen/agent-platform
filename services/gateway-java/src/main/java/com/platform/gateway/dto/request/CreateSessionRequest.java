package com.platform.gateway.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 创建会话请求
 */
@Data
public class CreateSessionRequest {

    /**
     * 会话类型
     * 可选值: chat, task, workflow
     */
    @NotBlank(message = "会话类型不能为空")
    private String sessionType;

    /**
     * 会话标题
     */
    @Size(max = 256, message = "标题最长256个字符")
    private String title;
}