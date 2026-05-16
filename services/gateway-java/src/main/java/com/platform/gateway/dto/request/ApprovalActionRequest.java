package com.platform.gateway.dto.request;

import lombok.Data;

/**
 * 审批操作请求 DTO
 *
 * <p>用于审批人对审批任务执行批准或拒绝操作。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>POST /api/v1/approvals/{id}/approve - 批准审批</li>
 *   <li>POST /api/v1/approvals/{id}/reject - 拒绝审批</li>
 * </ul>
 *
 * <p>【权限要求】approval:approve 或 approval:reject
 *
 * <p>【审计说明】审批操作会记录到审计日志
 *
 * @see com.platform.gateway.controller.ApprovalController
 * @see com.platform.gateway.dto.response.ApprovalTaskResponse
 */
@Data
public class ApprovalActionRequest {

    /**
     * 审批意见/备注
     *
     * <p>审批人填写的审批意见或备注说明。
     *
     * <p>【选填】建议填写审批理由
     */
    private String comment;
}
