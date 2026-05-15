package com.platform.governance.approval;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;

/**
 * 审批任务实体
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "approval_task", indexes = {
    @Index(name = "idx_approval_status", columnList = "status"),
    @Index(name = "idx_approval_tenant", columnList = "tenant_id"),
    @Index(name = "idx_approval_assignee", columnList = "assignee_id, status"),
    @Index(name = "idx_approval_requester", columnList = "requester_id, created_at")
})
public class ApprovalTask {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "run_id", nullable = false)
    private UUID runId;

    @Column(name = "tool_invocation_id")
    private UUID toolInvocationId;

    @Column(name = "tool_name", length = 128)
    private String toolName;

    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId;

    @Column(name = "requester_id", nullable = false, length = 128)
    private String requesterId;

    @Column(name = "assignee_id", length = 128)
    private String assigneeId;

    @Column(name = "approver_id", length = 128)
    private String approverId;

    @Column(name = "approver_email", length = 256)
    private String approverEmail;

    @Column(name = "status", nullable = false, length = 32)
    @Builder.Default
    private String status = "pending";

    @Column(name = "reason", columnDefinition = "TEXT")
    private String reason;

    @Column(name = "approval_reason", columnDefinition = "TEXT")
    private String approvalReason;

    @Column(name = "reviewer_id", length = 128)
    private String reviewerId;

    @Column(name = "review_comment", columnDefinition = "TEXT")
    private String reviewComment;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    @Column(name = "reviewed_at")
    private Instant reviewedAt;

    @Column(name = "processed_at")
    private Instant processedAt;

    @PrePersist
    protected void onCreate() {
        Instant now = Instant.now();
        this.createdAt = now;
        if (this.status == null) {
            this.status = "pending";
        }
    }

    @PreUpdate
    protected void onUpdate() {
        // Lifecycle callback for updates if needed
    }
}