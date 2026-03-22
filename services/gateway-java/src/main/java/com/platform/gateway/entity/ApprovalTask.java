package com.platform.gateway.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * 审批任务实体
 * 映射 approval_task 表
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

    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId;

    @Column(name = "task_type", nullable = false, length = 32)
    private String taskType;

    @Column(name = "title", nullable = false, length = 256)
    private String title;

    @Column(name = "description", nullable = false, columnDefinition = "TEXT")
    private String description;

    @Column(name = "request_context", nullable = false, columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    private Map<String, Object> requestContext;

    @Column(name = "requester_id", nullable = false, length = 128)
    private String requesterId;

    @Column(name = "assignee_id", length = 128)
    private String assigneeId;

    @Column(name = "priority", length = 16)
    @Builder.Default
    private String priority = "normal";

    @Column(name = "status", nullable = false, length = 32)
    @Builder.Default
    private String status = "pending";

    @Column(name = "reviewer_id", length = 128)
    private String reviewerId;

    @Column(name = "review_comment", columnDefinition = "TEXT")
    private String reviewComment;

    @Column(name = "reviewed_at")
    private Instant reviewedAt;

    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    protected void onCreate() {
        Instant now = Instant.now();
        this.createdAt = now;
        this.updatedAt = now;
        if (this.status == null) {
            this.status = "pending";
        }
        if (this.priority == null) {
            this.priority = "normal";
        }
    }

    @PreUpdate
    protected void onUpdate() {
        this.updatedAt = Instant.now();
    }
}
