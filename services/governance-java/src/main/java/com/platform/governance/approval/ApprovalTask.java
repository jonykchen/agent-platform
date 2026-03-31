package com.platform.governance.approval;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;

/**
 * 审批任务实体
 */
@Data
@Builder
public class ApprovalTask {

    private String id;
    private String runId;
    private String toolInvocationId;
    private String toolName;
    private String tenantId;
    private String requesterId;
    private String assigneeId;
    private String approverId;
    private String approverEmail;
    private String status;           // pending / approved / rejected / expired
    private String reason;
    private String approvalReason;
    private String reviewerId;
    private String reviewComment;
    private Instant createdAt;
    private Instant expiresAt;
    private Instant reviewedAt;
    private Instant processedAt;
}
