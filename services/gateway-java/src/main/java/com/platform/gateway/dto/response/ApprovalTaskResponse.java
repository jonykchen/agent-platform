package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;
import java.util.Map;

/**
 * 审批任务响应
 */
@Data
@Builder
public class ApprovalTaskResponse {

    /**
     * 审批任务 ID
     */
    private String id;

    /**
     * 运行实例 ID
     */
    private String run_id;

    /**
     * 工具调用 ID
     */
    private String tool_invocation_id;

    /**
     * 租户 ID
     */
    private String tenant_id;

    /**
     * 任务类型
     */
    private String task_type;

    /**
     * 任务标题
     */
    private String title;

    /**
     * 任务描述
     */
    private String description;

    /**
     * 请求上下文（工具参数等）
     */
    private Map<String, Object> request_context;

    /**
     * 请求者 ID
     */
    private String requester_id;

    /**
     * 指派审批人 ID
     */
    private String assignee_id;

    /**
     * 优先级
     */
    private String priority;

    /**
     * 状态
     */
    private String status;

    /**
     * 审批人 ID
     */
    private String reviewer_id;

    /**
     * 审批意见
     */
    private String review_comment;

    /**
     * 审批时间
     */
    private Instant reviewed_at;

    /**
     * 过期时间
     */
    private Instant expires_at;

    /**
     * 创建时间
     */
    private Instant created_at;

    /**
     * 更新时间
     */
    private Instant updated_at;
}
