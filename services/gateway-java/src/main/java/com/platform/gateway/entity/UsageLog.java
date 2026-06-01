package com.platform.gateway.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

/**
 * 用量日志实体
 * 映射 usage_log 表
 *
 * <p>按小时聚合的 Token、成本、请求数据，用于配额统计和用量分析。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "usage_log", uniqueConstraints = {
    @UniqueConstraint(name = "uk_usage_log", columnNames = {"tenant_id", "log_date", "log_hour", "model_used"})
}, indexes = {
    @Index(name = "idx_usage_log_tenant_date", columnList = "tenant_id, log_date DESC"),
    @Index(name = "idx_usage_log_tenant_date_model", columnList = "tenant_id, log_date, model_used"),
    @Index(name = "idx_usage_log_tenant_user", columnList = "tenant_id, user_id, log_date")
})
public class UsageLog {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId;

    @Column(name = "user_id", length = 128)
    private String userId;

    @Column(name = "log_date", nullable = false)
    private LocalDate logDate;

    @Column(name = "log_hour", nullable = false)
    @Builder.Default
    private Short logHour = 0;

    @Column(name = "input_tokens", nullable = false)
    @Builder.Default
    private Long inputTokens = 0L;

    @Column(name = "output_tokens", nullable = false)
    @Builder.Default
    private Long outputTokens = 0L;

    @Column(name = "total_tokens", nullable = false)
    @Builder.Default
    private Long totalTokens = 0L;

    @Column(name = "cost_usd", nullable = false, precision = 12, scale = 6)
    @Builder.Default
    private BigDecimal costUsd = BigDecimal.ZERO;

    @Column(name = "request_count", nullable = false)
    @Builder.Default
    private Integer requestCount = 0;

    @Column(name = "success_count", nullable = false)
    @Builder.Default
    private Integer successCount = 0;

    @Column(name = "failure_count", nullable = false)
    @Builder.Default
    private Integer failureCount = 0;

    @Column(name = "model_used", length = 64)
    private String modelUsed;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    protected void onCreate() {
        if (createdAt == null) {
            createdAt = Instant.now();
        }
    }
}
