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
 * 工具调用明细实体
 * 映射 tool_invocation 表
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "tool_invocation", indexes = {
    @Index(name = "idx_tool_invocation_run", columnList = "run_id"),
    @Index(name = "idx_tool_invocation_tool", columnList = "tool_name"),
    @Index(name = "idx_tool_invocation_status", columnList = "status")
})
public class ToolInvocation {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "step_id")
    private UUID stepId;

    @Column(name = "run_id", nullable = false)
    private UUID runId;

    @Column(name = "tool_name", nullable = false, length = 128)
    private String toolName;

    @Column(name = "tool_category", length = 32)
    private String toolCategory;

    @Column(name = "tool_version", length = 16)
    @Builder.Default
    private String toolVersion = "1.0";

    @Column(name = "risk_level", nullable = false, length = 16)
    @Builder.Default
    private String riskLevel = "low";

    @Column(name = "input_schema", columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    private Map<String, Object> inputSchema;

    @Column(name = "input_data", nullable = false, columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    private Map<String, Object> inputData;

    @Column(name = "output_data", columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    private Map<String, Object> outputData;

    @Column(name = "status", nullable = false, length = 32)
    private String status;

    @Column(name = "error_code", length = 64)
    private String errorCode;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "approval_id")
    private UUID approvalId;

    @Column(name = "was_cached", nullable = false)
    @Builder.Default
    private Boolean wasCached = false;

    @Column(name = "duration_ms")
    private Integer durationMs;

    @Column(name = "provider_latency_ms")
    private Integer providerLatencyMs;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    @PrePersist
    protected void onCreate() {
        if (createdAt == null) {
            createdAt = Instant.now();
        }
        if (status == null) {
            status = "pending";
        }
        if (riskLevel == null) {
            riskLevel = "low";
        }
        if (wasCached == null) {
            wasCached = false;
        }
    }
}
