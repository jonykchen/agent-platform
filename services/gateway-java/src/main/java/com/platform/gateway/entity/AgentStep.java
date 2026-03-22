package com.platform.gateway.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

/**
 * Agent 执行步骤实体
 * 映射 agent_step 表
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "agent_step", indexes = {
    @Index(name = "idx_step_run", columnList = "run_id, step_order"),
    @Index(name = "idx_step_tenant", columnList = "tenant_id, created_at"),
    @Index(name = "idx_step_type", columnList = "step_type")
})
public class AgentStep {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    /**
     * 关联运行实例
     */
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "run_id", nullable = false, foreignKey = @ForeignKey(name = "fk_step_run"))
    private AgentRun run;

    @Column(name = "run_id", nullable = false, insertable = false, updatable = false)
    private UUID runId;

    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId;

    @Column(name = "step_order", nullable = false)
    private Integer stepOrder;

    @Column(name = "step_type", nullable = false, length = 32)
    private String stepType;

    @Column(name = "content", nullable = false, columnDefinition = "TEXT")
    private String content;

    @Column(name = "tool_name", length = 128)
    private String toolName;

    @Column(name = "tool_input", columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    private String toolInput;

    @Column(name = "tool_output", columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    private String toolOutput;

    @Column(name = "thinking", columnDefinition = "TEXT")
    private String thinking;

    @Column(name = "token_count")
    @Builder.Default
    private Integer tokenCount = 0;

    @Column(name = "duration_ms")
    private Integer durationMs;

    @Column(name = "metadata", columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    @Builder.Default
    private String metadata = "{}";

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    protected void onCreate() {
        if (createdAt == null) {
            createdAt = Instant.now();
        }
    }
}
