package com.platform.gateway.dto.request;

import lombok.Data;

/**
 * 审批列表请求参数
 */
@Data
public class ApprovalListRequest {

    /**
     * 页码（从 1 开始）
     */
    private Integer page = 1;

    /**
     * 每页大小
     */
    private Integer page_size = 10;

    /**
     * 审批状态过滤
     */
    private String status;

    /**
     * 优先级过滤
     */
    private String priority;

    /**
     * 任务类型过滤
     */
    private String task_type;

    /**
     * 排序字段
     */
    private String sort_by = "created_at";

    /**
     * 排序方向
     */
    private String sort_order = "desc";
}
