package com.platform.gateway.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * Agent 运行实例实体
 * 映射 agent_run 表
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "agent_run", indexes = {
    @Index(name = "idx_run_tenant_created", columnList = "tenant_id, created_at"),
    @Index(name = "idx_run_user", columnList = "user_id, started_at"),
    @Index(name = "idx_run_session", columnList = "session_id"),
    @Index(name = "idx_run_status", columnList = "status"),
    @Index(name = "idx_run_model", columnList = "model_used")
}, uniqueConstraints = {
    @UniqueConstraint(name = "uk_session_run_number", columnNames = {"session_id", "run_number"})
})
public class AgentRun {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    /**
     * 关联会话
     */
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "session_id", nullable = false, foreignKey = @ForeignKey(name = "fk_run_session"))
    private AgentSession session;

    @Column(name = "session_id", nullable = false, insertable = false, updatable = false)
    private UUID sessionId;

    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId;

    @Column(name = "user_id", nullable = false, length = 128)
    private String userId;

    @Column(name = "run_number", nullable = false)
    private Integer runNumber;

    @Column(name = "input_message", nullable = false, columnDefinition = "TEXT")
    private String inputMessage;

    @Column(name = "output_message", columnDefinition = "TEXT")
    private String outputMessage;

    @Column(name = "status", nullable = false, length = 32)
    @Builder.Default
    private String status = "running";

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "error_code", length = 64)
    private String errorCode;

    @Column(name = "model_used", length = 64)
    private String modelUsed;

    @Column(name = "total_tokens")
    @Builder.Default
    private Integer totalTokens = 0;

    @Column(name = "total_cost_usd", precision = 10, scale = 6)
    @Builder.Default
    private BigDecimal totalCostUsd = BigDecimal.ZERO;

    @Column(name = "duration_ms")
    private Integer durationMs;

    @Column(name = "metadata", columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    @Builder.Default
    private String metadata = "{}";

    @Column(name = "started_at", nullable = false)
    private Instant startedAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    @PrePersist
    protected void onCreate() {
        if (startedAt == null) {
            startedAt = Instant.now();
        }
    }
}
