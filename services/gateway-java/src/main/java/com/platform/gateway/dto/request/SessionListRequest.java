package com.platform.gateway.dto.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

/**
 * 会话列表查询请求
 */
@Data
public class SessionListRequest {

    /**
     * 会话状态过滤
     * 可选值: active, archived, closed
     */
    private String status;

    /**
     * 页码（从1开始）
     */
    @Min(value = 1, message = "页码最小为1")
    private Integer pageNumber = 1;

    /**
     * 每页大小
     */
    @Min(value = 1, message = "每页大小最小为1")
    @Max(value = 100, message = "每页大小最大为100")
    private Integer pageSize = 20;

    /**
     * 标题搜索关键词
     */
    private String search;
}
