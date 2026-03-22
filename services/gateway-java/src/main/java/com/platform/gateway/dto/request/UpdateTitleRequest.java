package com.platform.gateway.dto.request;

import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 更新会话标题请求
 */
@Data
public class UpdateTitleRequest {

    /**
     * 新标题
     */
    @Size(max = 256, message = "标题最长256个字符")
    private String title;
}